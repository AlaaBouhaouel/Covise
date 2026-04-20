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
    path('posts/<int:post_id>/save/', views.toggle_saved_post, name='Toggle Saved Post'),
    path('posts/<int:post_id>/react/<str:reaction>/', views.toggle_post_reaction, name='Toggle Post Reaction'),
    path('posts/<int:post_id>/delete/', views.delete_post, name='Delete Post'),
    path('projects/', views.projects, name='Projects'),
    path('projects/<slug:project_slug>/', views.project_detail, name='Project Detail'),
    path('messages/', views.messages, name='Messages'),
    path('messages/state/', views.messages_state, name='Messages State'),
    path('requests/', views.requests_page, name='Requests'),
    path('messages/groups/create/', views.create_group_conversation, name='Create Group Conversation'),
    path('messages/<uuid:conversation_id>/send/', views.send_message, name='Send Message'),
    path('messages/<uuid:conversation_id>/media/', views.send_media_message, name='Send Media Message'),
    path('messages/<uuid:conversation_id>/seen/', views.mark_messages_seen, name='Mark Messages Seen'),
    path('messages/<uuid:conversation_id>/mute/', views.toggle_conversation_mute, name='Toggle Conversation Mute'),
    path('messages/<uuid:conversation_id>/recording/', views.toggle_conversation_recording, name='Toggle Conversation Recording'),
    path('messages/<uuid:conversation_id>/report/', views.report_conversation_user, name='Report Conversation User'),
    path('messages/<uuid:conversation_id>/delete/', views.delete_conversation, name='Delete Conversation'),
    path('messages/reactions/<uuid:message_id>/<str:reaction>/', views.toggle_message_reaction, name='Toggle Message Reaction'),
    path('messages/<uuid:message_id>/delete-message/', views.delete_message, name='Delete Message'),
    path('messages/<uuid:message_id>/report-message/', views.report_message, name='Report Message'),
    path('messages/start/<uuid:user_id>/', views.start_private_conversation, name='Start Private Conversation'),
    path('messages/requests/<uuid:request_id>/<str:action>/', views.respond_to_conversation_request, name='Respond To Conversation Request'),
    path('notifications/', views.notifications_list, name='Notifications List'),
    path('notifications/<int:notification_id>/read/', views.notifications_mark_read, name='Notifications Mark Read'),
    path('notifications/read-all/', views.notifications_mark_all_read, name='Notifications Mark All Read'),
    path('users/<uuid:user_id>/block/', views.toggle_block_user, name='Toggle Block User'),
    path('map/', views.map_view, name='Map'),
    path('chatbot/', views.chatbot, name='Chatbot'),
    path('profile/', views.profile, name='Profile'),
    path('profile/personal-data/', views.profile_personal_data, name='Profile Personal Data'),
    path('profile/experience/', views.profile_experience, name='Profile Experience'),
    path('profile/active-projects/', views.profile_active_projects, name='Profile Active Projects'),
    path('profile/saved-posts/', views.profile_saved_posts, name='Profile Saved Posts'),
    path('profile/posts/', views.profile_posts, name='Profile Posts'),
    path('profile/user/<uuid:user_id>/', views.public_profile, name='Public Profile'),
    path('profile/user/<uuid:user_id>/experience/', views.public_profile_experience, name='Public Profile Experience'),
    path('profile/user/<uuid:user_id>/active-projects/', views.public_profile_active_projects, name='Public Profile Active Projects'),
    path('profile/user/<uuid:user_id>/posts/', views.public_profile_posts, name='Public Profile Posts'),
    path('profile/user/<uuid:user_id>/report/', views.report_user_profile, name='Report User Profile'),
    path('profile/<int:comment_id>/<str:action>/', views.post_action, name='post_action'),
    path('comments/<int:comment_id>/edit/', views.edit_comment, name='Edit Comment'),
    path('comments/<int:comment_id>/delete/', views.delete_comment, name='Delete Comment'),
    path('comments/<int:comment_id>/pin/', views.toggle_comment_pin, name='Toggle Comment Pin'),
    path('profile/card/', views.profile_card, name='Profile Card'),
    path('settings/', views.settings, name='Settings'),
    path('settings/request-data-export/', views.request_data_export, name='Request Data Export'),
    path('settings/request-account-pause/', views.request_account_pause, name='Request Account Pause'),
    path('settings/request-data-deletion/', views.request_data_deletion, name='Request Data Deletion'),
    path('settings/delete-account/', views.delete_account, name='Delete Account'),
    path('settings/security/', views.account_security, name='Account Security'),
    path('settings/<slug:section_slug>/', views.settings_section, name='Settings Section'),
    path('agreement/', views.agreement, name='Agreement'),
    path('logout/', views.logout_page, name='Logout'),
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
    path('waitlist/', views.waitlist, name='Waitlist'),
    path('waitlist/verify-email/send/', views.waitlist_verify_email_send, name='Waitlist Email Verify Send'),
    path('waitlist/verified-email-abandoned/', views.waitlist_verified_email_abandoned, name='Waitlist Verified Email Abandoned'),
    path('waitlist/success/', views.waitlist_success, name='Waitlist Success'),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

]
