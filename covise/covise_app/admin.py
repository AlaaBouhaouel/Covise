from django.contrib import admin
from .models import OnboardingResponse, WaitlistEntry

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
