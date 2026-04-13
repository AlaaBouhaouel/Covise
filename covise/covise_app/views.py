import json
import logging
from pathlib import Path
from django.http import Http404, HttpResponsePermanentRedirect, JsonResponse
from django.db import IntegrityError, OperationalError, close_old_connections
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.timesince import timesince
from .models import OnboardingResponse, Profile, User, UserPreference, WaitlistEntry, Post, Comment, CommentReaction, Experiences, Active_projects, Project, Conversation, Message, ConversationRequest
from covise_app.utils import generate_referral_code, upload_cv_to_s3
from covise_app.user_context import build_profile_card_context, build_profile_context, build_settings_context, build_ui_user_context
from covise_app.profile_sync import PROFILE_ONBOARDING_FIELD_IDS, sync_profile_for_user
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required


logger = logging.getLogger(__name__)


def _as_bool(value):
    return str(value).strip().lower() == "true"


def _split_pipe_list(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]


def _record_successful_sign_in(user):
    user.sign_in_count = (user.sign_in_count or 0) + 1
    user.save(update_fields=["sign_in_count"])


def _display_value(value, fallback=""):
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts)
    if isinstance(value, dict):
        parts = [str(item).strip() for item in value.values() if str(item).strip()]
        return ", ".join(parts)
    return str(value).strip() if value else fallback


def _top_skill_labels(value, limit=3):
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, dict):
        items = [str(item).strip() for item in value.values() if str(item).strip()]
    elif value:
        items = [str(value).strip()]
    else:
        items = []

    deduped = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:limit]


def _relative_time_label(value):
    if not value:
        return "New"

    delta = timesince(value)
    if not delta:
        return "Right Now"

    first_part = delta.split(",")[0].strip().lower()
    if first_part.startswith("0 "):
        return "Right Now"

    return f"{first_part} ago"


def _build_post_feed_title(post):
    explicit_title = " ".join((getattr(post, "title", "") or "").split())
    if explicit_title:
        return explicit_title

    raw_text = " ".join((post.content or "").split())
    if not raw_text:
        return post.get_post_type_display()
    sentence_break = raw_text.find(". ")
    title_source = raw_text if sentence_break == -1 else raw_text[:sentence_break + 1]
    return (title_source[:110].rstrip() + "…") if len(title_source) > 110 else title_source


def _post_theme_class(post):
    theme_color = (getattr(post, "theme_color", "") or Post.ThemeColor.DEFAULT).strip()
    valid_theme_colors = {choice for choice, _label in Post.ThemeColor.choices}
    if theme_color not in valid_theme_colors:
        theme_color = Post.ThemeColor.DEFAULT
    return f"post-tone-{theme_color}"


def _conversation_partner(conversation, current_user):
    for participant in conversation.participants.all():
        if participant.pk != current_user.pk:
            return participant
    return current_user


def _find_existing_private_conversation(user_a, user_b):
    return (
        Conversation.objects.filter(conversation_type=Conversation.ConversationType.PRIVATE, participants=user_a)
        .filter(participants=user_b)
        .annotate(participant_count=Count("participants"))
        .filter(participant_count=2)
        .distinct()
        .first()
    )


def _get_or_create_private_conversation(user_a, user_b):
    conversation = _find_existing_private_conversation(user_a, user_b)
    if conversation:
        return conversation

    conversation = Conversation.objects.create(
        conversation_type=Conversation.ConversationType.PRIVATE,
        created_by=user_a,
    )
    conversation.participants.add(user_a, user_b)
    return conversation


def _serialize_message(message):
    sender_name = message.sender.full_name or message.sender.email
    return {
        "id": str(message.id),
        "sender_id": str(message.sender_id),
        "sender_name": sender_name,
        "text": message.body,
        "created_at": message.created_at.isoformat(),
    }


def _serialize_conversation(conversation, current_user):
    partner = _conversation_partner(conversation, current_user)
    partner_profile = getattr(partner, "profile", None)
    messages = list(conversation.messages.select_related("sender").order_by("created_at"))
    last_message = messages[-1] if messages else None
    status = _display_value(getattr(partner_profile, "current_role", None), "Private conversation")
    return {
        "id": str(conversation.id),
        "name": partner.full_name or partner.email,
        "avatar": partner.avatar_initials,
        "preview": last_message.body if last_message else "Start the conversation",
        "time": _relative_time_label(last_message.created_at) if last_message else "New",
        "unread": 0,
        "online": False,
        "match": "Private conversation",
        "status": status,
        "matchedOn": conversation.created_at.strftime("%B %d, %Y"),
        "userType": _display_value(getattr(partner_profile, "user_type", None), "CoVise member"),
        "industry": _display_value(getattr(partner_profile, "industry", None), "Not added yet"),
        "stage": _display_value(getattr(partner_profile, "stage", None), "Not added yet"),
        "mutual": 0,
        "pinned": "",
        "messages": [_serialize_message(message) for message in messages],
    }


