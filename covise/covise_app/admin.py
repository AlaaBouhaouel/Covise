from django.contrib import admin
from .models import OnboardingResponse, WaitlistEntry

@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "country", "non_gcc_business", "created_at")
    search_fields = ("full_name", "email", "phone_number")


@admin.register(OnboardingResponse)
class OnboardingResponseAdmin(admin.ModelAdmin):
    list_display = ("email", "flow_name", "waitlist_entry", "updated_at")
    search_fields = ("email", "flow_name")
