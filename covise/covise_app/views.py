import json
import logging
from pathlib import Path
from django.http import JsonResponse
from django.db import OperationalError, close_old_connections
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import OnboardingResponse, WaitlistEntry

logger = logging.getLogger(__name__)



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

def profile(request):
    return render(request, 'profile.html')

def profile_card(request):
    return render(request, 'profile_card.html')

def map_view(request):
    return render(request, 'map.html')

def chatbot(request):
    return render(request, 'chatbot.html')

def settings(request):
    return render(request, 'settings.html')

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

    waitlist_entry = None
    waitlist_id = request.session.get("waitlist_entry_id")
    if waitlist_id:
        waitlist_entry = WaitlistEntry.objects.filter(pk=waitlist_id).first()
    if waitlist_entry is None:
        waitlist_entry = WaitlistEntry.objects.filter(email=email).order_by("-created_at").first()

    OnboardingResponse.objects.update_or_create(
        email=email,
        defaults={
            "waitlist_entry": waitlist_entry,
            "flow_name": flow_name[:200],
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
def waitlist(request):
    context = {}

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        country = request.POST.get('country', '').strip()
        non_gcc_business = request.POST.get('non_gcc_business') == 'on'
        no_linkedin = request.POST.get('no_linkedin') == 'on'
        custom_country = request.POST.get('custom_country', '').strip()
        linkedin = request.POST.get('linkedin', '').strip()
        cv_file = request.FILES.get('cv')

        linkedin_missing_when_required = (not no_linkedin) and (not linkedin)
        cv_missing_when_required = no_linkedin and (not cv_file)

        if not all([full_name, phone_number, email]) or linkedin_missing_when_required or cv_missing_when_required:
            context['error_message'] = 'Please complete all required fields.'
        elif non_gcc_business and not custom_country:
            context['error_message'] = 'Please enter your country if you are outside the GCC.'
        elif not non_gcc_business and not country:
            context['error_message'] = 'Please select your country.'
        else:
            if non_gcc_business:
                country = ''
            else:
                custom_country = ''

            entry = None
            for attempt in range(2):
                try:
                    entry = WaitlistEntry.objects.create(
                        full_name=full_name,
                        phone_number=phone_number,
                        email=email,
                        country=country,
                        non_gcc_business=non_gcc_business,
                        custom_country=custom_country,
                        linkedin=linkedin,
                        cv=cv_file,
                    )
                    break
                except OperationalError:
                    # Handle transient DB disconnects (e.g., SSL EOF) by refreshing the connection once.
                    close_old_connections()
                    if attempt == 1:
                        logger.exception("Failed to create waitlist entry after retry for %s", email)
                        context['error_message'] = 'Temporary database issue. Please try again in a moment.'

            if entry is None:
                return render(request, 'waitlist.html', context)
            request.session["waitlist_email"] = email
            request.session["waitlist_entry_id"] = entry.id
            return redirect('Onboarding')

    return render(request, 'waitlist.html', context)


def waitlist_success(request):
    return render(request, 'waitlist_success.html')


def csrf_failure(request, reason=""):
    context = {"reason": reason}
    return render(request, "csrf_error.html", context, status=403)