def _serialize_conversation_request(request_item, current_user):
    is_incoming = request_item.recipient_id == current_user.id
    other_user = request_item.requester if is_incoming else request_item.recipient
    other_profile = getattr(other_user, "profile", None)
    description = _display_value(getattr(other_profile, "one_liner", None), "Wants to start a private conversation.")
    if not description:
        description = "Wants to start a private conversation."
    return {
        "id": str(request_item.id),
        "name": other_user.full_name or other_user.email,
        "avatar": other_user.avatar_initials,
        "description": description,
        "is_incoming": is_incoming,
        "status": request_item.status,
    }



def _load_boarding_flow():
    flow_path = Path(__file__).resolve().parent / "boarding.json"
    try:
        # Use utf-8-sig so a BOM in boarding.json does not break JSON parsing.
        with flow_path.open(encoding="utf-8-sig") as f:
            flow = json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.exception("Failed to load boarding.json: %s", exc)
        return None, "We are having trouble loading onboarding right now. Please try another time."

    if not isinstance(flow, dict) or not isinstance(flow.get("steps"), list):
        logger.error("Invalid boarding.json structure")
        return None, "We are having trouble loading onboarding right now. Please try another time."

    return flow, None


def _project_card_context(project):
    owner_name = project.founder_name or "CoVise Founder"
    if project.user and project.user.full_name:
        owner_name = project.user.full_name

    owner_initials = project.founder_initials or "CV"
    if project.user and getattr(project.user, "avatar_initials", ""):
        owner_initials = project.user.avatar_initials

    filter_tokens = list(project.filter_tokens or [])
    if project.stage:
        filter_tokens.append(str(project.stage).strip().lower().replace(" ", "-"))

    positions_text = " ".join(project.positions_needed or []).lower()
    if "co-founder" in positions_text or "cofounder" in positions_text:
        filter_tokens.append("seeking-co-founder")
    if "investor" in positions_text:
        filter_tokens.append("seeking-investor")
    if "operator" in positions_text or "operations" in positions_text:
        filter_tokens.append("seeking-operator")

    deduped_filters = []
    for token in filter_tokens:
        normalized = str(token).strip().lower()
        if normalized and normalized not in deduped_filters:
            deduped_filters.append(normalized)

    return {
        "slug": project.slug,
        "owner_user_id": project.user_id,
        "code": project.code,
        "title": project.title,
        "founder_name": owner_name,
        "founder_initials": owner_initials,
        "city": project.city,
        "country": project.country,
        "relative_time": f"{timesince(project.published_at)} ago" if project.published_at else "Recently added",
        "description": project.card_description or project.overview,
        "stage": project.stage,
        "sector": project.sector,
        "founder_commitment": project.founder_commitment,
        "capital_status": project.capital_status,
        "positions_needed": project.positions_needed[:3],
        "skills_needed": project.skills_needed[:3],
        "team_members_filled": project.team_members_filled,
        "team_size_target": project.team_size_target,
        "team_progress_percent": project.team_progress_percent,
        "alignment_score": project.alignment_score,
        "data_filters": " ".join(deduped_filters),
        "data_search": project.search_text or " ".join(
            bit for bit in [
                project.title,
                project.code,
                project.founder_name,
                project.city,
                project.country,
                project.sector,
                project.stage,
                project.founder_commitment,
                project.capital_status,
                " ".join(project.positions_needed or []),
                " ".join(project.skills_needed or []),
                " ".join(project.filter_tokens or []),
                project.slug,
            ] if bit
        ),
        "alignment_json": json.dumps(project.alignment_details or {"aspects": [], "summary": ""}),
    }

# Create your views here.
def landing(request):
    return render(request, 'landing.html')

@login_required
def home(request):
    if not request.user.is_authenticated:
        return HttpResponsePermanentRedirect(reverse('Landing Page'))

    posts = list(
        Post.objects.select_related("user", "user__profile").prefetch_related("comments__user").order_by("-created_at")
    )
    for post in posts:
        post.feed_title = _build_post_feed_title(post)
        post.feed_skills = _top_skill_labels(getattr(getattr(post.user, "profile", None), "skills", None))
        post.theme_class = _post_theme_class(post)
        post.relative_time = _relative_time_label(post.created_at)

    full_name = (request.user.full_name or "").strip()
    first_name = full_name.split()[0] if full_name else "User"
    profile = getattr(request.user, "profile", None)
    raw_skills = getattr(profile, "skills", None) if profile else []
    tags = set(raw_skills or [])
    response = render(request, 'home.html', {
        "posts": posts,
        "first_name": first_name,
        "tags": tags,
    })
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@login_required
def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("user").prefetch_related("comments__user"),
        id=post_id,
    )
    post.feed_title = _build_post_feed_title(post)
    post.theme_class = _post_theme_class(post)
    post.relative_time = _relative_time_label(post.created_at)
    response = render(request, "post_detail.html", {"post": post})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@login_required
