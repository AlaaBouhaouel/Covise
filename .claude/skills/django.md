---
name: django
description: CoVise backend mode. Activate when writing views, models, migrations, admin, S3 uploads, auth, settings, or any Django backend code.
---

# CoVise Backend Mode

## Project Constraints (Non-Negotiable)
- Django 5.2 LTS only
- Single settings.py (no config/ split — project is not that large)
- No DRF yet — server-rendered templates only
- No Celery, no Channels yet — not needed at current scale
- No new dependencies without justification
- Railway auto-deploys on push + runs migrations automatically
- Local dev: uvicorn only (runserver hangs due to StatReloader)

## What Claude Forgets or Gets Wrong

### ORM — High Deviation Risk
```python
# WRONG — Claude defaults to this
entries = WaitlistEntry.objects.all()
for e in entries:
    print(e.profile.user_type)  # N+1

# RIGHT
entries = WaitlistEntry.objects.select_related('profile').all()
```

- Always `select_related('profile')` when accessing OnboardingResponse
- Always `prefetch_related()` for any reverse FK or M2M
- Never filter in Python after `.all()` — filter in the queryset
- Never use `.values()` unless specific performance reason — breaks signals and type safety

### Migrations — High Deviation Risk
Claude frequently tries to run migrations against Railway's internal URL which always fails:
`"could not translate host name postgres.railway.internal"`

Correct behavior:
- Generate migration locally (`makemigrations` with empty `DATABASE_URL`)
- Push to GitHub
- Railway applies migration automatically on deploy
- Only use public Railway URL (`caboose.proxy.rlwy.net`) for emergency local migration runs

Never run `railway run python manage.py migrate` — overrides local env vars with Railway's internal URL.

### S3 — Established Pattern, Don't Deviate
- Upload utility exists in `covise_app/utils.py` — never bypass it
- Never save files to local filesystem
- Never store file content in database — always store `s3_key` (string) in PostgreSQL
- Always generate presigned URLs for downloads — never expose S3 bucket directly
- On S3 failure: log the error, set `s3_key = None`, continue — never block user registration over a failed CV upload

### Auth — Claude Defaults to Wrong Pattern
- Do NOT suggest django-allauth, dj-rest-auth, or JWT
- Use Django's built-in session auth only
- `@login_required` on every private view — Claude often forgets this
- Check object ownership before edit/delete — Claude skips this
- `LOGIN_URL = '/login/'` already set in settings

### Error Handling — Established Pattern
Always use the retry pattern from the waitlist view:
```python
for attempt in range(2):
    try:
        entry = Model.objects.create(...)
        break
    except OperationalError:
        close_old_connections()
        if attempt == 1:
            logger.exception("DB error for %s", identifier)
            context['error_message'] = 'Temporary issue. Try again.'
```

### Settings — Claude Hardcodes Things
Every new secret or config value must use:
```python
from decouple import config
NEW_VAR = config('NEW_VAR', default='')
```
Then add to Railway env vars AND local `.env`. Never hardcode values in `settings.py`.

### Admin — Claude Forgets to Register
Every new model needs admin registration:
```python
@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ['field1', 'created_at']
    search_fields = ['email']
    ordering = ['-created_at']
```

### Models — Baseline Claude Skips
Every new model must have:
```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)

def __str__(self):
    return f"{self.field} ({self.identifier})"

class Meta:
    ordering = ['-created_at']
```

Link everything back to `WaitlistEntry`:
- `OneToOneField` for profile data (already: `OnboardingResponse`)
- `ForeignKey` for workspace, posts, messages, projects
- Never orphan a model from the user identity

## Security Checklist
Run mentally before every view written:
- [ ] `@login_required` present?
- [ ] `{% csrf_token %}` in form?
- [ ] Input validated before use?
- [ ] `get_object_or_404()` used, not bare `.get()`?
- [ ] Ownership checked before edit/delete?
- [ ] No sensitive data in context or error message?
- [ ] S3 presigned URL expiry set (default 3600)?

## Self-Review Loop (Mandatory)

**CYCLE 1:**
- [ ] N+1 queries present?
- [ ] Missing select_related/prefetch_related?
- [ ] Security checklist passed?
- [ ] Migration needed?
- [ ] Admin registered?
- [ ] Established patterns followed (S3, error handling)?

Score /10 — fix if below 8

**CYCLE 2:**
- [ ] Did fixes introduce new issues?
- [ ] Edge cases handled (null, duplicate, empty)?
- [ ] `logger` used instead of `print()`?
- [ ] `settings.py` using `config()` not hardcoded?

Score /10 — only deliver if 8+

## Evolution
After any correction, append one line:
> [date] — [section]: [what Claude got wrong and correct pattern]
