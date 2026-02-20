from django.shortcuts import render

# Create your views here.
def landing(request):
    return render(request, 'landing.html')

def home(request):
    return render(request, 'home.html')

def messages(request):
    return render(request, 'messages.html')

def requests(request):
    return render(request, 'requests.html')

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
