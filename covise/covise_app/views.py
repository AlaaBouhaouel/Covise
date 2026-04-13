import json
import logging
import random
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from pathlib import Path
from django.http import Http404, JsonResponse
from django.db import IntegrityError, OperationalError, close_old_connections
from django.utils import timezone
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import OnboardingResponse, PrivateProfileCompletion, WaitlistEmailVerification, WaitlistEntry
from covise_app.utils import generate_referral_code, upload_cv_to_s3
from covise_app.project_details import PROJECT_DETAILS
try:
    import resend
except ImportError:
    resend = None

logger = logging.getLogger(__name__)
RESEND_API_KEY = settings.RESEND_API
WAITLIST_FAILURE_ALERT_EMAIL = getattr(settings, "WAITLIST_FAILURE_ALERT_EMAIL", "ellabouhawel@gmail.com")
url_validator = URLValidator(schemes=["http", "https"])


def _normalize_email(value):
    return str(value or "").strip().lower()


def _generate_verification_code():
    return f"{random.randint(0, 999999):06d}"


def _integrity_error_text(exc):
    parts = [str(exc)]
    if getattr(exc, "__cause__", None):
        parts.append(str(exc.__cause__))
    if getattr(exc, "__context__", None):
        parts.append(str(exc.__context__))
    return " ".join(part for part in parts if part).lower()


def _log_waitlist_submission_failure(email, reason, *, verified_already, cv_uploaded, cv_s3_key="", extra=None):
    details = {
        "email": email,
        "reason": reason,
        "verified_already": verified_already,
        "cv_uploaded": cv_uploaded,
    }
    if cv_s3_key:
        details["cv_s3_key"] = cv_s3_key
    if extra:
        details.update(extra)
    logger.warning("Waitlist submission incomplete: %s", details)
    if reason in {"referral_code_collision", "unexpected_integrity_error", "operational_error"}:
        _send_waitlist_failure_alert(email, reason, details)