def add_comment(request, post_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    post = Post.objects.filter(id=post_id).first()
    if not post:
        return JsonResponse({"error": "Post not found"}, status=404)

    payload = json.loads(request.body or "{}")
    content = str(payload.get("content", "")).strip()
    if not content:
        return JsonResponse({"error": "Comment cannot be empty"}, status=400)

    comment = Comment.objects.create(
        user=request.user,
        post=post,
        content=content,
    )
    post.comments_number = post.comments.count()
    post.save(update_fields=["comments_number"])

    return JsonResponse({
        "comment": {
            "id": comment.id,
            "user_id": request.user.id,
            "author": request.user.full_name or request.user.email,
            "avatar_initials": request.user.avatar_initials,
            "content": comment.content,
            "created_at": "just now",
        },
        "comments_count": post.comments_number,
    })


@login_required
def create_post(request):
    full_name = (request.user.full_name or "").strip()
    first_name = full_name.split()[0] if full_name else "User"

    context = {
        "first_name": first_name,
        "post_type_choices": Post.PostType.choices,
        "form_data": {
            "title": "",
            "post_type": Post.PostType.UPDATE,
            "theme_color": Post.ThemeColor.DEFAULT,
            "content": "",
        },
    }

    if request.method != "POST":
        response = render(request, "create_post.html", context)
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    title = request.POST.get("title", "").strip()
    post_type = request.POST.get("post_type", Post.PostType.UPDATE).strip()
    theme_color = request.POST.get("theme_color", Post.ThemeColor.DEFAULT).strip()
    content = request.POST.get("content", "").strip()
    image = request.FILES.get("image")

    context["form_data"] = {
        "title": title,
        "post_type": post_type,
        "theme_color": theme_color,
        "content": content,
    }

    valid_post_types = {choice for choice, _label in Post.PostType.choices}
    valid_theme_colors = {choice for choice, _label in Post.ThemeColor.choices}
    if not title or not content:
        context["error_message"] = "Title and post content are required."
        return render(request, "create_post.html", context, status=400)

    if post_type not in valid_post_types:
        context["error_message"] = "Select a valid post type."
        return render(request, "create_post.html", context, status=400)

    if theme_color not in valid_theme_colors:
        theme_color = Post.ThemeColor.DEFAULT

    post = Post.objects.create(
        user=request.user,
        title=title,
        post_type=post_type,
        theme_color=theme_color,
        image=image,
        content=content,
    )
    return redirect("Post Detail", post_id=post.id)

@login_required
def messages(request):
    conversations = list(
        Conversation.objects.filter(participants=request.user)
        .prefetch_related("participants__profile", "messages__sender")
        .order_by("-last_message_at", "-updated_at")
        .distinct()
    )
    serialized_conversations = [_serialize_conversation(conversation, request.user) for conversation in conversations]
    conversation_requests = list(
        ConversationRequest.objects.filter(Q(requester=request.user) | Q(recipient=request.user), status=ConversationRequest.Status.PENDING)
        .select_related("requester__profile", "recipient__profile")
    )
    serialized_requests = [_serialize_conversation_request(item, request.user) for item in conversation_requests]

    requested_conversation_id = request.GET.get("conversation", "").strip()
    active_conversation_id = ""
    if requested_conversation_id and any(item["id"] == requested_conversation_id for item in serialized_conversations):
        active_conversation_id = requested_conversation_id
    elif serialized_conversations:
        active_conversation_id = serialized_conversations[0]["id"]

    return render(
        request,
        'messages.html',
        {
            "conversation_data": serialized_conversations,
            "conversation_requests": serialized_requests,
            "active_conversation_id": active_conversation_id,
        },
    )


@login_required
@require_POST
def start_private_conversation(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise Http404("User not found")
    if target_user == request.user:
        return redirect("Messages")
    if not _can_view_profile(request.user, target_user):
        raise Http404("Profile not available")

    existing_conversation = _find_existing_private_conversation(request.user, target_user)
    if existing_conversation:
        return redirect(f"{reverse('Messages')}?conversation={existing_conversation.id}")

    existing_request = (
        ConversationRequest.objects.filter(
            Q(requester=request.user, recipient=target_user) | Q(requester=target_user, recipient=request.user),
            status=ConversationRequest.Status.PENDING,
        )
        .distinct()
        .first()
    )
    if not existing_request:
        ConversationRequest.objects.create(
            requester=request.user,
            recipient=target_user,
        )
    return redirect("Messages")


@login_required
@require_POST
def respond_to_conversation_request(request, request_id, action):
    request_item = ConversationRequest.objects.filter(
        id=request_id,
        recipient=request.user,
        status=ConversationRequest.Status.PENDING,
    ).first()
    if not request_item:
        raise Http404("Request not found")

    if action == "accept":
        conversation = _get_or_create_private_conversation(request_item.requester, request_item.recipient)
        request_item.status = ConversationRequest.Status.ACCEPTED
        request_item.conversation = conversation
        request_item.responded_at = timezone.now()
        request_item.save(update_fields=["status", "conversation", "responded_at"])
        return JsonResponse({"ok": True, "conversation_id": str(conversation.id)})

    if action == "decline":
        request_item.status = ConversationRequest.Status.DECLINED
        request_item.responded_at = timezone.now()
        request_item.save(update_fields=["status", "responded_at"])
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "Invalid action"}, status=400)

@login_required
def projects(request):
    response = render(request, "coming_soon.html", {"page_name": "Projects"})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@login_required
