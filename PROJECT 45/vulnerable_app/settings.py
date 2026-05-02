"""
VULNERABLE Django Settings - DO NOT USE IN PRODUCTION
This file contains intentional security vulnerabilities for educational purposes.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# VULNERABILITY 1: Debug mode enabled in production
DEBUG = True  # Should be False in production!

ALLOWED_HOSTS = ['*']  # VULNERABLE: Allows any host

SECRET_KEY = 'django-insecure-very-weak-key-change-in-production'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'vulnerable_app',  # Our vulnerable app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Missing security middleware (VULNERABILITY 2)
]

ROOT_URLCONF = 'vulnerable_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# VULNERABILITY 3: Weak database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # Missing connection security settings
    }
}

# VULNERABILITY 4: Insecure file upload settings
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# VULNERABILITY 5: Weak password hashing
PASSWORD_HASHERS = [
    'vulnerable_app.hashers.MD5PasswordHasher',  # Custom weak hasher
]

AUTH_PASSWORD_VALIDATORS = [
    # Missing password complexity requirements
]

# VULNERABILITY 6: No CSRF protection for APIs
CSRF_COOKIE_SECURE = False  # Should be True in production
SESSION_COOKIE_SECURE = False  # Should be True in production

# VULNERABILITY 7: Missing security headers
SECURE_BROWSER_XSS_FILTER = False  # Should be True
SECURE_CONTENT_TYPE_NOSNIFF = False  # Should be True
X_FRAME_OPTIONS = 'ALLOWALL'  # Should be 'DENY'

# VULNERABILITY 8: Insecure email settings
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@jumpapp.com'

# VULNERABILITY 9: No rate limiting
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# VULNERABILITY 10: Exposed S3 settings
AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'  # Exposed keys!
AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
AWS_STORAGE_BUCKET_NAME = 'jumpapp-media-public'  # Public bucket!

# VULNERABILITY 11: No logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# VULNERABILITY 12: No CORS protection
CORS_ALLOW_ALL_ORIGINS = True  # Extremely permissive
CORS_ALLOW_CREDENTIALS = True
