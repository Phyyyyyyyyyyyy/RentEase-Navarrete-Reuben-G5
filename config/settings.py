"""
Django settings for the RentEase project.

Secrets and database credentials are read from a local `.env` file
(see `.env.example`). Never commit the real `.env`.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(
            f'Missing environment variable {name}. Copy .env.example to .env and fill it in.'
        )
    return value


SECRET_KEY = env('SECRET_KEY', required=True)
DEBUG = env('DEBUG', 'False').lower() in ('1', 'true', 'yes')
ALLOWED_HOSTS = [h.strip() for h in env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'properties',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'


# Database: PostgreSQL (Supabase). Set DATABASE_URL in .env, e.g.
# postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
DATABASES = {
    'default': dj_database_url.parse(
        env('DATABASE_URL', required=True),
        conn_max_age=60,
        conn_health_checks=True,
    )
}


# Authentication
AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrUsernameBackend']
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Uploaded profile photos
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
