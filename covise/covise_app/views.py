from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import WaitlistEntry

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

def onboarding(request):
    return render(request, 'onboarding.html')

@ensure_csrf_cookie
def waitlist(request):
    context = {}

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        country = request.POST.get('country', '').strip()
        non_gcc_business = request.POST.get('non_gcc_business') == 'on'
        custom_country = request.POST.get('custom_country', '').strip()
        linkedin = request.POST.get('linkedin', '').strip()

        if not all([full_name, phone_number, email, linkedin]):
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

            WaitlistEntry.objects.create(
                full_name=full_name,
                phone_number=phone_number,
                email=email,
                country=country,
                non_gcc_business=non_gcc_business,
                custom_country=custom_country,
                linkedin=linkedin,
            )
            return redirect('Waitlist Success')

    return render(request, 'waitlist.html', context)


def waitlist_success(request):
    return render(request, 'waitlist_success.html')


def csrf_failure(request, reason=""):
    context = {"reason": reason}
    return render(request, "csrf_error.html", context, status=403)
