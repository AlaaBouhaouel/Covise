import uuid

from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin

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
    my_referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
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
        related_name="onboarding_response",
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



class UsersModel(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email) #to verify that the email is in the correct format and to convert it to lowercase
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)    



# covise_app/models.py
class User(AbstractBaseUser, PermissionsMixin):
    @property
    def avatar_initials(self):
        name = (self.full_name or "").strip()

        if name:
            parts = name.split()
            if len(parts) >= 2:
                return (parts[0][0] + parts[1][0]).upper()
            return name[:2].upper()

        return self.email[:2].upper()
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #the primary key is the ID field, which is a UUIDField. This means that each user will have a unique identifier that is generated using the UUID algorithm.

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    sign_in_count = models.PositiveIntegerField(default=0)
    has_seen_interactive_demo = models.BooleanField(default=False)

    objects = UsersModel()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
        

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    source_waitlist_entry = models.ForeignKey(
        WaitlistEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="migrated_profiles",
    )
    source_onboarding_response = models.ForeignKey(
        OnboardingResponse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="migrated_profiles",
    )

    full_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    nationality = models.CharField(max_length=150, blank=True)
    profile_image = models.ImageField(upload_to="profile_images/", blank=True, null=True)

    linkedin = models.URLField(max_length=300, blank=True)
    github = models.URLField(max_length=300, blank=True)
    proof_of_work_url = models.URLField(max_length=300, blank=True)
    bio = models.TextField(blank=True)
    tools = models.TextField(blank=True)
    plan = models.CharField(max_length=50, default="Free")
    waitlist_snapshot = models.JSONField(default=dict, blank=True)
    onboarding_answers = models.JSONField(default=dict, blank=True)

    non_gcc_business = models.BooleanField(default=False)
    custom_country = models.CharField(max_length=100, blank=True)
    cv_s3_key = models.CharField(max_length=500, blank=True, null=True)
    my_referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


    def __str__(self):
        return f"Profile of {self.user.email}"


class UserPreference(models.Model):
    class ProfileVisibility(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        MATCHED_ONLY = "matched_only", "Matched users only"
        NOBODY = "nobody", "Nobody"

    class EmailFrequency(models.TextChoices):
        INSTANT = "instant", "Instant"
        DAILY = "daily", "Daily Digest"
        WEEKLY = "weekly", "Weekly Digest"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")

    profile_visibility = models.CharField(
        max_length=20,
        choices=ProfileVisibility.choices,
        default=ProfileVisibility.EVERYONE,
    )
    read_profile_data = models.BooleanField(default=True)
    show_conviction_score = models.BooleanField(default=True)
    show_cv_to_matches = models.BooleanField(default=True)
    show_linkedin_to_matches = models.BooleanField(default=True)
    appear_in_search = models.BooleanField(default=True)
    pause_matching = models.BooleanField(default=False)

    ai_enabled = models.BooleanField(default=True)
    ai_read_messages = models.BooleanField(default=True)
    ai_read_workspace = models.BooleanField(default=True)
    ai_post_updates = models.BooleanField(default=False)
    ai_send_messages = models.BooleanField(default=False)
    ai_edit_workspace = models.BooleanField(default=False)
    ai_manage_milestones = models.BooleanField(default=False)

    email_new_match = models.BooleanField(default=True)
    email_new_message = models.BooleanField(default=True)
    email_connection_request = models.BooleanField(default=True)
    email_request_accepted = models.BooleanField(default=True)
    email_milestone_reminder = models.BooleanField(default=True)
    email_workspace_activity = models.BooleanField(default=False)
    email_platform_updates = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)

    in_app_new_match = models.BooleanField(default=True)
    in_app_new_message = models.BooleanField(default=True)
    in_app_connection_request = models.BooleanField(default=True)
    in_app_request_accepted = models.BooleanField(default=True)
    in_app_milestone_reminder = models.BooleanField(default=True)
    in_app_workspace_activity = models.BooleanField(default=False)
    in_app_platform_updates = models.BooleanField(default=True)
    in_app_marketing = models.BooleanField(default=False)

    email_frequency = models.CharField(
        max_length=20,
        choices=EmailFrequency.choices,
        default=EmailFrequency.INSTANT,
    )

    preferred_cofounder_types = models.JSONField(default=list, blank=True)
    preferred_industries = models.JSONField(default=list, blank=True)
    preferred_gcc_markets = models.JSONField(default=list, blank=True)
    minimum_commitment = models.CharField(max_length=20, default="Either")
    open_to_foreign_founders = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Preferences for {self.user.email}"


