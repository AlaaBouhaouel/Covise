from django.urls import path
from . import views
urlpatterns = [
    path('', views.landing, name='Landing Page'),
    path('home/', views.home, name='Home'),
    path('requests/', views.requests, name='Requests'),
    path('messages/', views.messages, name='Messages'),
    path('map/', views.map_view, name='Map'),
    path('chatbot/', views.chatbot, name='Chatbot'),
    path('profile/', views.profile, name='Profile'),
    path('settings/', views.settings, name='Settings'),
    path('login/', views.login_view, name='Login'),
    path('signin/', views.signin, name='Sign In'),
    path('onboarding/', views.onboarding, name='Onboarding'),
    path('waitlist/', views.waitlist, name='Waitlist'),
    path('waitlist/success/', views.waitlist_success, name='Waitlist Success'),
]

