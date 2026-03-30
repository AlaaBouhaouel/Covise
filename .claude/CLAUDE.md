# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Django Backend

```bash
cd C:\Users\AlaBo\Desktop\Covise\covise
C:\Users\AlaBo\Desktop\Covise\venv1\Scripts\python.exe manage.py runserver
# or without auto-reload:
C:\Users\AlaBo\Desktop\Covise\venv1\Scripts\python.exe manage.py runserver --noreload

# Database migrations
C:\Users\AlaBo\Desktop\Covise\venv1\Scripts\python.exe manage.py makemigrations
C:\Users\AlaBo\Desktop\Covise\venv1\Scripts\python.exe manage.py migrate
```

## Running the Frontend (Tldraw AI Agent)

```bash
npm run dev      # Vite dev server
npm run build    # Production build
```

## Architecture Overview

This is a **two-app monorepo**:

### 1. Django Web Platform (`covise/` + `covise_app/`)
The main user-facing platform for a startup/investor matchmaking service. All pages are server-rendered Django templates with vanilla JS and per-page CSS.

- **Templates:** `covise/templates/` — one HTML file per page (landing, home, project, messages, workspace, profile, settings, chatbot, onboarding, etc.)
- **CSS:** `covise/static/` — one CSS file per page (e.g. `home.css`, `requests.css` for projects page, `workspace.css`). Each CSS file is largely self-contained, including sidebar, main layout, and all component styles for that page.
- **Views:** `covise_app/views.py` — function-based views, mostly render templates
- **Models:** `WaitlistEntry` (signup info + S3 CV key) and `OnboardingResponse` (50+ JSONFields covering investor/founder onboarding answers)
- **URLs:** `covise_app/urls.py` — all routes are defined here
- **Admin path:** `/nxtui_we897_prw/` (obfuscated)
- **File uploads:** CVs go to AWS S3 (`covise-cvs-prod` bucket, `eu-central-1`)
- **Production:** Gunicorn on Railway, PostgreSQL via `dj-database-url`, WhiteNoise for static files

### 2. Tldraw AI Agent (`client/` + `worker/` + `shared/`)
A canvas-based AI collaboration interface built on Tldraw. Mostly independent from the Django app.

- **`client/`** — React 19 + TypeScript, compiled with Vite. Core is `TldrawAgent` in `client/agent/`, which drives canvas actions via AI responses.
- **`worker/`** — Cloudflare Workers (Durable Objects) that proxy AI model calls (Claude, Gemini, GPT) and stream responses back to the client.
- **`shared/`** — Zod schemas and TypeScript types shared between client and worker.

## CSS Conventions

- **Theme:** `data-theme="light"` / `data-theme="dark"` on `<body>`. Use CSS custom properties (`var(--accent)`, `var(--sidebar-link-bg)`, etc.) for theme-aware values — never hardcode dark-mode colors.
- **Sidebar:** Each page CSS independently styles `.sidebar` and `.sidebar-link`. Light mode rules should use `[data-theme="light"] .sidebar .sidebar-link { background: rgba(255,255,255,0.9); color: #2b3f6c; border-color: rgba(72,108,175,0.2); }`. Active link uses `#side_active`.
- **Mobile breakpoints:** `@media (max-width: 1100px)` resets `margin-left: 0` on `.main`; `@media (max-width: 720px)` moves sidebar to bottom (`position: fixed; bottom: 0`); `@media (max-width: 520px)` strips sidebar link containers (no background/border, `width/height: auto`).
- **The projects page** uses `requests.css` (not `projects.css`).
- **No hardcoded values:** Always use `var(--token)` for colors, spacing, and theme-sensitive properties.

## Environment Variables

- Django: `.env` in project root — `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `AWS_*` keys
- Cloudflare Worker: `.dev.vars` — `ANTHROPIC_API_KEY`



## Pre-Push Security Gate (Mandatory)

Whenever the user asks any variant of **"is it ready to be pushed?"**, **"can I push?"**, **"ready to deploy?"**, or **"safe to push?"** — always invoke the `pre-push` agent before answering. Never answer these questions from memory or assumption.

The `pre-push` agent:
- Scans all modified files for hardcoded secrets, API keys, passwords
- Verifies all uploads go to S3 — nothing saved to local filesystem
- Confirms `settings.py` uses `config()` for every secret
- Checks `.gitignore` is protecting sensitive files
- Scans templates and JS for exposed credentials or internal URLs
- Returns either ✅ CLEAN or 🚫 BLOCKED with exact file + line

**Never suggest `git push` without a CLEAN verdict from this agent.**

---

## Build–Critique Loop (Mandatory for Every Task)

All non-trivial code changes must go through a minimum of **2 full build–critique cycles** before the final answer is delivered. No exceptions.

Two agents handle this loop:

| Agent | Model | Role |
|---|---|---|
| `builder` | claude-opus-4-5 | Implements the change — reads files, writes code, runs migrations |
| `critic` | claude-opus-4-5 | Reviews the output against a fixed checklist, scores it, approves or rejects |

### The loop

```
CYCLE 1
  → builder: implement
  → critic: review, score /10, list issues
  → if rejected: builder fixes all issues

CYCLE 2 (minimum)
  → builder: apply fixes
  → critic: fresh review, score /10
  → if score ≥ 8 and cycle ≥ 2: deliver final answer
  → if score < 8: repeat
```

**Critic never approves before cycle 2**, even if cycle 1 is perfect.
**Builder never skips reading** the files it will touch.
**Final answer is only delivered after critic returns APPROVED on cycle ≥ 2.**

---

## Change Documentation (Always Required)

After every change — whether asked or not — always provide:

1. **Files changed** — list every file touched and what was done in it
2. **Data flow** — a brief diagram or sequence showing how data moves through the change
3. **Why** — one sentence per file explaining the reason for that specific change

Use this format:

```
FILES CHANGED
─────────────
models.py       → added X field for Y reason
views.py        → updated Z view to do W
migration 000N  → covers the new fields

DATA FLOW
─────────
[source] → [transform] → [destination]

WHY
───
models.py: needed to persist X so that Y can reference it later
views.py: X must happen before the retry loop or the file object is exhausted
```

This is mandatory. If a user asks "what did you change" or "explain the workflow", this format is the answer. Never answer these questions from memory — re-read the files and confirm before responding.

---

## Self-anneal
**1. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again
- Update SKILL.md with what you learned
- System is now stronger

**2. Update Skills as you learn**
Skills are living documents. When you discover API constraints, better approaches, or edge cases—update the SKILL.md. But don't create new Skills without asking.

**3. Self-annealing loop**

Errors are learning opportunities. When something breaks:
1. Fix the script
2. Test it
3. Update SKILL.md with new flow
4. System is now stronger