from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import OnboardingResponse, Profile, WaitlistEntry, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "full_name", "is_staff", "is_active", "is_superuser")
    search_fields = ("email", "full_name")
    list_filter = ("is_staff", "is_active", "is_superuser", "groups")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2", "is_staff", "is_active"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "status", "country", "non_gcc_business", "my_referral_code", "referred_by", "created_at")
    list_filter = ("status", "non_gcc_business", "created_at")
    search_fields = ("full_name", "email", "phone_number", "my_referral_code")
    readonly_fields = ("my_referral_code", "referred_by")


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
        ("Identity", {"fields": ("full_name", "phone_number", "country", "custom_country", "linkedin", "bio")}),
        ("Referral", {"fields": ("my_referral_code", "referred_by")}),
        ("Business Info", {"fields": ("non_gcc_business", "cv_s3_key", "flow_name")}),
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
                "profile_visibility_consent",
                "answers",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
