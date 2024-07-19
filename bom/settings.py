"""
Django settings for indabom project.

Generated by 'django-admin startproject' using Django 1.10.5.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
from datetime import timedelta

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# Application definition

INSTALLED_APPS = [
    "bom.apps.BomConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "materializecssform",
    "social_django",
    "djmoney",
    "djmoney.contrib.exchange",
    "rest_framework",
    "rest_framework_simplejwt",
]


REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    "SLIDING_TOKEN_LIFETIME": timedelta(days=30),
    "SLIDING_TOKEN_REFRESH_LIFETIME_LATE_USER": timedelta(days=1),
    "SLIDING_TOKEN_LIFETIME_LATE_USER": timedelta(days=30),
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
]

ROOT_URLCONF = "bom.urls"

AUTHENTICATION_BACKENDS = (
    # TODO: depreciated: "social_core.backends.google.GoogleOpenId",
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.google.GoogleOAuth",
    "django.contrib.auth.backends.ModelBackend",
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "bom/templates/bom")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
                "bom.context_processors.bom_config",
            ],
            "builtins": ["django.templatetags.i18n"],
        },
    },
]

WSGI_APPLICATION = "bom.wsgi.application"

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
if "DEBUG" in os.environ:
    DEBUG = os.environ.get("DEBUG")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        # Include the default Django email handler for errors
        # This is what you'd get without configuring logging at all.
        # "mail_admins": {
        #    "class": "django.utils.log.AdminEmailHandler",
        #    "level": "ERROR",
        # But the emails are plain text by default - HTML is nicer
        #    "include_html": True,
        # },
        # Log to a text file that can be rotated by logrotate
        "logfile": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": (
                os.path.join(BASE_DIR, "log/bom.log") if not DEBUG else "./bom_dev.log"
            ),
        },
    },
    "loggers": {
        # Again, default Django configuration to email unhandled exceptions
        # "django.request": {
        #    "handlers": ["mail_admins"],
        #    "level": "ERROR",
        #    "propagate": True,
        # },
        # Might as well log any errors anywhere else in Django
        "django": {
            "handlers": ["logfile"],
            "level": "ERROR",
            "propagate": False,
        },
        # django-bom app
        "bom": {
            "handlers": ["logfile"],
            "level": "INFO",  # Or maybe INFO or DEBUG
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/
LANGUAGE_CODE = "fa-IR" if not DEBUG else "en-US"

TIME_ZONE = "Asia/Tehran"

USE_I18N = True

USE_TZ = True

LANGUAGES = [
    ("fa", "Persian"),
    ("en", "English"),
]
LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

LOGIN_URL = "/login/"
LOGOUT_URL = "/logout/"

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/settings?tab_anchor=file"
SOCIAL_AUTH_DISCONNECT_REDIRECT_URL = "/settings?tab_anchor=file"
SOCIAL_AUTH_LOGIN_ERROR_URL = "/"

SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/plus.login",
]
SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {
    "access_type": "offline",
    "approval_prompt": "force",  # forces storage of refresh token
}

SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
    "bom.third_party_apis.google_drive.initialize_parent",
)

SOCIAL_AUTH_DISCONNECT_PIPELINE = (
    "social_core.pipeline.disconnect.allowed_to_disconnect",
    "bom.third_party_apis.google_drive.uninitialize_parent",
    "social_core.pipeline.disconnect.get_entries",
    "social_core.pipeline.disconnect.revoke_tokens",
    "social_core.pipeline.disconnect.disconnect",
)

# django-money settings
CURRENCY_DECIMAL_PLACES = 0
EXCHANGE_BACKEND = "djmoney.contrib.exchange.backends.FixerBackend"

# django-bom configuration
BOM_CONFIG_DEFAULT = {
    "base_template": "base.html",
    "mouser_api_key": None,
    "admin_dashboard": {
        "enable_autocomplete": True,
        "page_size": 50,
    },
}

bom_config_new = BOM_CONFIG_DEFAULT.copy()
# if 'BOM_CONFIG' in os.environ:
#    bom_config_new.update(os.environ.get("BOM_CONFIG"))
BOM_CONFIG = bom_config_new

# Custom login url for BOM_LOGIN
BOM_LOGIN_URL = None

# google GoogleOAuth
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = "secretkey"
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = "secretkey"

EMAIL_BACKEND = "sendgrid_backend.SendgridBackend"
SENDGRID_API_KEY = "secretkey"

FIXER_ACCESS_KEY = "secretkey from fixer.io"  # for exchange rate conversions

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey")

ALLOWED_HOSTS = ["*"]
if "DJANGO_ALLOWED_HOSTS" in os.environ and os.environ.get("DJANGO_ALLOWED_HOSTS"):
    # 'DJANGO_ALLOWED_HOSTS' should be a single string of hosts with a space between each.
    # For example: 'DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1 [::1]'
    ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS").split(" ")

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("SQL_DATABASE", os.path.join(BASE_DIR, "db.sqlite3")),
        "USER": os.environ.get("SQL_USER", "user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
    }
}

# TODO: fix this
CSRF_TRUSTED_ORIGINS = [
    "https://127.0.0.1",
    "http://localhost:1313",
    "http://127.0.0.1",
    "http://127.0.0.1:1313",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

if "CSRF_TRUSTED_ORIGINS" in os.environ and os.environ.get("CSRF_TRUSTED_ORIGINS"):
    # 'CSRF_TRUSTED_ORIGINS' should be a single string of hosts with a space between each.
    # For example: 'CSRF_TRUSTED_ORIGINS=http://localhost:1313 https://127.0.0.1 http://127.0.0.1:1313'
    CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS").split(" ")

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
