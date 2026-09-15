"""
Django settings for flax_backend project.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-secret-key-change-me"

DEBUG = True

ALLOWED_HOSTS = ["*"]  # tighten this in production

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "flaxes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must be high in the list
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "flax_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "flax_backend.wsgi.application"

# Database.
# Switched from SQLite to SQL Server Express, matching the instance you
# tested in SSMS (".\SQLEXPRESS", Windows Authentication as ZERO\User).
#
# ASSUMPTIONS — adjust if these don't match your setup:
#   - The ODBC driver installed on your machine is "ODBC Driver 17 for
#     SQL Server". If SSMS/Windows only has "ODBC Driver 18" installed,
#     change the driver name below AND keep TrustServerCertificate=yes
#     (driver 18 defaults to requiring encryption + a valid cert, which a
#     local dev SQL Server usually doesn't have).
#   - You created a dedicated "FlaxDB" database in SSMS (see the steps).
#   - Windows Authentication (trusted_connection) is used, matching the
#     ZERO\User login shown in your SSMS session — no username/password
#     needed. If you instead set up SQL Server auth, replace USER/PASSWORD
#     and drop 'trusted_connection'.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'defaultdb'),
        'USER': os.environ.get('DB_USER', 'avnadmin'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'AVNS_67ll7cHd1m4dczSmr_q'),
        'HOST': os.environ.get('DB_HOST', 'mysql-1936593e-cadkalpana-1cce.l.aivencloud.com'),
        'PORT': os.environ.get('DB_PORT', '16025'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

FLAX_ASSIGNMENT_REMOVE_CODE = "1234"

STATIC_URL = "static/"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

# Allow the Flutter app (any origin) to call the API during development.
CORS_ALLOW_ALL_ORIGINS = True