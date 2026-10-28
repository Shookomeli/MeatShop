import os
from pathlib import Path

try:
    import environ
    env = environ.Env()
    environ.Env.read_env(os.path.join(Path(__file__).resolve().parent.parent, '.env'))
except ImportError:
    class DummyEnv:
        def __call__(self, key, default=None):
            return os.environ.get(key, default)
        def bool(self, key, default=False):
            val = os.environ.get(key)
            if val is None:
                return default
            return val.lower() in ('true', '1', 'yes')
    env = DummyEnv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = env('SECRET_KEY', default='django-insecure-meatshop-phase1-dev-key')
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = ['*']

# Scale mode: mock (development/tests) | keli_xk3118t1 (hardware, Phase 11+)
SCALE_MODE = env('SCALE_MODE', default='mock')

# Currency display unit: TOMAN | RIAL
# Monetary database fields store whole-number Rial. This controls display formatting only.
CURRENCY_DISPLAY_UNIT = env('CURRENCY_DISPLAY_UNIT', default='TOMAN')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'products',
    'sales',
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

ROOT_URLCONF = 'MeatShop.urls'

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

WSGI_APPLICATION = 'MeatShop.wsgi.application'

# Database configuration
# Development database: BASE_DIR / 'db.sqlite3'
# Production database: C:\MeatShop\data\db.sqlite3 (configured via DATABASE_PATH env var)
# CRITICAL: Never replace or overwrite the customer's production database with a development database.
database_path = env('DATABASE_PATH', default=None)
if database_path:
    db_name = Path(database_path)
else:
    db_name = BASE_DIR / 'db.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': db_name,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization & Persian Locale
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
