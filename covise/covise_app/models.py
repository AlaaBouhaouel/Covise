from django.db import models

class WaitlistEntry(models.Model):
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField()
    country = models.CharField(max_length=100, blank=True)
    non_gcc_business = models.BooleanField(default=False)
    custom_country = models.CharField(max_length=100, blank=True)
    linkedin = models.URLField(max_length=300)
    cv = models.FileField(upload_to='cv_uploads/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class OnboardingResponse(models.Model):
    waitlist_entry = models.ForeignKey(
        WaitlistEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboarding_responses",
    )
    email = models.EmailField(db_index=True)
    flow_name = models.CharField(max_length=200, blank=True)
    answers = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"OnboardingResponse<{self.email}>"
