from django.urls import path
from . import views


from django.contrib.sitemaps.views import sitemap
from covise_app.sitemaps import StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('', views.landing, name='Landing Page'),
    path('home/', views.home, name='Home'),
    path('projects/', views.projects, name='Projects'),
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

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

]