def project_detail(request, project_slug):
    project = Project.objects.filter(slug=project_slug, is_active=True).first()
    if not project:
        raise Http404("Project not found")

    score = project.alignment_score
    if score >= 85:
        alignment_band = "high"
    elif score >= 70:
        alignment_band = "medium"
    else:
        alignment_band = "low"

    context = {
        "project": project,
        "alignment_band": alignment_band,
    }
    return render(request, "project_detail.html", context)

def _can_view_profile(viewer, target_user):
    if viewer == target_user:
        return True

    preferences = getattr(target_user, "preferences", None)
    visibility = getattr(preferences, "profile_visibility", "everyone")

    if visibility == "nobody":
        return False
    if visibility == "matched_only":
        return False
    return True


def _render_profile_page(request, target_user, is_own_profile):
    profile_page = build_profile_context(target_user)
    preferences = profile_page.get("preferences", {})
    can_view_profile_data = is_own_profile or preferences.get("read_profile_data", True)
    target_profile = getattr(target_user, "profile", None)
    onboarding_prompts = {
        "headline": "Complete your profile so CoVise can introduce you to stronger matches.",
        "location": "Add your location",
        "what_im_building": "Add your one-liner and market focus to show founders what you're building.",
        "looking_for": "Add the skills, commitment, and collaborator type you are looking for.",
    }

    if not can_view_profile_data:
        profile_page["headline"] = "This user prefers to keep their profile details private."
        profile_page["location"] = "Private"
        profile_page["what_im_building"] = ""
        profile_page["what_im_building_tags"] = []
        profile_page["looking_for"] = ""
        profile_page["looking_for_tags"] = []
    elif not is_own_profile:
        if not target_profile:
            profile_page["headline"] = "This user has not added public profile details yet."
            profile_page["location"] = "Location not shared"
            profile_page["what_im_building"] = "No public project summary yet."
            profile_page["what_im_building_tags"] = []
            profile_page["looking_for"] = "No collaborator preferences shared yet."
            profile_page["looking_for_tags"] = []
            profile_page["conviction_title"] = "Profile details limited"
            profile_page["conviction_sub"] = "This user has not added enough public profile data yet."
        else:
            if not profile_page.get("headline") or profile_page.get("headline") == onboarding_prompts["headline"]:
                profile_page["headline"] = "This user has not added a public bio yet."
            if not profile_page.get("location") or profile_page.get("location") == onboarding_prompts["location"]:
                profile_page["location"] = "Location not shared"
            if not profile_page.get("what_im_building") or profile_page.get("what_im_building") == onboarding_prompts["what_im_building"]:
                profile_page["what_im_building"] = "No public project summary yet."
                profile_page["what_im_building_tags"] = []
            if not profile_page.get("looking_for") or profile_page.get("looking_for") == onboarding_prompts["looking_for"]:
                profile_page["looking_for"] = "No collaborator preferences shared yet."
                profile_page["looking_for_tags"] = []
            if not profile_page.get("conviction_score"):
                profile_page["conviction_title"] = "Profile details limited"
                profile_page["conviction_sub"] = "This user has not added enough public profile data yet."

    context = {
        "ui_user": build_ui_user_context(target_user),
        "viewed_user_id": target_user.id,
        "profile_page": profile_page,
        "experiences": target_user.experiences.all() if can_view_profile_data else target_user.experiences.none(),
        "active_projects": target_user.active_projects.all() if can_view_profile_data else target_user.active_projects.none(),
        "posts": target_user.posts.all() if can_view_profile_data else target_user.posts.none(),
        "is_own_profile": is_own_profile,
        "profile_read_only": not is_own_profile,
        "can_view_profile_data": can_view_profile_data,
    }
    return render(request, "profile.html", context)


@login_required
def profile(request):
    return _render_profile_page(request, request.user, True)