def _send_waitlist_failure_alert(user_email, reason, details):
    if resend is None or not RESEND_API_KEY or not WAITLIST_FAILURE_ALERT_EMAIL:
        logger.warning(
            "Skipped waitlist failure alert for %s because email alerts are not configured.",
            user_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [WAITLIST_FAILURE_ALERT_EMAIL],
        "subject": f"ERROR: waitlist submission failed after email verification for {user_email}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">Error after email verification</h1>'
            f'<p style="margin: 0 0 10px;"><strong>User email:</strong> {user_email}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Date:</strong> {timestamp}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Reason:</strong> {reason}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Details:</strong> {json.dumps(details, default=str)}</p>'
            '</div>'
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send waitlist failure alert email for %s", user_email)


def _send_waitlist_abandonment_alert(user_email):
    if resend is None or not RESEND_API_KEY or not WAITLIST_FAILURE_ALERT_EMAIL:
        logger.warning(
            "Skipped waitlist abandonment alert for %s because email alerts are not configured.",
            user_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [WAITLIST_FAILURE_ALERT_EMAIL],
        "subject": f"WITHDRAWN: user verified email but left before full waitlist submission for {user_email}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">User withdrew after email verification</h1>'
            f'<p style="margin: 0 0 10px;"><strong>User email:</strong> {user_email}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Date:</strong> {timestamp}</p>'
            '<p style="margin: 0;">The user completed email verification but left the waitlist flow before submitting the full form.</p>'
            '</div>'
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send waitlist abandonment alert email for %s", user_email)


def _send_private_profile_failure_alert(user_email, reason, details):
    if resend is None or not RESEND_API_KEY or not WAITLIST_FAILURE_ALERT_EMAIL:
        logger.warning(
            "Skipped private profile failure alert for %s because email alerts are not configured.",
            user_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [WAITLIST_FAILURE_ALERT_EMAIL],
        "subject": f"ERROR: private profile submission failed for {user_email}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">Private profile submission failed</h1>'
            f'<p style="margin: 0 0 10px;"><strong>User email:</strong> {user_email}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Date:</strong> {timestamp}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Reason:</strong> {reason}</p>'
            f'<p style="margin: 0 0 10px;"><strong>Details:</strong> {json.dumps(details, default=str)}</p>'
            '</div>'
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send private profile failure alert email for %s", user_email)


def _send_waitlist_verification_email(email_verification):
    if resend is None:
        raise RuntimeError("resend is not installed.")
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API is not configured.")

    resend.api_key = RESEND_API_KEY
    payload = {
        "from": "CoVise <founders@covise.net>",
        "to": [email_verification.email],
        "subject": "Verify your email for the CoVise waitlist",
        "html":  (
    '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 24px; color: #e2e8f0; background: #0f1117; border-radius: 12px;">'
    # Logo / Brand header
    '<div style="text-align: center; margin-bottom: 32px;">'
    '<img src="https://logo-im-g.s3.eu-central-1.amazonaws.com/covise_logo.png " alt="CoVise" style="height: 40px; margin-bottom: 8px;">'
    '<h1 style="font-size: 28px; font-weight: 700; color: #ffffff; margin: 0;">CoVise</h1>'
    '<p style="font-size: 13px; color: #64748b; margin: 4px 0 0; letter-spacing: 0.05em;">THE FOUNDERS COMMUNITY</p>'
    '</div>'
    
    '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 28px;">'
    
    # Body
    f'<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 8px;">Hey, this is the CoVise Team,</p>'
    '<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 20px;">We\'re excited to have you on board!</p>'
    '<p style="font-size: 15px; color: #94a3b8; margin: 0 0 8px;">You\'re one step away from reserving your spot in the CoVise community.</p>'
    '<p style="font-size: 15px; color: #94a3b8; margin: 0 0 24px;">Enter this 6-digit verification code in the waitlist form to complete your application:</p>'
    
    # Code block
    '<div style="text-align: center; background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.15); border-radius: 10px; padding: 24px; margin: 0 0 28px;">'
    '<p style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 10px;">Verification Code</p>'
    f'<p style="font-size: 32px; font-weight: 700; letter-spacing: 0.3em; color: #ffffff; margin: 0;">{email_verification.verification_code}</p>'
    '</div>'
    
    '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 20px;">'
    
    # Footer
    '<p style="font-size: 13px; color: #cbd5e1; margin: 0;">— The CoVise Team</p>'
    '<p style="font-size: 12px; color: #cbd5e1; margin: 12px 0 0;">If you didn\'t request this, you can safely ignore this email.</p>'
    
    '</div>'),
    }
    result = resend.Emails.send(payload)




def _load_boarding_flow():
    flow_path = Path(__file__).resolve().parent / "boarding.json"
    try:
        # Use utf-8-sig so a BOM in boarding.json does not break JSON parsing.
        with flow_path.open(encoding="utf-8-sig") as f:
            flow = json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.exception("Failed to load boarding.json: %s", exc)
        return None, "We are having trouble loading onboarding right now. Please try another time."

    if not isinstance(flow, dict) or not isinstance(flow.get("steps"), list):
        logger.error("Invalid boarding.json structure")
        return None, "We are having trouble loading onboarding right now. Please try another time."

    return flow, None

# Create your views here.
def landing(request):
    return render(request, 'landing.html')

def home(request):
    return render(request, 'home.html')

def messages(request):
    return render(request, 'messages.html')

def projects(request):
    return render(request, 'project.html')


def project_detail(request, project_slug):
    project = PROJECT_DETAILS.get(project_slug)
    if not project:
        raise Http404("Project not found")

    score = project.get("alignment_score", 0)
    if score >= 85:
        alignment_band = "high"
    elif score >= 70:
        alignment_band = "medium"
    else:
        alignment_band = "low"

    context = {
        "project": project,
        "alignment_band": alignment_band,
    }
    return render(request, "project_detail.html", context)

def profile(request):
    return render(request, 'profile.html')

def profile_card(request):
    return render(request, 'profile_card.html')


@ensure_csrf_cookie
def private_profile_completion(request):
    success_email = request.session.pop("private_profile_completion_success_email", "")
    context = {
        "error_message": "",
        "submitted": bool(success_email),
        "success_email": success_email,
        "form_values": {
            "email": "",
            "full_name": "",
            "linkedin_url": "",
            "venture_summary": "",
        },
    }

    if request.method == "POST":
        email = _normalize_email(request.POST.get("email"))
        full_name = request.POST.get("full_name", "").strip()
        linkedin_url = request.POST.get("linkedin_url", "").strip()
        venture_summary = request.POST.get("venture_summary", "").strip()

        context["form_values"] = {
            "email": email,
            "full_name": full_name,
            "linkedin_url": linkedin_url,
            "venture_summary": venture_summary,
        }

        if not email or not full_name or not linkedin_url or not venture_summary:
            context["error_message"] = "Please complete all fields before submitting."
            return render(request, "private_profile_completion.html", context)

        try:
            validate_email(email)
            url_validator(linkedin_url)
        except ValidationError:
            context["error_message"] = "Please enter a valid email and LinkedIn URL."
            return render(request, "private_profile_completion.html", context)

        submission = None
        for attempt in range(2):
            try:
                submission = PrivateProfileCompletion.objects.create(
                    email=email,
                    full_name=full_name,
                    linkedin_url=linkedin_url,
                    venture_summary=venture_summary[:150],
                )
                break
            except IntegrityError as exc:
                error_text = _integrity_error_text(exc)
                if "email" in error_text and PrivateProfileCompletion.objects.filter(email=email).exists():
                    context["error_message"] = "This email has already submitted this form."
                    return render(request, "private_profile_completion.html", context)

                logger.exception("Unexpected integrity error while creating private profile submission for %s", email)
                _send_private_profile_failure_alert(
                    email,
                    "unexpected_integrity_error",
                    {"attempt": attempt + 1, "error": str(exc)},
                )
                context["error_message"] = "Temporary submission issue. Please try again in a moment."
                return render(request, "private_profile_completion.html", context)
            except OperationalError as exc:
                close_old_connections()
                logger.warning(
                    "OperationalError while creating private profile submission for %s on attempt %s: %s",
                    email,
                    attempt + 1,
                    exc,
                )
                if attempt == 1:
                    _send_private_profile_failure_alert(
                        email,
                        "operational_error",
                        {"attempts": attempt + 1, "error": str(exc)},
                    )
                    context["error_message"] = "Temporary database issue. Please try again in a moment."
                    return render(request, "private_profile_completion.html", context)

        if submission is None:
            _send_private_profile_failure_alert(
                email,
                "unknown_submission_failure",
                {"message": "Submission object was not created and no explicit exception path returned."},
            )
            context["error_message"] = "Temporary submission issue. Please try again in a moment."
            return render(request, "private_profile_completion.html", context)

        request.session["private_profile_completion_success_email"] = submission.email
        return redirect("Private Profile Completion")

    return render(request, "private_profile_completion.html", context)

def map_view(request):
    return render(request, 'map.html')

def chatbot(request):
    return render(request, 'chatbot.html')

def settings(request):
    return render(request, 'settings.html')

def terms(request):
    return render(request, 'terms.html')

def privacy(request):
    return render(request, 'privacy.html')

def security(request):
    return render(request, 'security.html')

def login_view(request):
    return render(request, 'login.html')

def signin(request):
    return render(request, 'signin.html')

def onboarding_final(request):
    return render(request, 'onboarding-final.html')


@ensure_csrf_cookie
def onboarding(request):
    flow, onboarding_error_message = _load_boarding_flow()
    onboarding_unavailable = flow is None
    initial_answers = {}
    if request.session.get("waitlist_email"):
        initial_answers["email"] = request.session["waitlist_email"]
    return render(
        request,
        'onboarding.html',
        {
            'boarding_flow': flow,
            'onboarding_initial_answers': initial_answers,
            'onboarding_unavailable': onboarding_unavailable,
            'onboarding_error_message': onboarding_error_message,
        },
    )


def onboarding_submit(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return JsonResponse({"error": "answers must be an object."}, status=400)

    flow_name = str(payload.get("flow_name", "")).strip()
    email = str(answers.get("email", "")).strip() or str(request.session.get("waitlist_email", "")).strip()
    if not email:
        return JsonResponse({"error": "Email is required to save onboarding."}, status=400)

    waitlist_id = request.session.get("waitlist_entry_id")
    waitlist_entry = WaitlistEntry.objects.filter(pk=waitlist_id).first() if waitlist_id else None
    if waitlist_entry is None:
        return JsonResponse(
            {"error": "Waitlist session expired or missing. Please restart from the waitlist form."},
            status=400,
        )

    onboarding_field_ids = [
        "user_type",
        "industry",
        "stage",
        "target_market",
        "team_size",
        "one_liner",
        "cofounders_needed",
        "looking_for_type",
        "founder_timeline",
        "current_role",
        "years_experience",
        "industries_interested",
        "venture_stage_preference",
        "founder_type_preference",
        "specialist_timeline",
        "investor_type",
        "investment_geography",
        "ticket_size",
        "investment_stage",
        "investment_industries",
        "investor_value_add",
        "investor_looking_for",
        "investor_timeline",
        "home_country",
        "target_gcc_market",
        "foreign_industry",
        "foreign_stage",
        "foreign_one_liner",
        "local_partner_need",
        "foreign_timeline",
        "program_type",
        "program_location",
        "program_stage_focus",
        "program_industries",
        "cohort_size",
        "program_offering",
        "incubator_looking_for",
        "incubator_timeline",
        "skills",
        "availability",
        "capital_contribution",
        "looking_for_skills",
        "cofounder_commitment",
        "compensation",
        "cofounder_location_pref",
        "monthly_revenue",
        "funding_status",
        "customer_count",
        "commitment_level",
        "risk_tolerance",
        "execution_history",
        "leadership_style",
        "how_heard",
        "referral_code",
        "profile_visibility_consent",
    ]
    onboarding_defaults = {field_id: answers.get(field_id) for field_id in onboarding_field_ids}

    # Link referral if user entered a valid code
    entered_code = str(answers.get("referral_code", "")).strip().upper()
    if entered_code:
        referrer = WaitlistEntry.objects.filter(my_referral_code=entered_code).exclude(pk=waitlist_entry.pk).first()
        if referrer and not waitlist_entry.referred_by_id:
            waitlist_entry.referred_by = referrer
            waitlist_entry.save(update_fields=["referred_by"])

    OnboardingResponse.objects.update_or_create(
        waitlist_entry=waitlist_entry,
        defaults={
            "email": waitlist_entry.email or email,
            "flow_name": flow_name[:200],
            **onboarding_defaults,
            "answers": answers,
        },
    )

    return JsonResponse({"ok": True})

def loading(request):
    return render(request, 'loading.html')

def pricing(request):
    return render(request, 'pricing.html')

def features(request):
    return render(request, 'features.html')

def about(request):
    return render(request, 'about.html')

def workspace(request):
    return render(request, 'workspace.html')

@ensure_csrf_cookie
def waitlist_verify_email_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    email = _normalize_email(payload.get("email"))
    if not email:
        return JsonResponse({"error": "Email is required."}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Please enter a valid email address."}, status=400)
    
    # if the email is already on the waitlist:
    if WaitlistEntry.objects.filter(email=email).exists():
        return JsonResponse({"error": "This email is already registered on CoVise."}, status=400)

    existing_verification = WaitlistEmailVerification.objects.filter(
        email=email,
        verified_at__isnull=False,
    ).first()
    if existing_verification: #If the email was verified before:
        request.session["verified_waitlist_email"] = email
        return JsonResponse(
            {
                "ok": True,
                "already_verified": True,
                "message": "Email verified. You can submit now.",
            }
        )
    email_verification = WaitlistEmailVerification.objects.filter(email=email).first()

    #If the email is not verified and new to both WaitlistEmailVerification and WaitlistEntry:
    if email_verification is None:
        email_verification = WaitlistEmailVerification.objects.create(
            email=email,
            token=uuid.uuid4(),
            verification_code=_generate_verification_code(),
        )
    #If the email is not verified and already has a WaitlistEmailVerification record (e.g. from a previous verification attempt), generate a new code and token:
    elif not email_verification.verification_code:
        email_verification.token = uuid.uuid4()
        email_verification.verification_code = _generate_verification_code()
        email_verification.verified_at = None
        email_verification.save(update_fields=["token", "verification_code", "verified_at", "updated_at"])

    try:
        _send_waitlist_verification_email(email_verification)
    except Exception as exc:
        logger.exception("Failed to send verification email for %s: %s", email, exc)
        return JsonResponse(
            {"error": "Failed to send verification email. Please try again in a moment."},
            status=500,
        )

    return JsonResponse(
        {
            "ok": True,
            "message": "A verification code was sent to your email. Enter it below before submitting.",
        }
    )


@ensure_csrf_cookie
def waitlist_verify_email_code(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    email = _normalize_email(payload.get("email"))
    code = str(payload.get("code", "")).strip()
    if not email or not code:
        return JsonResponse({"error": "Email and verification code are required."}, status=400)

    email_verification = WaitlistEmailVerification.objects.filter(email=email).first()
    if email_verification is None:
        return JsonResponse({"error": "Please request a verification code first."}, status=400)

    if email_verification.verified_at is not None:
        request.session["verified_waitlist_email"] = email
        request.session["waitlist_verification_notice"] = "Email verified. You can submit now."
        return JsonResponse({"ok": True, "message": "Email verified. You can submit now."})

    if email_verification.verification_code != code:
        return JsonResponse({"error": "Incorrect verification code. Please try again."}, status=400)

    email_verification.verified_at = timezone.now()
    email_verification.save(update_fields=["verified_at", "updated_at"])
    request.session["verified_waitlist_email"] = email
    request.session["waitlist_verification_notice"] = "Email verified. You can submit now."
    return JsonResponse({"ok": True, "message": "Email verified. You can submit now."})


@ensure_csrf_cookie
def waitlist_verified_email_abandoned(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    email = _normalize_email(request.POST.get("email"))
    if not email and request.body:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        email = _normalize_email(payload.get("email"))

    if not email:
        return JsonResponse({"ok": False, "error": "Email is required."}, status=400)

    if WaitlistEntry.objects.filter(email=email).exists():
        return JsonResponse({"ok": True, "skipped": "entry_exists"})

    verification = WaitlistEmailVerification.objects.filter(
        email=email,
        verified_at__isnull=False,
    ).first()
    if verification is None:
        return JsonResponse({"ok": True, "skipped": "not_verified"})

    if request.session.get("waitlist_abandon_alerted_email") == email:
        return JsonResponse({"ok": True, "skipped": "already_alerted"})

    request.session["waitlist_abandon_alerted_email"] = email
    _send_waitlist_abandonment_alert(email)
    return JsonResponse({"ok": True})


@ensure_csrf_cookie
def waitlist(request):
    context = {
        "initial_waitlist_email": request.session.pop(
            "waitlist_initial_email",
            request.session.get("verified_waitlist_email", ""),
        ),
        "initial_full_name": request.session.pop("waitlist_full_name", ""),
        "initial_phone_number": request.session.pop("waitlist_phone_number", ""),
        "initial_email_verification_code": request.session.pop("waitlist_email_verification_code", ""),
        "initial_verified_email": request.session.get("verified_waitlist_email", ""),
        "initial_verification_notice": request.session.pop("waitlist_verification_notice", ""),
        "initial_verification_pending_email": request.session.pop("waitlist_pending_email", ""),
        "initial_country": request.session.pop("waitlist_country", ""),
        "initial_non_gcc_business": request.session.pop("waitlist_non_gcc_business", False),
        "initial_custom_country": request.session.pop("waitlist_custom_country", ""),
        "initial_description": request.session.pop("waitlist_description", ""),
        "initial_custom_description": request.session.pop("waitlist_custom_description", ""),
        "initial_linkedin": request.session.pop("waitlist_linkedin", ""),
        "initial_no_linkedin": request.session.pop("waitlist_no_linkedin", False),
        "initial_venture_summary": request.session.pop("waitlist_venture_summary", ""),
        "initial_referral_code": request.session.pop("waitlist_referral_code", ""),
        "error_message": request.session.pop("waitlist_error_message", ""),
        "show_second_step": request.session.pop("waitlist_show_second_step", False),
    }

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = _normalize_email(request.POST.get('email'))
        email_verification_code = ''.join(ch for ch in str(request.POST.get('email_verification_code', '')) if ch.isdigit())[:6]
        country = request.POST.get('country', '').strip()
        description = request.POST.get('description', '').strip()
        custom_description = request.POST.get('custom_description', '').strip()
        entered_referral_code = request.POST.get('referral_code', '').strip().upper()
        non_gcc_business = request.POST.get('non_gcc_business') == 'on'
        no_linkedin = request.POST.get('no_linkedin') == 'on'
        custom_country = request.POST.get('custom_country', '').strip()
        linkedin = request.POST.get('linkedin', '').strip()
        venture_summary = request.POST.get('venture_summary', '').strip()
        cv_file = request.FILES.get('cv')

        def redirect_with_error(message, *, pending_email='', show_second_step=None):
            request.session["waitlist_error_message"] = message
            request.session["waitlist_full_name"] = full_name
            request.session["waitlist_phone_number"] = phone_number
            request.session["waitlist_initial_email"] = email
            request.session["waitlist_email_verification_code"] = email_verification_code
            request.session["waitlist_pending_email"] = pending_email
            request.session["waitlist_country"] = country
            request.session["waitlist_non_gcc_business"] = non_gcc_business
            request.session["waitlist_custom_country"] = custom_country
            request.session["waitlist_description"] = description
            request.session["waitlist_custom_description"] = custom_description
            request.session["waitlist_linkedin"] = linkedin
            request.session["waitlist_no_linkedin"] = no_linkedin
            request.session["waitlist_venture_summary"] = venture_summary
            request.session["waitlist_referral_code"] = entered_referral_code
            if show_second_step is None:
                show_second_step = any([
                    country,
                    custom_country,
                    description,
                    custom_description,
                    linkedin,
                    venture_summary,
                    entered_referral_code,
                    non_gcc_business,
                    no_linkedin,
                ])
            request.session["waitlist_show_second_step"] = show_second_step
            return redirect('Waitlist')

        linkedin_missing_when_required = (not no_linkedin) and (not linkedin)
        cv_missing_when_required = no_linkedin and (not cv_file)

        is_email_verified = WaitlistEmailVerification.objects.filter(
            email=email,
            verified_at__isnull=False,
        ).exists()

        if not all([full_name, phone_number, email]) or linkedin_missing_when_required or cv_missing_when_required:
            return redirect_with_error('Please complete all required fields.')
        elif non_gcc_business and not custom_country:
            return redirect_with_error('Please enter your country if you are outside the GCC.')
        elif not description:
            return redirect_with_error('Please select what best describes you.')
        elif description == 'other' and not custom_description:
            return redirect_with_error('Please tell us more if you selected Other.')
        elif entered_referral_code and not WaitlistEntry.objects.filter(my_referral_code=entered_referral_code).exists():
            return redirect_with_error('This referral code is not valid.')
        elif not is_email_verified and not email_verification_code:
            return redirect_with_error('Enter the verification code sent to your email.', pending_email=email)
        elif not is_email_verified:
            email_verification = WaitlistEmailVerification.objects.filter(email=email).first()
            if email_verification is None:
                return redirect_with_error('Please verify your email before submitting.', pending_email=email)
            if email_verification.verification_code != email_verification_code:
                return redirect_with_error('Incorrect verification code. Please try again.', pending_email=email)
            email_verification.verified_at = timezone.now()
            email_verification.save(update_fields=["verified_at", "updated_at"])
            request.session["verified_waitlist_email"] = email
            is_email_verified = True

        if is_email_verified and not non_gcc_business and not country:
            return redirect_with_error('Please select your country.')
        if is_email_verified:
            if non_gcc_business:
                country = ''
            else:
                custom_country = ''

            if description != 'other':
                custom_description = ''

            if WaitlistEntry.objects.filter(email=email).exists():
                return redirect_with_error('This email is already registered on CoVise.')

            # Upload CV before DB retry loop — file object is exhausted after first read
            cv_s3_key = None
            if cv_file:
                cv_s3_key = upload_cv_to_s3(cv_file, email)
                if cv_s3_key is None:
                    logger.warning("[waitlist] S3 upload failed for %s", email)

            referred_by = None
            if entered_referral_code:
                referred_by = WaitlistEntry.objects.filter(my_referral_code=entered_referral_code).first()



            entry = None
            for attempt in range(2):
                generated_referral_code = generate_referral_code()
                try:
                    entry = WaitlistEntry.objects.create(
                        full_name=full_name,
                        phone_number=phone_number,
                        email=email,
                        country=country,
                        non_gcc_business=non_gcc_business,
                        custom_country=custom_country,
                        description=description,
                        custom_description=custom_description,
                        linkedin=linkedin,
                        no_linkedin=no_linkedin,
                        venture_summary=venture_summary,
                        referral_code=entered_referral_code,
                        referred_by=referred_by,
                        cv_s3_key=cv_s3_key,
                        my_referral_code=generated_referral_code,
                    )
                    break
                except IntegrityError as exc:
                    error_text = _integrity_error_text(exc)

                    if (
                        "email" in error_text
                        and WaitlistEntry.objects.filter(email=email).exists()
                    ):
                        _log_waitlist_submission_failure(
                            email,
                            "duplicate_email",
                            verified_already=is_email_verified,
                            cv_uploaded=bool(cv_s3_key),
                            cv_s3_key=cv_s3_key or "",
                            extra={"attempt": attempt + 1},
                        )
                        return redirect_with_error('This email is already registered on CoVise.')

                    if "my_referral_code" in error_text:
                        logger.warning(
                            "Referral code collision while creating waitlist entry for %s on attempt %s",
                            email,
                            attempt + 1,
                        )
                        if attempt == 1:
                            _log_waitlist_submission_failure(
                                email,
                                "referral_code_collision",
                                verified_already=is_email_verified,
                                cv_uploaded=bool(cv_s3_key),
                                cv_s3_key=cv_s3_key or "",
                                extra={"attempts": attempt + 1},
                            )
                            return redirect_with_error('Temporary database issue. Please try again in a moment.')
                        continue

                    logger.exception("Unexpected integrity error while creating waitlist entry for %s", email)
                    _log_waitlist_submission_failure(
                        email,
                        "unexpected_integrity_error",
                        verified_already=is_email_verified,
                        cv_uploaded=bool(cv_s3_key),
                        cv_s3_key=cv_s3_key or "",
                        extra={"attempt": attempt + 1, "error": str(exc)},
                    )
                    return redirect_with_error('Temporary database issue. Please try again in a moment.')
                except OperationalError as exc:
                    # Handle transient DB disconnects (e.g., SSL EOF) by refreshing the connection once.
                    close_old_connections()
                    logger.warning(
                        "OperationalError while creating waitlist entry for %s on attempt %s: %s",
                        email,
                        attempt + 1,
                        exc,
                    )
                    if attempt == 1:
                        logger.exception("Failed to create waitlist entry after retry for %s", email)
                        _log_waitlist_submission_failure(
                            email,
                            "operational_error",
                            verified_already=is_email_verified,
                            cv_uploaded=bool(cv_s3_key),
                            cv_s3_key=cv_s3_key or "",
                            extra={"attempts": attempt + 1, "error": str(exc)},
                        )
                        return redirect_with_error('Temporary database issue. Please try again in a moment.')

            request.session["waitlist_email"] = email
            request.session["waitlist_entry_id"] = entry.id
            request.session["my_referral_code"] = entry.my_referral_code
            request.session.pop("waitlist_abandon_alerted_email", None)
            return redirect('Waitlist Success')

    return render(request, 'waitlist.html', context)


def waitlist_success(request):
    if not request.session.get("waitlist_entry_id"):
        return redirect('Waitlist')

    return render(request, 'waitlist_success.html', {
        'my_referral_code': request.session.get('my_referral_code', ''),
    })


def csrf_failure(request, reason=""):
    context = {"reason": reason}
    return render(request, "csrf_error.html", context, status=403)
