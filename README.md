# CoVise

CoVise is a Django-based founder matching and collaboration platform. It combines waitlist capture, onboarding, profile building, project and workspace features, and private messaging in one product.

Production site: `https://covise.net`

## What the app does

- Waitlist collection and early-interest capture
- Structured onboarding that turns answers into profile data
- Custom email-based authentication
- Public and private profile flows
- Founder discovery and matching-oriented profile fields
- Projects and workspace pages
- Private messaging with Django Channels and WebSockets
- Message-request flow before a private conversation is opened

## Stack

- Python
- Django
- Django Channels
- Daphne
- Redis
- SQLite for local development
- PostgreSQL in production
- WhiteNoise for static files
- AWS S3 for CV and file upload helpers

## Architecture

### Core data flow

Waitlist -> Onboarding -> Account -> Profile sync -> Product features

### Main models

- `WaitlistEntry`
- `OnboardingResponse`
- `Profile`
- `UserPreference`
- `Conversation`
- `Message`
- `ConversationRequest`

### Realtime messaging

Messaging is implemented with:

- `channels`
- `daphne`
- `channels-redis`
- Redis channel layers
- WebSocket consumers in `covise_app/consumers.py`

Private chats are gated by a request/accept flow:

1. User A sends a private chat request from User B's public profile.
2. User B accepts or declines the request.
3. A `Conversation` is created only after acceptance.
4. Messages are delivered live through WebSockets and stored in the database.

## Project structure

```text
Covise/
|- README.md
`- covise/
   |- manage.py
   |- requirements.txt
   |- covise/
   |  |- settings.py
   |  |- urls.py
   |  |- asgi.py
   |  `- wsgi.py
   |- covise_app/
   |  |- models.py
   |  |- views.py
   |  |- urls.py
   |  |- consumers.py
   |  |- routing.py
   |  `- migrations/
   |- templates/
   `- static/
```

## Local setup

### 1. Create and activate a virtual environment

```bash
cd covise
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Start Redis

Redis is required for realtime messaging.

If you use Docker:

```bash
docker run -p 6379:6379 redis
```

### 5. Run the development server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Environment notes

The project reads configuration from environment variables via `python-decouple`.

Useful variables include:

- `SECRET_KEY`
- `DEBUG`
- `DATABASE_URL`
- `DB_SSL_REQUIRE`
- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`

## Local defaults

- If `DATABASE_URL` is empty, Django falls back to `db.sqlite3`.
- Redis is expected at `redis://127.0.0.1:6379/0`.
- If S3 credentials are missing, S3-backed upload helpers will not work correctly.

## Deployment notes

- Static files are served with WhiteNoise.
- The app includes both `WSGI` and `ASGI` entry points.
- Realtime chat depends on the ASGI stack in `covise/asgi.py`.
- Production should run Redis alongside the app for Channels messaging.

## Current status

Implemented:

- waitlist flow
- onboarding flow
- custom auth
- profile system
- settings
- public/private profile interactions
- private messaging with message requests and realtime delivery

Still evolving:

- richer file sharing in chat
- agreements and documents workflow
- deeper workspace and project integrations
