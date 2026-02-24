from django.urls import path
from . import views


from django.contrib.sitemaps.views import sitemap
from covise_app.sitemaps import StaticViewSitemap

from django.http import HttpResponse

def robots_txt(request):
    content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /profile/
Sitemap: https://covise.net/sitemap.xml
"""
    return HttpResponse(content, content_type='text/plain')


sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('robots.txt', robots_txt),

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