@login_required
def public_profile(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise Http404("User not found")
    if not _can_view_profile(request.user, target_user):
        raise Http404("Profile not available")
    return _render_profile_page(request, target_user, request.user == target_user)


@login_required
def post_action (request, comment_id, action):
    if request.method == "POST":
        comment = Comment.objects.get(id=comment_id)
        reaction_type = None
        if action == "upvote":
            reaction_type = CommentReaction.ReactionType.UP
        elif action == "downvote":
            reaction_type = CommentReaction.ReactionType.DOWN
        else:
            return JsonResponse({"error": "Invalid action"}, status=400)

        existing_reaction = CommentReaction.objects.filter(
            user=request.user,
            comment=comment,
        ).first()

        if existing_reaction and existing_reaction.reaction == reaction_type:
            existing_reaction.delete()
        elif existing_reaction:
            existing_reaction.reaction = reaction_type
            existing_reaction.save(update_fields=["reaction"])
        else:
            CommentReaction.objects.create(
                user=request.user,
                comment=comment,
                reaction=reaction_type,
            )

        reaction_totals = comment.reactions.aggregate(
            upvotes=Count("id", filter=Q(reaction=CommentReaction.ReactionType.UP)),
            downvotes=Count("id", filter=Q(reaction=CommentReaction.ReactionType.DOWN)),
        )
        comment.up = reaction_totals["upvotes"] or 0
        comment.down = reaction_totals["downvotes"] or 0
        comment.save()
        user_reaction = CommentReaction.objects.filter(
            user=request.user,
            comment=comment,
        ).values_list("reaction", flat=True).first()
        return JsonResponse({
            "upvotes": comment.up,
            "downvotes": comment.down,
            "user_reaction": user_reaction,
        })
    return JsonResponse({"error": "Invalid request"}, status=400)



@login_required
def profile_card(request):
    return render(request, 'profile_card.html', {
        'profile_card': build_profile_card_context(request.user),
    })
@login_required
def map_view(request):
    return render(request, 'map.html')
@login_required
def chatbot(request):
    response = render(request, "coming_soon.html", {"page_name": "CoVise Advisor"})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
@login_required
def settings(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    preferences, _ = UserPreference.objects.get_or_create(user=request.user)

    user = request.user
    context = {}

    print(request.method)

    if request.method == "POST":
        print ("save_section ",request.POST.get("save_section"))

        try:
            if request.POST.get("save_section") == "personal_data":
                email=request.POST.get("email", "").strip()
                phone_number=request.POST.get("phone_number", "").strip()
                if email and email != user.email:
                    if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                        context["settings_page"] = build_settings_context(request.user)
                        context["error_message"] = "This email is already registered on CoVise. Please sign in instead."
                        context["save_success"] = False
                        return render(request, "settings.html", context)
                    user.email = email
                    user.save(update_fields=["email"])

                print ("phone_number ",request.POST.get("phone_number"))

                profile.phone_number = phone_number
                profile.save(update_fields=["phone_number"])

                print("Saved phone number in profile :", profile.phone_number)

            if request.POST.get("save_section") == "professional_data":
                linkedin=request.POST.get("linkedin", "").strip()
                github=request.POST.get("github", "").strip()
                proof_of_work_url=request.POST.get("proof_of_work_url", "").strip()
                location=request.POST.get("location", "").strip()
                nationality=request.POST.get("nationality", "").strip()
                bio=request.POST.get("bio", "").strip()

                profile.linkedin = linkedin
                profile.github = github
                profile.proof_of_work_url = proof_of_work_url
                profile.country = location
                profile.nationality = nationality
                profile.bio = bio
                profile.save(update_fields=["linkedin", "github", "proof_of_work_url", "country", "nationality", "bio"])

            if request.POST.get("save_section")=="experiences":
                title=request.POST.get("title", "").strip()
                date=request.POST.get("date", "").strip()
                desc=request.POST.get("desc", "").strip()
                Experiences.objects.create(
                    user=request.user,
                    title=title,
                    date=date,
                    desc=desc,
                )

            if request.POST.get("save_section")=="projects":
                name=request.POST.get("name", "").strip()
                status=request.POST.get("status", "").strip()
                desc=request.POST.get("desc", "").strip()
                Active_projects.objects.create(
                    user=request.user,
                    name=name,
                    status=status,
                    desc=desc,
                )

            if request.POST.get("save_section") == "profile_preferences":
                profile_visibility = request.POST.get("profile_visibility")
                show_conviction_score = request.POST.get("show_conviction_score")
                show_cv_to_matches = request.POST.get("show_cv_to_matches")
                show_linkedin_to_matches = request.POST.get("show_linkedin_to_matches")
                appear_in_search= request.POST.get("appear_in_search")
                pause_matching = request.POST.get("pause_matching")
                if profile_visibility:
                    preferences.profile_visibility = profile_visibility
                preferences.show_conviction_score = _as_bool(show_conviction_score)
                preferences.show_cv_to_matches = _as_bool(show_cv_to_matches)
                preferences.show_linkedin_to_matches = _as_bool(show_linkedin_to_matches)
                preferences.appear_in_search = _as_bool(appear_in_search)
                preferences.pause_matching = _as_bool(pause_matching)
                preferences.save(update_fields=["profile_visibility", "show_conviction_score", "show_cv_to_matches", "show_linkedin_to_matches", "appear_in_search", "pause_matching"])

            if request.POST.get("save_section") == "ai_preferences":
                ai_enabled = request.POST.get("ai_enabled")
                read_profile_data = request.POST.get("read_profile_data")
                ai_read_messages = request.POST.get("ai_read_messages")
                ai_read_workspace = request.POST.get("ai_read_workspace")
                ai_post_updates = request.POST.get("ai_post_updates")
                ai_send_messages = request.POST.get("ai_send_messages")
                ai_edit_workspace = request.POST.get("ai_edit_workspace")
                ai_manage_milestones = request.POST.get("ai_manage_milestones")

                preferences.ai_enabled = _as_bool(ai_enabled)
                preferences.read_profile_data = _as_bool(read_profile_data)
                preferences.ai_read_messages = _as_bool(ai_read_messages)
                preferences.ai_read_workspace = _as_bool(ai_read_workspace)
                preferences.ai_post_updates = _as_bool(ai_post_updates)
                preferences.ai_send_messages = _as_bool(ai_send_messages)
                preferences.ai_edit_workspace = _as_bool(ai_edit_workspace)
                preferences.ai_manage_milestones = _as_bool(ai_manage_milestones)
                preferences.save(update_fields=["ai_enabled", "read_profile_data", "ai_read_messages", "ai_read_workspace", "ai_post_updates", "ai_send_messages", "ai_edit_workspace", "ai_manage_milestones"])

            if request.POST.get("save_section") == "notifications":
                email_frequency = request.POST.get("email_frequency")
                email_new_match = request.POST.get("email_new_match")
                email_new_message = request.POST.get("email_new_message")
                email_connection_request = request.POST.get("email_connection_request")
                email_request_accepted = request.POST.get("email_request_accepted")
                email_milestone_reminder = request.POST.get("email_milestone_reminder")
                email_workspace_activity = request.POST.get("email_workspace_activity")
                email_platform_updates = request.POST.get("email_platform_updates")
                email_marketing = request.POST.get("email_marketing")
                in_app_new_match = request.POST.get("in_app_new_match")
                in_app_new_message = request.POST.get("in_app_new_message")
                in_app_connection_request = request.POST.get("in_app_connection_request")
                in_app_request_accepted = request.POST.get("in_app_request_accepted")
                in_app_milestone_reminder = request.POST.get("in_app_milestone_reminder")
                in_app_workspace_activity = request.POST.get("in_app_workspace_activity")
                in_app_platform_updates = request.POST.get("in_app_platform_updates")
                in_app_marketing = request.POST.get("in_app_marketing")

                if email_frequency:
                    preferences.email_frequency = email_frequency
                preferences.email_new_match = _as_bool(email_new_match)
                preferences.email_new_message = _as_bool(email_new_message)
                preferences.email_connection_request = _as_bool(email_connection_request)
                preferences.email_request_accepted = _as_bool(email_request_accepted)
                preferences.email_milestone_reminder = _as_bool(email_milestone_reminder)
                preferences.email_workspace_activity = _as_bool(email_workspace_activity)
                preferences.email_platform_updates = _as_bool(email_platform_updates)
                preferences.email_marketing = _as_bool(email_marketing)
                preferences.in_app_new_match = _as_bool(in_app_new_match)
                preferences.in_app_new_message = _as_bool(in_app_new_message)
                preferences.in_app_connection_request = _as_bool(in_app_connection_request)
                preferences.in_app_request_accepted = _as_bool(in_app_request_accepted)
                preferences.in_app_milestone_reminder = _as_bool(in_app_milestone_reminder)
                preferences.in_app_workspace_activity = _as_bool(in_app_workspace_activity)
                preferences.in_app_platform_updates = _as_bool(in_app_platform_updates)
                preferences.in_app_marketing = _as_bool(in_app_marketing)
                preferences.save(update_fields=["email_frequency", "email_new_match", "email_new_message", "email_connection_request", "email_request_accepted", "email_milestone_reminder", "email_workspace_activity", "email_platform_updates", "email_marketing", "in_app_new_match", "in_app_new_message", "in_app_connection_request", "in_app_request_accepted", "in_app_milestone_reminder", "in_app_workspace_activity", "in_app_platform_updates", "in_app_marketing"])

            if request.POST.get("save_section") == "matching_preferences":
                preferred_cofounder_types = request.POST.get("preferred_cofounder_types")
                preferred_industries = request.POST.get("preferred_industries")
                preferred_gcc_markets = request.POST.get("preferred_gcc_markets")
                minimum_commitment = request.POST.get("minimum_commitment")
                open_to_foreign_founders = request.POST.get("open_to_foreign_founders")
                pause_matching = request.POST.get("pause_matching")
                preferences.preferred_cofounder_types = _split_pipe_list(preferred_cofounder_types)
                preferences.preferred_industries = _split_pipe_list(preferred_industries)
                preferences.preferred_gcc_markets = _split_pipe_list(preferred_gcc_markets)
                if minimum_commitment:
                    preferences.minimum_commitment = minimum_commitment
                preferences.open_to_foreign_founders = _as_bool(open_to_foreign_founders)
                preferences.pause_matching = _as_bool(pause_matching)
                preferences.save(update_fields=["preferred_cofounder_types", "pause_matching", "preferred_industries", "preferred_gcc_markets", "minimum_commitment", "open_to_foreign_founders"])

            return redirect(f"{reverse('Settings')}?saved=1")
        except Exception:
            return redirect(f"{reverse('Settings')}?saved=2")

    context["settings_page"] = build_settings_context(request.user)
    if request.GET.get("saved") == "1":
        context["success_message"] = "Saved successfully."
        context["save_success"] = True
    if request.GET.get("saved") == "2":
        context["error_message"] = "An error occurred while saving. Please try again."
        context["save_success"] = False
    return render(request, 'settings.html', context)

def terms(request):
    return render(request, 'terms.html')

def privacy(request):
    return render(request, 'privacy.html')

def security(request):
    return render(request, 'security.html')

def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next')


    if request.method == 'GET':
        return render(request, 'login.html', {'next': next_url})
    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '').strip()
    context = {
        "form_data": {
            "email": email,
        }
    }
    if not email or not password:
        context["error_message"] = "Both email and password are required."
        return render(request, 'login.html', context, status=400)

    existing_user = User.objects.filter(email=email).first()
    if existing_user is None:
        approved_waitlist_entry = WaitlistEntry.objects.filter(
            email=email,
            status=WaitlistEntry.Status.APPROVED,
        ).first()
        if approved_waitlist_entry is not None:
            context["error_message"] = "Your email is approved. Create your account from sign in first."
        else:
            context["error_message"] = "This is a private community. You can only access it if your application has been approved. Please request access to become a member."
        return render(request, 'login.html', context, status=400)

    user = authenticate(request, email=email, password=password)
    if user is None:
        context["error_message"] = "Incorrect password. Please try again."
        return render(request, 'login.html', context, status=400)

    if not hasattr(user, "profile"):
        sync_profile_for_user(user)
    UserPreference.objects.get_or_create(user=user)
    login(request, user)
    _record_successful_sign_in(user)
    return redirect(next_url or "Home")


def signin(request):
    if request.method != 'POST':
        return render(request, 'signin.html')
    
    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '').strip()
    confirm_password = request.POST.get('confirm_password', '').strip()
    context = {
        "form_data": {
            "email": email,
        }
    }
    if not email or not password or not confirm_password:
        context["error_message"] = "All fields are required."
        return render(request, 'signin.html', context, status=400)
    
    if User.objects.filter(email=email).exists():
        context["error_message"] = "This email is already registered on CoVise. Please log in instead."
        return render(request, 'signin.html', context, status=400)
    
    approved_waitlist_entry = WaitlistEntry.objects.filter(
        email=email,
        status=WaitlistEntry.Status.APPROVED,
    ).first()
    if approved_waitlist_entry is None:
        context["error_message"] = "This email is not registered in CoVise or has not been approved yet. Please request access to become a member."
        return render(request, 'signin.html', context, status=400)
    
    if password != confirm_password:
        context["error_message"] = "Passwords do not match."
        return render(request, 'signin.html', context, status=400)
    
    if password and len(password) < 8:
        context["error_message"] = "Passwords must be at least 8 characters long."
        return render(request, 'signin.html', context, status=400)


    try:
        user = User.objects.create_user(
            email=email,
            full_name=approved_waitlist_entry.full_name,
            password=password,
        )
    except IntegrityError: #this error raises when there is a duplicate email in the database due to the unique constraint on the email field
        context["error_message"] = "This email is already registered on CoVise. Please log in instead."
        return render(request, 'signin.html', context, status=400)

    sync_profile_for_user(user, waitlist_entry=approved_waitlist_entry)
    UserPreference.objects.get_or_create(user=user)
    if approved_waitlist_entry.status != WaitlistEntry.Status.ACTIVATED:
        approved_waitlist_entry.status = WaitlistEntry.Status.ACTIVATED
        approved_waitlist_entry.save(update_fields=["status"])
    user = authenticate(request, email=email, password=password)
    if user is None:
        context["error_message"] = "Your account was created, but we could not sign you in automatically. Please try logging in."
        return render(request, 'signin.html', context, status=500)
    login(request, user)
    _record_successful_sign_in(user)
    return redirect("Home")


