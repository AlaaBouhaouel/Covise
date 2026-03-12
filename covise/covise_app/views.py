import json
import logging
from pathlib import Path
from django.http import Http404, JsonResponse
from django.db import OperationalError, close_old_connections
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import OnboardingResponse, WaitlistEntry

logger = logging.getLogger(__name__)

PROJECT_DETAILS = {
    "cv-6631": {
        "slug": "cv-6631",
        "code": "CV-6631",
        "title": "B2B Marketplace for Construction Materials",
        "tagline": "Digital procurement rail for mid-size contractors with transparent pricing and delivery SLAs.",
        "alignment_score": 91,
        "city": "Riyadh",
        "country": "Saudi Arabia",
        "sector": "Construction Tech / B2B Commerce",
        "stage": "Supplier relationships established",
        "founder_commitment": "Full-Time",
        "capital_status": "Bootstrapped",
        "target_raise": "SAR 1.8M pre-seed",
        "runway": "11 months",
        "positions_needed": [
            "Technical Co-Founder (Marketplace Architecture)",
            "Founding Product Manager",
        ],
        "skills_needed": [
            "B2B ordering workflows",
            "Supplier pricing engines",
            "ERP integrations",
            "Dispatch optimization",
        ],
        "overview": "The venture is building a vertical marketplace connecting contractors with vetted material suppliers. The MVP handles RFQs, quote comparisons, payment reconciliation, and delivery tracking for bulk orders.",
        "problem_points": [
            "Procurement decisions still happen via fragmented WhatsApp threads and phone calls.",
            "Contractors face non-transparent pricing and frequent delivery uncertainty.",
            "Supplier discovery for non-core categories remains relationship-driven, not data-driven.",
        ],
        "solution_points": [
            "Standardized RFQ intake with side-by-side quote normalization.",
            "Supplier reliability score based on on-time delivery and quality dispute ratio.",
            "Order timeline tracking with milestone alerts to procurement leads.",
        ],
        "market_assumptions": [
            {"label": "Initial SAM (Central + Eastern KSA)", "value": "SAR 2.4B annual addressed volume"},
            {"label": "Take rate target (Year 2)", "value": "3.1% blended"},
            {"label": "Target contractor accounts (18 months)", "value": "220 active accounts"},
        ],
        "unit_economics": [
            {"metric": "Average order value", "value": "SAR 38,500", "note": "Weighted across cement, steel, finishing"},
            {"metric": "Gross contribution/order", "value": "SAR 1,170", "note": "After payment and logistics fees"},
            {"metric": "Payback period", "value": "3.4 months", "note": "On paid channel cohorts"},
        ],
        "go_to_market": [
            "Founder-led sales to 30 anchor contractors with recurring monthly procurement needs.",
            "Supplier onboarding incentives tied to first 90-day fulfillment quality.",
            "Partnership pipeline with quantity surveyor networks for warm project-intent signals.",
        ],
        "milestones": [
            {"name": "Pilot with 12 contractors", "status": "Completed", "date": "2026-01"},
            {"name": "Supplier scoring engine v1", "status": "In Progress", "date": "2026-04"},
            {"name": "Escrow and milestone payments", "status": "Planned", "date": "2026-06"},
        ],
        "risk_register": [
            {"risk": "Supplier churn during first 2 quarters", "mitigation": "Dual-sourcing per category + SLA rebates", "owner": "Operations"},
            {"risk": "Price parity disputes with offline channels", "mitigation": "Transparent fee model and preferred-volume tiers", "owner": "Commercial"},
            {"risk": "High-touch support load at launch", "mitigation": "Assisted onboarding playbook and in-app guided RFQ", "owner": "Product"},
        ],
        "diligence_docs": [
            "Pilot cohort order logs (anonymized)",
            "Supplier contracts and SLA schedule",
            "Procurement workflow map and support SOP",
            "Financial model v3.2 with sensitivity scenarios",
        ],
    },
    "cv-7784": {
        "slug": "cv-7784",
        "code": "CV-7784",
        "title": "Women-Only Fitness Studio (Riyadh)",
        "tagline": "Premium neighborhood studio with small-group programming and measurable retention loops.",
        "alignment_score": 87,
        "city": "Riyadh",
        "country": "Saudi Arabia",
        "sector": "Fitness / Consumer Services",
        "stage": "Location shortlisted",
        "founder_commitment": "Full-Time",
        "capital_status": "SAR 250,000 committed",
        "target_raise": "SAR 900,000 seed extension",
        "runway": "14 months",
        "positions_needed": [
            "Business & Operations Partner",
            "Head Coach (Founding Team)",
        ],
        "skills_needed": [
            "Membership analytics",
            "Studio operations",
            "Scheduling systems",
            "Community growth",
        ],
        "overview": "The studio is positioned around evidence-backed training cycles for women in professional age groups. The model combines coach-led classes, onboarding assessments, and retention-focused member journeys.",
        "problem_points": [
            "Overcrowded gyms with inconsistent coaching quality reduce retention.",
            "Generic programming fails to adapt to member goals and schedules.",
            "Member communication is fragmented across social channels and paper schedules.",
        ],
        "solution_points": [
            "Capacity-capped classes with coach-to-member ratio standards.",
            "Goal-based progression tracks with monthly assessment checkpoints.",
            "Centralized app for booking, reminders, and class feedback loops.",
        ],
        "market_assumptions": [
            {"label": "Addressable member base (3km radius)", "value": "11,500 potential members"},
            {"label": "Target occupancy (month 12)", "value": "74% average class fill"},
            {"label": "Projected monthly recurring revenue", "value": "SAR 210,000"},
        ],
        "unit_economics": [
            {"metric": "Average membership ticket", "value": "SAR 690/month", "note": "Blended plan portfolio"},
            {"metric": "Gross margin", "value": "58%", "note": "Post coach payroll and facility costs"},
            {"metric": "Retention at month 6 target", "value": "67%", "note": "Cohort target"},
        ],
        "go_to_market": [
            "Pre-opening waitlist with founder-led community sessions.",
            "Referral ladder with in-club rewards and class credits.",
            "Partnerships with local wellness brands for co-marketing campaigns.",
        ],
        "milestones": [
            {"name": "Lease negotiation and fit-out BOQ", "status": "In Progress", "date": "2026-03"},
            {"name": "Core trainer hiring (4 roles)", "status": "Planned", "date": "2026-05"},
            {"name": "Soft launch with 120 members", "status": "Planned", "date": "2026-07"},
        ],
        "risk_register": [
            {"risk": "Slower-than-expected member conversion", "mitigation": "Free assessment funnel + onboarding calls", "owner": "Growth"},
            {"risk": "Coach attrition in first year", "mitigation": "Comp band review and upskilling pathway", "owner": "People Ops"},
            {"risk": "Peak-hour capacity bottlenecks", "mitigation": "Dynamic timetable and demand-based class additions", "owner": "Operations"},
        ],
        "diligence_docs": [
            "Location shortlist scorecard",
            "Member persona interviews (n=42)",
            "Pricing elasticity analysis",
            "P&L model with conservative/base/aggressive cases",
        ],
    },
    "cv-8093": {
        "slug": "cv-8093",
        "code": "CV-8093",
        "title": "Digital Tender Platform for Contractors",
        "tagline": "Tender lifecycle software for mid-market construction firms with compliance-first workflows.",
        "alignment_score": 90,
        "city": "Dammam",
        "country": "Saudi Arabia",
        "sector": "SaaS / Construction Procurement",
        "stage": "Industry validation complete",
        "founder_commitment": "Full-Time",
        "capital_status": "SAR 100,000 committed",
        "target_raise": "SAR 2.3M pre-seed",
        "runway": "9 months",
        "positions_needed": [
            "Full-Stack Technical Co-Founder",
            "Implementation Lead",
        ],
        "skills_needed": [
            "Workflow engines",
            "Document parsing",
            "Role-based permissions",
            "B2B SaaS onboarding",
        ],
        "overview": "The platform digitizes tender intake, document distribution, vendor communication, and scoring workflows. Focus is on reducing cycle time while creating auditable decision trails.",
        "problem_points": [
            "Tender packets are manually distributed and version control is error-prone.",
            "Decision logs are hard to audit, increasing compliance exposure.",
            "Vendor clarification loops delay bid closure.",
        ],
        "solution_points": [
            "Centralized tender workspace with role-scoped access and version history.",
            "Structured scoring templates with committee-level accountability.",
            "Vendor Q&A module with SLA timers and escalation paths.",
        ],
        "market_assumptions": [
            {"label": "Initial ICP companies", "value": "420 regional contractors"},
            {"label": "Target ACV", "value": "SAR 74,000"},
            {"label": "12-month contracted ARR target", "value": "SAR 1.9M"},
        ],
        "unit_economics": [
            {"metric": "Implementation cycle", "value": "4-6 weeks", "note": "Includes process mapping"},
            {"metric": "Gross margin target", "value": "76%", "note": "At 25+ active accounts"},
            {"metric": "Net revenue retention target", "value": "112%", "note": "Through seat expansion"},
        ],
        "go_to_market": [
            "Direct founder pipeline through procurement and PMO heads.",
            "Proof-of-value pilots for one tender cycle before annual contract.",
            "Implementation templates by vertical (civil, MEP, fit-out).",
        ],
        "milestones": [
            {"name": "MVP workflow engine", "status": "Completed", "date": "2025-12"},
            {"name": "First paid pilot conversion", "status": "In Progress", "date": "2026-04"},
            {"name": "ISO-aligned audit trail module", "status": "Planned", "date": "2026-07"},
        ],
        "risk_register": [
            {"risk": "Long enterprise sales cycles", "mitigation": "Pilot-first pricing and procurement-friendly legal pack", "owner": "Founder"},
            {"risk": "Complex integrations with legacy stacks", "mitigation": "CSV/API hybrid bridge during phase one", "owner": "Engineering"},
            {"risk": "Change resistance from tender committees", "mitigation": "Onsite enablement and stakeholder scorecards", "owner": "Implementation"},
        ],
        "diligence_docs": [
            "Discovery transcripts with procurement leads",
            "MVP architecture and security controls",
            "Sample tender workflow configuration",
            "Pipeline and conversion assumptions workbook",
        ],
    },
    "cv-3314": {
        "slug": "cv-3314",
        "code": "CV-3314",
        "title": "Saudi Specialty Coffee Brand (D2C Model)",
        "tagline": "Specialty beans with subscription-first D2C, selective wholesale, and controlled inventory turns.",
        "alignment_score": 74,
        "city": "Jeddah",
        "country": "Saudi Arabia",
        "sector": "Consumer Brand / Food & Beverage",
        "stage": "Brand and supplier secured",
        "founder_commitment": "Full-Time",
        "capital_status": "SAR 200,000 committed",
        "target_raise": "SAR 1.1M seed",
        "runway": "10 months",
        "positions_needed": [
            "Operations & Supply Chain Partner",
            "Growth Marketing Lead",
        ],
        "skills_needed": [
            "Vendor management",
            "Demand planning",
            "Subscription retention",
            "Unit economics discipline",
        ],
        "overview": "The brand focuses on curated monthly coffee drops and recurring subscriptions. Wholesale is limited to high-fit cafes to protect pricing and operational reliability during scale-up.",
        "problem_points": [
            "Generic mass-market coffee options dominate convenience channels.",
            "Specialty quality is inconsistent across online-first local brands.",
            "Many new coffee brands over-expand SKU count early and hurt cash cycle.",
        ],
        "solution_points": [
            "Focused SKU strategy with seasonal rotations and transparent sourcing.",
            "Subscription cohorts with taste preference mapping and guided onboarding.",
            "Inventory gating and reorder points linked to demand forecasts.",
        ],
        "market_assumptions": [
            {"label": "Target monthly orders by month 12", "value": "2,800 orders"},
            {"label": "Subscription share target", "value": "46% of revenue"},
            {"label": "Wholesale partner target", "value": "28 curated accounts"},
        ],
        "unit_economics": [
            {"metric": "Average order value", "value": "SAR 132", "note": "D2C mix with accessories"},
            {"metric": "Contribution margin", "value": "41%", "note": "After shipping and payment fees"},
            {"metric": "CAC payback", "value": "2.7 months", "note": "Paid social + referral mix"},
        ],
        "go_to_market": [
            "Creator-led tasting sessions and launch drops for early advocates.",
            "Referral mechanics embedded into subscription lifecycle.",
            "Selective cafe placements to strengthen local credibility.",
        ],
        "milestones": [
            {"name": "Roasting partner QA sign-off", "status": "Completed", "date": "2026-02"},
            {"name": "Subscription portal launch", "status": "In Progress", "date": "2026-04"},
            {"name": "Wholesale onboarding playbook", "status": "Planned", "date": "2026-06"},
        ],
        "risk_register": [
            {"risk": "Inventory mismatch for seasonal blends", "mitigation": "Rolling 8-week forecast and SKU throttling", "owner": "Operations"},
            {"risk": "Paid acquisition efficiency volatility", "mitigation": "Cohort-level CAC caps and channel diversification", "owner": "Growth"},
            {"risk": "Fulfillment quality variance", "mitigation": "3PL QA checklist and SLA penalty clauses", "owner": "Founder"},
        ],
        "diligence_docs": [
            "Brand strategy memo and positioning study",
            "Supplier QA and cupping records",
            "Subscription funnel baseline analytics",
            "Cash-flow model with inventory stress tests",
        ],
    },
    "cv-9245": {
        "slug": "cv-9245",
        "code": "CV-9245",
        "title": "Performance Optimization App for GCC Professionals",
        "tagline": "Personal performance stack blending fitness, focus, and habit telemetry for knowledge workers.",
        "alignment_score": 58,
        "city": "Remote-first (GCC)",
        "country": "Saudi Arabia / UAE",
        "sector": "Consumer App / Productivity + Wellness",
        "stage": "UI prototype completed",
        "founder_commitment": "Part-Time moving to Full-Time within 6 months",
        "capital_status": "Self-funded",
        "target_raise": "SAR 1.4M pre-seed",
        "runway": "8 months",
        "positions_needed": [
            "Mobile App Developer (Flutter/React Native)",
            "Data Product Analyst",
        ],
        "skills_needed": [
            "Mobile architecture",
            "Behavioral product loops",
            "API integrations",
            "Analytics instrumentation",
        ],
        "overview": "The app combines activity tracking, calendar context, focus blocks, and self-reported energy markers into one daily score model. The product thesis is sustained routine quality over short-term intensity.",
        "problem_points": [
            "Users juggle multiple disconnected tools for fitness, scheduling, and focus.",
            "Most habit apps optimize streak vanity metrics rather than meaningful outcomes.",
            "Workload and wellness data are rarely interpreted together.",
        ],
        "solution_points": [
            "Unified daily performance dashboard with weighted signals.",
            "Adaptive coaching prompts based on sleep, schedule, and workload variance.",
            "Weekly reflection flow with trend diagnosis and recommended interventions.",
        ],
        "market_assumptions": [
            {"label": "Target free users (12 months)", "value": "28,000"},
            {"label": "Premium conversion target", "value": "4.8%"},
            {"label": "Monthly premium ARPU", "value": "SAR 39"},
        ],
        "unit_economics": [
            {"metric": "Blended CAC target", "value": "SAR 24", "note": "Organic-led with creator partnerships"},
            {"metric": "Month-3 retention target", "value": "33%", "note": "Premium and free combined"},
            {"metric": "Gross margin", "value": "83%", "note": "Excluding R&D payroll"},
        ],
        "go_to_market": [
            "Early access cohort through professional communities and founder circles.",
            "Content-led acquisition around practical performance routines.",
            "Referral unlocks tied to premium feature trials.",
        ],
        "milestones": [
            {"name": "Prototype usability tests (n=55)", "status": "Completed", "date": "2026-02"},
            {"name": "Beta release and instrumentation", "status": "In Progress", "date": "2026-05"},
            {"name": "Subscription launch", "status": "Planned", "date": "2026-08"},
        ],
        "risk_register": [
            {"risk": "Retention volatility after week two", "mitigation": "First-week activation redesign and tailored nudges", "owner": "Product"},
            {"risk": "Data privacy trust concerns", "mitigation": "Clear consent model and privacy dashboard", "owner": "Engineering"},
            {"risk": "Founder bandwidth constraints", "mitigation": "Time-boxed roadmap and fractional support", "owner": "Founder"},
        ],
        "diligence_docs": [
            "Prototype test recordings and UX report",
            "Event taxonomy and analytics plan",
            "Retention benchmark analysis",
            "Roadmap and hiring plan (2 quarters)",
        ],
    },
}



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
