from django.urls import path
from django.contrib.auth import views as auth_views
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
    path('posts/create/', views.create_post, name='Create Post'),
    path('posts/<int:post_id>/', views.post_detail, name='Post Detail'),
    path('posts/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('projects/', views.projects, name='Projects'),
    path('projects/<slug:project_slug>/', views.project_detail, name='Project Detail'),
    path('messages/', views.messages, name='Messages'),
    path('messages/start/<uuid:user_id>/', views.start_private_conversation, name='Start Private Conversation'),
    path('messages/requests/<uuid:request_id>/<str:action>/', views.respond_to_conversation_request, name='Respond To Conversation Request'),
    path('map/', views.map_view, name='Map'),
    path('chatbot/', views.chatbot, name='Chatbot'),
    path('profile/', views.profile, name='Profile'),
    path('profile/user/<uuid:user_id>/', views.public_profile, name='Public Profile'),
    path('profile/<int:comment_id>/<str:action>/', views.post_action, name='post_action'),
    path('profile/card/', views.profile_card, name='Profile Card'),
    path('settings/', views.settings, name='Settings'),
    path('terms/', views.terms, name='Terms'),
    path('privacy/', views.privacy, name='Privacy'),
    path('login/', views.login_view, name='Login'),
    path('security/', views.security, name='Security'),
    path('signin/', views.signin, name='Sign In'),
    path(
        'forgot-password/',
        auth_views.PasswordResetView.as_view(
            template_name='forgot_password.html',
            email_template_name='registration/password_reset_email.txt',
            subject_template_name='registration/password_reset_subject.txt',
            success_url='/forgot-password/sent/',
        ),
        name='Forgot Password',
    ),
    path(
        'forgot-password/sent/',
        auth_views.PasswordResetDoneView.as_view(template_name='forgot_password_sent.html'),
        name='Forgot Password Sent',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='reset_password_confirm.html',
            success_url='/reset/complete/',
        ),
        name='Password Reset Confirm',
    ),
    path(
        'reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='reset_password_complete.html'),
        name='Password Reset Complete',
    ),
    path('onboarding-final/', views.onboarding_final, name='Onboarding Final'),
    path('onboarding/', views.onboarding, name='Onboarding'),
    path('onboarding/submit/', views.onboarding_submit, name='Onboarding Submit'),
    path('loading/', views.loading, name='Loading'),
#    path('pricing/', views.pricing, name='Pricing'),
    path('features/', views.features, name='Features'),
    path('about/', views.about, name='About'),
    path('workspace/', views.workspace, name='Workspace'),
    # path('waitlist/', views.waitlist, name='Waitlist'),
    # path('waitlist/verify-email/send/', views.waitlist_verify_email_send, name='Waitlist Email Verify Send'),
    # path('waitlist/verify-email/code/', views.waitlist_verify_email_code, name='Waitlist Email Verify Code'),
    # path('waitlist/success/', views.waitlist_success, name='Waitlist Success'),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

]
