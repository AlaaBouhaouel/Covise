from pathlib import Path
import os
from decouple import config
import dj_database_url


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
    'daphne',
    'anymail',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sitemaps',
    'django.contrib.contenttypes',
    'channels',
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
    'covise_app.middleware.AgreementRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'covise.urls'
CSRF_FAILURE_VIEW = 'covise_app.views.csrf_failure'
REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/0')
REDIS_SOCKET_CONNECT_TIMEOUT = config('REDIS_SOCKET_CONNECT_TIMEOUT', default=5, cast=int)
REDIS_SOCKET_TIMEOUT = config('REDIS_SOCKET_TIMEOUT', default=5, cast=int)
REDIS_HEALTH_CHECK_INTERVAL = config('REDIS_HEALTH_CHECK_INTERVAL', default=30, cast=int)
REDIS_RETRY_ON_TIMEOUT = config('REDIS_RETRY_ON_TIMEOUT', default=True, cast=bool)
REDIS_OPERATION_RETRY_ATTEMPTS = config('REDIS_OPERATION_RETRY_ATTEMPTS', default=3, cast=int)
REDIS_OPERATION_RETRY_DELAY_MS = config('REDIS_OPERATION_RETRY_DELAY_MS', default=250, cast=int)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": REDIS_URL,
                    "socket_connect_timeout": REDIS_SOCKET_CONNECT_TIMEOUT,
                    "socket_timeout": REDIS_SOCKET_TIMEOUT,
                    "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
                    "retry_on_timeout": REDIS_RETRY_ON_TIMEOUT,
                }
            ],
            "expiry": 60,
            "group_expiry": 86400,
            "capacity": 1500,
        },
    },
}

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
                'covise_app.context_processors.user_ui_context',

            ],
        },
    },
]

WSGI_APPLICATION = 'covise.wsgi.application'
ASGI_APPLICATION= 'covise.asgi.application'
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
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

RESEND_API = config('RESEND_API', default=config('RESEND_API_KEY', default=''))
RESEND_API_KEY = RESEND_API

EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='anymail.backends.resend.EmailBackend' if RESEND_API_KEY else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='support@covise.net')
ANYMAIL = {
    'RESEND_API_KEY': RESEND_API_KEY,
}

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
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


    
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/home/'

# AWS S3
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='eu-central-1')
WAITLIST_FAILURE_ALERT_EMAIL = config('WAITLIST_FAILURE_ALERT_EMAIL', default='ellabouhawel@gmail.com')
REPORT_ALERT_EMAIL = config('REPORT_ALERT_EMAIL', default=WAITLIST_FAILURE_ALERT_EMAIL)
