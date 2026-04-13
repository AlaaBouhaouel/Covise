from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import OnboardingResponse, Profile, UserPreference, WaitlistEmailVerification, WaitlistEntry, User, Post, Comment, Experiences, Active_projects, Project, Conversation, Message, ConversationRequest


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "full_name", "sign_in_count", "has_seen_interactive_demo", "last_login", "is_staff", "is_active", "is_superuser")
    search_fields = ("email", "full_name")
    list_filter = ("is_staff", "is_active", "is_superuser", "groups")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name",)}),
        ("Activity", {"fields": ("sign_in_count", "has_seen_interactive_demo", "last_login", "date_joined")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2", "is_staff", "is_active"),
        }),
    )
    readonly_fields = ("sign_in_count", "last_login", "date_joined")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "status", "country", "non_gcc_business", "my_referral_code", "referred_by", "created_at")
    list_filter = ("status", "non_gcc_business", "created_at")
    search_fields = ("full_name", "email", "phone_number", "my_referral_code")
    readonly_fields = ("my_referral_code", "referred_by")


@admin.register(WaitlistEmailVerification)
class WaitlistEmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("email", "verification_code", "verified_at", "created_at", "updated_at")
    search_fields = ("email", "verification_code")
    list_filter = ("verified_at", "created_at", "updated_at")
    readonly_fields = ("token", "created_at", "updated_at")


@admin.register(OnboardingResponse)
class OnboardingResponseAdmin(admin.ModelAdmin):
    list_display = ("email", "flow_name", "waitlist_entry", "updated_at")
    search_fields = ("email", "flow_name")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "full_name",
        "phone_number",
        "country",
        "non_gcc_business",
        "linkedin",
        "my_referral_code",
        "referred_by",
        "flow_name",
        "source_waitlist_entry",
        "source_onboarding_response",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__email",
        "full_name",
        "phone_number",
        "country",
        "my_referral_code",
        "flow_name",
    )
    list_filter = (
        "non_gcc_business",
        "country",
        "flow_name",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("User Link", {"fields": ("user", "source_waitlist_entry", "source_onboarding_response")}),
        (
            "Identity",
            {
                "fields": (
                    "full_name",
                    "phone_number",
                    "country",
                    "nationality",
                    "custom_country",
                    "linkedin",
                    "github",
                    "proof_of_work_url",
                    "bio",
                    "tools",
                    "plan",
                )
            },
        ),
        ("Referral", {"fields": ("my_referral_code", "referred_by")}),
        ("Business Info", {"fields": ("non_gcc_business", "cv_s3_key", "flow_name", "waitlist_snapshot", "onboarding_answers")}),
        ("Onboarding Snapshot", {
            "fields": (
                "user_type",
                "industry",
                "stage",
                "target_market",
                "team_size",
                "one_liner",
                "cofounders_needed",
                "looking_for_type",
                "founder_timeline",
                "current_role",
                "years_experience",
                "industries_interested",
                "venture_stage_preference",
                "founder_type_preference",
                "specialist_timeline",
                "investor_type",
                "investment_geography",
                "ticket_size",
                "investment_stage",
                "investment_industries",
                "investor_value_add",
                "investor_looking_for",
                "investor_timeline",
                "home_country",
                "target_gcc_market",
                "foreign_industry",
                "foreign_stage",
                "foreign_one_liner",
                "local_partner_need",
                "foreign_timeline",
                "program_type",
                "program_location",
                "program_stage_focus",
                "program_industries",
                "cohort_size",
                "program_offering",
                "incubator_looking_for",
                "incubator_timeline",
                "skills",
                "availability",
                "capital_contribution",
                "looking_for_skills",
                "cofounder_commitment",
                "compensation",
                "cofounder_location_pref",
                "monthly_revenue",
                "funding_status",
                "customer_count",
                "commitment_level",
                "risk_tolerance",
                "execution_history",
                "leadership_style",
                "how_heard",
                "referral_code",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "profile_visibility",
        "pause_matching",
        "ai_enabled",
        "email_frequency",
        "updated_at",
    )
    search_fields = ("user__email", "user__full_name")
    list_filter = ("profile_visibility", "pause_matching", "ai_enabled", "email_frequency", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("User Link", {"fields": ("user",)}),
        (
            "Profile Visibility",
            {
                "fields": (
                    "profile_visibility",
                    "show_conviction_score",
                    "show_cv_to_matches",
                    "show_linkedin_to_matches",
                    "appear_in_search",
                    "pause_matching",
                )
            },
        ),
        (
            "AI Permissions",
            {
                "fields": (
                    "ai_enabled",
                    "ai_read_messages",
                    "ai_read_workspace",
                    "ai_post_updates",
                    "ai_send_messages",
                    "ai_edit_workspace",
                    "ai_manage_milestones",
                )
            },
        ),
        (
            "Notifications",
            {
                "fields": (
                    "email_new_match",
                    "email_new_message",
                    "email_connection_request",
                    "email_request_accepted",
                    "email_milestone_reminder",
                    "email_workspace_activity",
                    "email_platform_updates",
                    "email_marketing",
                    "in_app_new_match",
                    "in_app_new_message",
                    "in_app_connection_request",
                    "in_app_request_accepted",
                    "in_app_milestone_reminder",
                    "in_app_workspace_activity",
                    "in_app_platform_updates",
                    "in_app_marketing",
                    "email_frequency",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "post_type", "theme_color", "image", "likes_number", "comments_number", "created_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")

@admin.register(Experiences)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "date", "desc")


@admin.register(Active_projects)
class ActiveProjectsAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "status", "desc")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "user", "founder_name", "city", "country", "stage", "alignment_score", "is_active", "published_at")
    search_fields = ("code", "title", "user__email", "user__full_name", "founder_name", "city", "country", "sector", "search_text")
    list_filter = ("is_active", "country", "city", "stage", "sector", "published_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation_type", "created_by", "last_message_at", "created_at")
    search_fields = ("id", "created_by__email", "created_by__full_name", "participants__email", "participants__full_name")
    filter_horizontal = ("participants",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at")
    search_fields = ("id", "conversation__id", "sender__email", "sender__full_name", "body")


@admin.register(ConversationRequest)
class ConversationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "recipient", "status", "conversation", "created_at", "responded_at")
    search_fields = ("requester__email", "requester__full_name", "recipient__email", "recipient__full_name")
    list_filter = ("status", "created_at", "responded_at")
