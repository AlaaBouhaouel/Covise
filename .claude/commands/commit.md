# Commit

Create a git commit for the current staged/unstaged changes.

1. Run `git status` and `git diff` to review all changes
2. Stage relevant files (avoid `.env`, `.dev.vars`, secrets)
3. Write a concise commit message in this format:
   - One-line summary (imperative mood, max 72 chars)
   - Examples: `fix mobile sidebar overflow on projects page`, `add alignment score eye popup`, `update light mode sidebar colors`
4. Run the Pre-Push Security Gate below before committing
5. Commit using:
```bash
git commit -m "your message"
```

Do NOT push unless the user explicitly asks.

---

## Pre-Push Security Gate (Mandatory Before Every git add/commit/push)

Run this check automatically before suggesting any git add, git commit, or git push.
Never skip. Never assume it is clean.

### Step 1 — Scan for Secret Leaks
```bash
git diff --cached --name-only
```
For each modified file, scan for these **INSTANT ABORT** triggers — stop immediately if found:
- Strings matching: `sk-*`, `AKIA*`, `aws_secret*`, `SECRET_KEY=`, `DATABASE_URL=postgresql://`, `password=`, `token=`, `api_key=`
- Any `.env` file staged
- Real email addresses hardcoded (not dummy data)
- Real phone numbers
- AWS credentials (access key ID starts with `AKIA`)
- Railway connection strings
- Private key or certificate content

### Step 2 — Check .gitignore is Protecting Sensitive Files
```bash
git status --short
```
These must **never** appear in git status output:
- `.env`, `.env.local`, `.env.production`
- `db.sqlite3`
- `*.pem`, `*.key`
- `__pycache__/`, `staticfiles/`, `media/`

If any appear: stop, add to `.gitignore`, run `git rm --cached filename`, then continue.

### Step 3 — Verify settings.py is Clean
- [ ] `SECRET_KEY = config('SECRET_KEY')` — not hardcoded
- [ ] `DEBUG = config('DEBUG', cast=bool)` — not hardcoded True
- [ ] `DATABASE_URL` comes from `config()` — not hardcoded
- [ ] AWS keys come from `config()` — not hardcoded
- [ ] `ALLOWED_HOSTS` does not contain `*` in production
- [ ] No email/payment credentials hardcoded

### Step 4 — Scan New Templates (.html)
- [ ] No API keys in `<script>` blocks
- [ ] No hardcoded real user data
- [ ] No AWS bucket names or S3 URLs hardcoded
- [ ] Django template variables used for dynamic data

### Step 5 — Scan New Static Files (.css/.js)
- [ ] No API keys in `fetch()` calls
- [ ] No hardcoded endpoints with credentials
- [ ] No internal service URLs exposed

### Files That Must Never Be Committed
- `covise/.env`
- `db.sqlite3`
- `covise/staticfiles/`
- Any file containing AWS access keys (`AKIA*`)
- Any file containing the actual `SECRET_KEY` value
- Any Railway connection string

### Pre-Push Checklist Output
Before every push suggestion, output this block:

```
PRE-PUSH SECURITY GATE
----------------------
Files being pushed: [list]

□ .env not staged
□ No hardcoded secrets in modified files
□ settings.py uses config() for all secrets
□ .gitignore protecting sensitive files
□ No AWS/Railway credentials in templates or JS

STATUS: CLEAN — safe to push
```
or
```
STATUS: BLOCKED — [what was found + fix required]
```

Never suggest `git push` without showing this block first.

### Emergency — If Secrets Were Already Pushed
1. STOP — do not push further
2. Rotate the leaked credential immediately (Railway DB URL / AWS IAM key / Django SECRET_KEY)
3. Update Railway environment variables with new values
4. Remove secret from git history: `git filter-branch` or BFG Repo Cleaner
5. Force push cleaned history
6. If AWS key leaked: check CloudTrail for unauthorized access immediately
