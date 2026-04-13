from pathlib import Path
import os
from decouple import config
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

try:
    import resend
except ImportError:
    resend = None

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='fallback-secret-key')

DEBUG_RAW = str(config('DEBUG', default='false')).strip().lower()
DEBUG = DEBUG_RAW in {'1', 'true', 'yes', 'on', 'debug', 'local'}

ALLOWED_HOSTS = ['covise.net', 'www.covise.net', '.up.railway.app', 'localhost', '127.0.0.1']
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    'https://covise.net',
    'https://www.covise.net',
    'https://*.up.railway.app',
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sitemaps',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'covise_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'covise.urls'
CSRF_FAILURE_VIEW = 'covise_app.views.csrf_failure'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'covise.wsgi.application'
AUTH_USER_MODEL = "covise_app.User"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# HTTPS Security (only in production)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = False
    CSRF_USE_SESSIONS = False
if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / 'static']


DATABASE_URL = config('DATABASE_URL', default='')
LOCAL_SQLITE_PATH = config('LOCAL_SQLITE_PATH', default='').strip()
RESEND_API = config('RESEND_API', default='')
WAITLIST_FAILURE_ALERT_EMAIL = config('WAITLIST_FAILURE_ALERT_EMAIL', default='ellabouhawel@gmail.com')
PRIVATE_PROFILE_COMPLETION_TOKEN = config('PRIVATE_PROFILE_COMPLETION_TOKEN', default='').strip()


def _send_configuration_alert(subject, message):
    if not RESEND_API or not WAITLIST_FAILURE_ALERT_EMAIL or resend is None:
        return

    resend.api_key = RESEND_API
    payload = {
        'from': 'CoVise Alerts <founders@covise.net>',
        'to': [WAITLIST_FAILURE_ALERT_EMAIL],
        'subject': subject,
        'html': (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            f'<h1 style="font-size: 22px; margin: 0 0 16px;">{subject}</h1>'
            f'<p style="margin: 0 0 10px;"><strong>Date:</strong> {timezone.now().isoformat()}</p>'
            f'<p style="margin: 0;">{message}</p>'
            '</div>'
        ),
    }
    try:
        resend.Emails.send(payload)
    except Exception:
        pass

if not DEBUG and not DATABASE_URL:
    _send_configuration_alert(
        'CoVise production boot blocked: missing DATABASE_URL',
        'DEBUG is false but DATABASE_URL is empty. Django refused to fall back to local SQLite in production.',
    )
    raise ImproperlyConfigured(
        "DATABASE_URL must be set when DEBUG is false. Refusing to fall back to local SQLite in production."
    )

if DATABASE_URL:
    db_ssl_require_raw = str(config('DB_SSL_REQUIRE', default='')).strip().lower()
    if db_ssl_require_raw in {'1', 'true', 'yes', 'on'}:
        db_ssl_require = True
    elif db_ssl_require_raw in {'0', 'false', 'no', 'off'}:
        db_ssl_require = False
    else:
        # Default to SSL for non-local PostgreSQL URLs (e.g., Railway) even in DEBUG.
        db_ssl_require = 'postgres' in DATABASE_URL.lower() and not (
            'localhost' in DATABASE_URL.lower() or '127.0.0.1' in DATABASE_URL.lower()
        )

    db_conn_max_age = 0 if DEBUG else 600
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=db_conn_max_age,
            ssl_require=db_ssl_require,
        )
    }
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
else:
    sqlite_path = Path(LOCAL_SQLITE_PATH) if LOCAL_SQLITE_PATH else Path.home() / '.covise' / 'data' / 'db.sqlite3'
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
        }
    }

    


# AWS S3
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='eu-central-1')