class Conversation(models.Model):
    class ConversationType(models.TextChoices):
        PRIVATE = "private", "Private"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_type = models.CharField(
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.PRIVATE,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_conversations",
    )
    participants = models.ManyToManyField(User, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-last_message_at", "-updated_at"]

    def __str__(self):
        return f"{self.get_conversation_type_display()} conversation {self.pk}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message<{self.sender.email}>"


class ConversationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_conversation_requests",
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_conversation_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        related_name="requests",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ConversationRequest<{self.requester.email} -> {self.recipient.email}>"




class Post(models.Model):
    class PostType(models.TextChoices):
        IDEA = "idea", "Idea"
        UPDATE = "update", "Update"
        ASK = "ask", "Ask"
        WIN = "win", "Win"
        AMA = "ask_me_anything", "Ask Me Anything"


    user=models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    post_type=models.CharField(max_length=20, choices=PostType.choices)
    content=models.TextField()
    likes_number=models.IntegerField(default=0)
    comments_number=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)



class Comment(models.Model): 
    user = models.ForeignKey(User,on_delete=models.CASCADE, related_name="comments")
    post=models.ForeignKey(Post, on_delete=models.CASCADE,  related_name="comments" )
    content=models.CharField(max_length=200)
    up=models.IntegerField(default=0)
    down=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)


class CommentReaction(models.Model):
    class ReactionType(models.TextChoices):
        UP = "up", "Upvote"
        DOWN = "down", "Downvote"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_reactions")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="reactions")
    reaction = models.CharField(max_length=10, choices=ReactionType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "comment"], name="unique_user_comment_reaction")
        ]

class Experiences(models.Model):
    user=models.ForeignKey(User, on_delete=models.CASCADE, related_name="experiences")
    title=models.CharField(max_length=100, blank=False)
    date=models.DateTimeField(blank=False)
    desc=models.TextField()

class Active_projects(models.Model):
    user=models.ForeignKey(User, on_delete=models.CASCADE, related_name="active_projects")
    name=models.CharField(max_length=100, blank=False )
    status=models.CharField(max_length=100, blank=True)
    desc=models.TextField()


class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects", null=True, blank=True)
    slug = models.SlugField(unique=True)
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=255)
    tagline = models.CharField(max_length=400, blank=True)
    founder_name = models.CharField(max_length=150, blank=True)
    founder_initials = models.CharField(max_length=4, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    sector = models.CharField(max_length=200, blank=True)
    stage = models.CharField(max_length=200, blank=True)
    founder_commitment = models.CharField(max_length=100, blank=True)
    capital_status = models.CharField(max_length=150, blank=True)
    target_raise = models.CharField(max_length=150, blank=True)
    runway = models.CharField(max_length=100, blank=True)
    overview = models.TextField(blank=True)
    card_description = models.TextField(blank=True)
    alignment_score = models.PositiveIntegerField(default=0)
    alignment_details = models.JSONField(default=dict, blank=True)
    positions_needed = models.JSONField(default=list, blank=True)
    skills_needed = models.JSONField(default=list, blank=True)
    problem_points = models.JSONField(default=list, blank=True)
    solution_points = models.JSONField(default=list, blank=True)
    market_assumptions = models.JSONField(default=list, blank=True)
    unit_economics = models.JSONField(default=list, blank=True)
    go_to_market = models.JSONField(default=list, blank=True)
    milestones = models.JSONField(default=list, blank=True)
    risk_register = models.JSONField(default=list, blank=True)
    diligence_docs = models.JSONField(default=list, blank=True)
    filter_tokens = models.JSONField(default=list, blank=True)
    search_text = models.TextField(blank=True)
    team_members_filled = models.PositiveIntegerField(default=1)
    team_size_target = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ai_summary = models.TextField(blank=True)
    ai_notes = models.TextField(blank=True)
    ai_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-updated_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    @property
    def team_progress_percent(self):
        if not self.team_size_target:
            return 0
        return round((self.team_members_filled / self.team_size_target) * 100)
