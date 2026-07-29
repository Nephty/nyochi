import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-in-production')

DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() != 'false'

ALLOWED_HOSTS = ['*'] if DEBUG else os.environ.get('ALLOWED_HOSTS', '').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'recipes',
    'ingredients',
    'shops',
    'tags',
    'grocery',
    'find_recipes',
    'accounts',
]

SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN') or None
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG

CSRF_TRUSTED_ORIGINS = ['https://*.nephty.top', 'https://nephty.top']

LOGIN_URL = os.environ.get('LOGIN_URL', 'https://nephty.top/login')
LOGIN_REDIRECT_URL = 'recipe-list'
LOGOUT_REDIRECT_URL = 'https://nephty.top/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'config.middleware.AppAccessMiddleware',
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.environ.get('RECIPE_BOOK_DB_PATH', str(BASE_DIR / 'db' / 'db.sqlite3'))),
    },
    'hub': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('HUB_DB_PATH', str(BASE_DIR / 'db' / 'hub.sqlite3')),
    },
}

DATABASE_ROUTERS = ['config.routers.HubRouter']

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

FORCE_SCRIPT_NAME = os.environ.get('DJANGO_FORCE_SCRIPT_NAME') or None

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

STATIC_URL = f"{os.environ.get('DJANGO_FORCE_SCRIPT_NAME', '')}/static/"
STATIC_ROOT = Path(os.environ.get('RECIPE_BOOK_STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
