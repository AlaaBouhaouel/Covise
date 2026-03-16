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
    path('projects/<slug:project_slug>/', views.project_detail, name='Project Detail'),
    path('messages/', views.messages, name='Messages'),
    path('map/', views.map_view, name='Map'),
    path('chatbot/', views.chatbot, name='Chatbot'),
    path('profile/', views.profile, name='Profile'),
    path('profile/card/', views.profile_card, name='Profile Card'),
    path('settings/', views.settings, name='Settings'),
    path('terms/', views.terms, name='Terms'),
    path('privacy/', views.privacy, name='Privacy'),
    path('login/', views.login_view, name='Login'),
    path('signin/', views.signin, name='Sign In'),
    path('onboarding-final/', views.onboarding_final, name='Onboarding Final'),
    path('onboarding/', views.onboarding, name='Onboarding'),
    path('onboarding/submit/', views.onboarding_submit, name='Onboarding Submit'),
    path('loading/', views.loading, name='Loading'),
    path('pricing/', views.pricing, name='Pricing'),
    path('features/', views.features, name='Features'),
    path('about/', views.about, name='About'),
    path('workspace/', views.workspace, name='Workspace'),
    path('waitlist/', views.waitlist, name='Waitlist'),
    path('waitlist/success/', views.waitlist_success, name='Waitlist Success'),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

]