def onboarding_final(request):
    return render(request, 'onboarding-final.html')


@ensure_csrf_cookie
def onboarding(request):
    flow, onboarding_error_message = _load_boarding_flow()
    onboarding_unavailable = flow is None
    initial_answers = {}
    if request.session.get("waitlist_email"):
        initial_answers["email"] = request.session["waitlist_email"]
    return render(
        request,
        'onboarding.html',
        {
            'boarding_flow': flow,
            'onboarding_initial_answers': initial_answers,
            'onboarding_unavailable': onboarding_unavailable,
            'onboarding_error_message': onboarding_error_message,
        },
    )


def onboarding_submit(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return JsonResponse({"error": "answers must be an object."}, status=400)

    flow_name = str(payload.get("flow_name", "")).strip()
    email = str(answers.get("email", "")).strip() or str(request.session.get("waitlist_email", "")).strip()
    if not email:
        return JsonResponse({"error": "Email is required to save onboarding."}, status=400)

    waitlist_id = request.session.get("waitlist_entry_id")
    waitlist_entry = WaitlistEntry.objects.filter(pk=waitlist_id).first() if waitlist_id else None
    if waitlist_entry is None:
        return JsonResponse(
            {"error": "Waitlist session expired or missing. Please restart from the waitlist form."},
            status=400,
        )

    onboarding_defaults = {field_id: answers.get(field_id) for field_id in PROFILE_ONBOARDING_FIELD_IDS}

    # Link referral if user entered a valid code
    entered_code = str(answers.get("referral_code", "")).strip().upper()
    if entered_code:
        referrer = WaitlistEntry.objects.filter(my_referral_code=entered_code).exclude(pk=waitlist_entry.pk).first()
        if referrer and not waitlist_entry.referred_by_id:
            waitlist_entry.referred_by = referrer
            waitlist_entry.save(update_fields=["referred_by"])

    onboarding_response, _ = OnboardingResponse.objects.update_or_create(
        waitlist_entry=waitlist_entry,
        defaults={
            "email": waitlist_entry.email or email,
            "flow_name": flow_name[:200],
            **onboarding_defaults,
            "answers": answers,
        },
    )

    user = User.objects.filter(email=waitlist_entry.email or email).first()
    if user:
        sync_profile_for_user(
            user,
            waitlist_entry=waitlist_entry,
            onboarding_response=onboarding_response,
            flow_name=flow_name[:200],
            answers=answers,
        )

    return JsonResponse({"ok": True})

def loading(request):
    return render(request, 'loading.html')

def pricing(request):
    return render(request, 'pricing.html')

def features(request):
    return render(request, 'features.html')

def about(request):
    return render(request, 'about.html')
@login_required
def workspace(request):
    response = render(request, "coming_soon.html", {"page_name": "Workspace"})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response

@ensure_csrf_cookie
def waitlist(request):
    context = {}

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        country = request.POST.get('country', '').strip()
        non_gcc_business = request.POST.get('non_gcc_business') == 'on'
        no_linkedin = request.POST.get('no_linkedin') == 'on'
        custom_country = request.POST.get('custom_country', '').strip()
        linkedin = request.POST.get('linkedin', '').strip()
        cv_file = request.FILES.get('cv')

        print(
            f"[waitlist] POST received email={email!r} country={country!r} "
            f"non_gcc_business={non_gcc_business} no_linkedin={no_linkedin} "
            f"has_cv={bool(cv_file)}"
        )

        linkedin_missing_when_required = (not no_linkedin) and (not linkedin)
        cv_missing_when_required = no_linkedin and (not cv_file)

        if not all([full_name, phone_number, email]) or linkedin_missing_when_required or cv_missing_when_required:
            context['error_message'] = 'Please complete all required fields.'
            print(
                "[waitlist] validation failed: required fields missing "
                f"(full_name={bool(full_name)} phone_number={bool(phone_number)} "
                f"email={bool(email)} linkedin_required_missing={linkedin_missing_when_required} "
                f"cv_required_missing={cv_missing_when_required})"
            )
        elif non_gcc_business and not custom_country:
            context['error_message'] = 'Please enter your country if you are outside the GCC.'
            print("[waitlist] validation failed: non-GCC checked but custom_country is empty")
        elif not non_gcc_business and not country:
            context['error_message'] = 'Please select your country.'
            print("[waitlist] validation failed: GCC country not selected")
        else:
            if non_gcc_business:
                country = ''
            else:
                custom_country = ''

            if WaitlistEntry.objects.filter(email=email).exists():
                context['error_message'] = 'This email is already registered on CoVise.'
                print(f"[waitlist] duplicate email blocked before create for email={email!r}")
                return render(request, 'waitlist.html', context)

            # Upload CV before DB retry loop — file object is exhausted after first read
            cv_s3_key = None
            if cv_file:
                cv_s3_key = upload_cv_to_s3(cv_file, email)
                if cv_s3_key is None:
                    logger.warning("[waitlist] S3 upload failed for %s", email)

            referral_code = generate_referral_code()

            entry = None
            for attempt in range(2):
                try:
                    entry = WaitlistEntry.objects.create(
                        full_name=full_name,
                        phone_number=phone_number,
                        email=email,
                        country=country,
                        non_gcc_business=non_gcc_business,
                        custom_country=custom_country,
                        linkedin=linkedin,
                        cv_s3_key=cv_s3_key,
                        my_referral_code=referral_code,
                    )
                    break
                except IntegrityError:
                    context['error_message'] = 'This email is already registered on CoVise.'
                    print(f"[waitlist] duplicate email blocked by IntegrityError for email={email!r}")
                    return render(request, 'waitlist.html', context)
                except OperationalError:
                    # Handle transient DB disconnects (e.g., SSL EOF) by refreshing the connection once.
                    close_old_connections()
                    print(f"[waitlist] db OperationalError on attempt={attempt + 1} for email={email!r}")
                    if attempt == 1:
                        logger.exception("Failed to create waitlist entry after retry for %s", email)
                        context['error_message'] = 'Temporary database issue. Please try again in a moment.'

            if entry is None:
                print(f"[waitlist] render waitlist again after db failure for email={email!r}")
                return render(request, 'waitlist.html', context)
            user = User.objects.filter(email=email).first()
            if user:
                sync_profile_for_user(user, waitlist_entry=entry)
            request.session["waitlist_email"] = email
            request.session["waitlist_entry_id"] = entry.id
            request.session["my_referral_code"] = entry.my_referral_code
            print(f"[waitlist] success: redirecting to onboarding for email={email!r} entry_id={entry.id}")
            return redirect('Onboarding')

    return render(request, 'waitlist.html', context)


def waitlist_success(request):
    return render(request, 'waitlist_success.html', {
        'my_referral_code': request.session.get('my_referral_code', ''),
    })


def csrf_failure(request, reason=""):
    context = {"reason": reason}
    return render(request, "csrf_error.html", context, status=403)
