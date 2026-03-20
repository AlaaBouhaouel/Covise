from django.db import models

class WaitlistEntry(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        ACTIVATED = "activated", "Activated"
        REJECTED = "rejected", "Rejected"

    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(unique=True)
    country = models.CharField(max_length=100, blank=True)
    non_gcc_business = models.BooleanField(default=False)
    custom_country = models.CharField(max_length=100, blank=True)
    linkedin = models.URLField(max_length=300)
    cv_s3_key = models.CharField(max_length=500, blank=True, null=True)
    my_referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class OnboardingResponse(models.Model):
    waitlist_entry = models.OneToOneField(
        WaitlistEntry,
        on_delete=models.CASCADE,
        related_name="profile",
        null=True,
        blank=True,
    )
    email = models.EmailField(db_index=True)
    flow_name = models.CharField(max_length=200, blank=True)
    user_type = models.JSONField(null=True, blank=True)
    industry = models.JSONField(null=True, blank=True)
    stage = models.JSONField(null=True, blank=True)
    target_market = models.JSONField(null=True, blank=True)
    team_size = models.JSONField(null=True, blank=True)
    one_liner = models.JSONField(null=True, blank=True)
    cofounders_needed = models.JSONField(null=True, blank=True)
    looking_for_type = models.JSONField(null=True, blank=True)
    founder_timeline = models.JSONField(null=True, blank=True)
    current_role = models.JSONField(null=True, blank=True)
    years_experience = models.JSONField(null=True, blank=True)
    industries_interested = models.JSONField(null=True, blank=True)
    venture_stage_preference = models.JSONField(null=True, blank=True)
    founder_type_preference = models.JSONField(null=True, blank=True)
    specialist_timeline = models.JSONField(null=True, blank=True)
    investor_type = models.JSONField(null=True, blank=True)
    investment_geography = models.JSONField(null=True, blank=True)
    ticket_size = models.JSONField(null=True, blank=True)
    investment_stage = models.JSONField(null=True, blank=True)
    investment_industries = models.JSONField(null=True, blank=True)
    investor_value_add = models.JSONField(null=True, blank=True)
    investor_looking_for = models.JSONField(null=True, blank=True)
    investor_timeline = models.JSONField(null=True, blank=True)
    home_country = models.JSONField(null=True, blank=True)
    target_gcc_market = models.JSONField(null=True, blank=True)
    foreign_industry = models.JSONField(null=True, blank=True)
    foreign_stage = models.JSONField(null=True, blank=True)
    foreign_one_liner = models.JSONField(null=True, blank=True)
    local_partner_need = models.JSONField(null=True, blank=True)
    foreign_timeline = models.JSONField(null=True, blank=True)
    program_type = models.JSONField(null=True, blank=True)
    program_location = models.JSONField(null=True, blank=True)
    program_stage_focus = models.JSONField(null=True, blank=True)
    program_industries = models.JSONField(null=True, blank=True)
    cohort_size = models.JSONField(null=True, blank=True)
    program_offering = models.JSONField(null=True, blank=True)
    incubator_looking_for = models.JSONField(null=True, blank=True)
    incubator_timeline = models.JSONField(null=True, blank=True)
    skills = models.JSONField(null=True, blank=True)
    availability = models.JSONField(null=True, blank=True)
    capital_contribution = models.JSONField(null=True, blank=True)
    looking_for_skills = models.JSONField(null=True, blank=True)
    cofounder_commitment = models.JSONField(null=True, blank=True)
    compensation = models.JSONField(null=True, blank=True)
    cofounder_location_pref = models.JSONField(null=True, blank=True)
    monthly_revenue = models.JSONField(null=True, blank=True)
    funding_status = models.JSONField(null=True, blank=True)
    customer_count = models.JSONField(null=True, blank=True)
    commitment_level = models.JSONField(null=True, blank=True)
    risk_tolerance = models.JSONField(null=True, blank=True)
    execution_history = models.JSONField(null=True, blank=True)
    leadership_style = models.JSONField(null=True, blank=True)
    how_heard = models.JSONField(null=True, blank=True)
    referral_code = models.JSONField(null=True, blank=True)
    profile_visibility_consent = models.JSONField(null=True, blank=True)
    answers = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        identifier = self.waitlist_entry.email if self.waitlist_entry else self.email
        return f"OnboardingResponse<{identifier}>"
