from xumma.translation_manager import TranslationManager
from dotenv import load_dotenv
import os
from pathlib import Path
from datetime import timedelta
from kombu import Queue, Exchange


load_dotenv(override=True)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

TRANSLATIONS_PATH = os.path.join(BASE_DIR, "translations")
TRANSLATION_MANAGER = TranslationManager(translations_path="translations")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = str(os.environ.get('DEBUG')) == '1'

DJDT = str(os.environ.get('DJDT')) == '1'

CSRF_TRUSTED_ORIGINS_LIST = os.environ.get('CSRF_TRUSTED_ORIGINS_LIST')
TRUSTED_LIST = [i for i in CSRF_TRUSTED_ORIGINS_LIST.split(" ")]
CSRF_TRUSTED_ORIGINS = TRUSTED_LIST

ALLOWED_HOSTS_LIST = os.environ.get('ALLOWED_HOSTS')
HOSTS_LIST = [i for i in ALLOWED_HOSTS_LIST.split(" ")]
ALLOWED_HOSTS = HOSTS_LIST


CORS_ALLOWED_ORIGINS_LIST = os.environ.get('CORS_ALLOWED_ORIGINS_LIST')
CORS_LIST = [i for i in CORS_ALLOWED_ORIGINS_LIST.split(" ")]
CORS_ALLOWED_ORIGINS = CORS_LIST
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://\w+\.xtms-frontend.pages.dev$",
]

DOMAIN = os.getenv('DOMAIN')
SITE_NAME = os.getenv('SITE_NAME')
SITE_URL = os.getenv('SITE_URL')
BACKEND_URL = os.getenv('BACKEND_URL')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'axes',
    'djoser',
    'corsheaders',
    'channels',
    'storages',
    'django_celery_results',
    'django_celery_beat',
    'phonenumber_field',

    'rest_framework',
    'rest_framework_simplejwt',

    'abb',
    'app',
    'att',
    'axx',
    'ayy',
    'bch',
    'dff',
    'dtt',
    'eff',
    'eml',
]


if DJDT:
    INTERNAL_IPS = ['127.0.0.1']
    INSTALLED_APPS += ('debug_toolbar',)
    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.history.HistoryPanel',
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
        'debug_toolbar.panels.profiling.ProfilingPanel',
    ]


### DEFAULT EMAIL SETTINGS ###
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_USE_TLS = str(os.environ.get('EMAIL_USE_TLS')) == '1'
EMAIL_USE_SSL = str(os.environ.get('EMAIL_USE_SSL')) == '1'
EMAIL_PORT = os.environ.get('EMAIL_PORT')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

### AWB SES ###
EMAIL_BACKEND_AWS = os.environ.get('EMAIL_BACKEND_AWS')
DEFAULT_FROM_EMAIL_AWS = os.environ.get('DEFAULT_FROM_EMAIL_AWS')
EMAIL_HOST_AWS = os.environ.get('EMAIL_HOST_AWS')
EMAIL_USE_TLS_AWS = str(os.environ.get('EMAIL_USE_TLS_AWS')) == '1'
EMAIL_USE_SSL_AWS = str(os.environ.get('EMAIL_USE_SSL_AWS')) == '1'
EMAIL_PORT_AWS = os.environ.get('EMAIL_PORT_AWS')
EMAIL_HOST_USER_AWS = os.environ.get('EMAIL_HOST_USER_AWS')
EMAIL_HOST_PASSWORD_AWS = os.environ.get('EMAIL_HOST_PASSWORD_AWS')

EMAIL_TIMEOUT = 3  # Timeout in seconds

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
# ACCOUNT_EMAIL_VERIFICATION = "mandatory"


MIDDLEWARE = [
    'abb.custom_middleware.CustomHandleInvalidHostMiddleware',  # 👈 must be FIRST
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'django.middleware.locale.LocaleMiddleware',

    ### AxesMiddleware should be the last middleware in the MIDDLEWARE list. ###
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'xumma.urls'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated'
    ],

    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'app.authentication.CustomJWTAuthentication',
        'app.authentication.PersonalApiTokenAuthentication',
    ),

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',


    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'emails_hour': '100/hour',
        'emails_day': '600/day',
    },
}

### TURN OFF DRF BROWSABLE API IN PRODUCTION ###
if not DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
        "rest_framework.renderers.JSONRenderer",
    )


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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


WSGI_APPLICATION = 'xumma.wsgi.application'
ASGI_APPLICATION = 'xcmd.asgi.application'


### Database settings ###
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('ENGINE'),
        'NAME': os.environ.get('SQL_NAME'),
        'USER': os.environ.get('SQL_USER'),
        'PASSWORD': os.environ.get('SQL_PASSWORD'),
        'HOST': os.environ.get('SQL_HOST'),
        'PORT': os.environ.get('SQL_PORT'),
    }
}


AUTHENTICATION_BACKENDS = [
    # AxesStandaloneBackend should be the first backend in the AUTHENTICATION_BACKENDS list.
    'axes.backends.AxesStandaloneBackend',

    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
]


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


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
# USE_I18N = True
USE_TZ = True

# DATETIME_FORMAT = "%d-%m-%Y%H:%M:%S"
DATETIME_FORMAT = "%d-%m-%y %H:%M:%S"


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'app.User'


STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"


SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


DJOSER = {
    'LOGIN_FIELD': 'email',
    'TOKEN_MODEL': None,

    'PASSWORD_RESET_CONFIRM_URL': 'api/password/reset/confirm/{uid}/{token}',
    'USERNAME_RESET_CONFIRM_URL': 'api/username/reset/confirm/{uid}/{token}',
    'ACTIVATION_URL': 'auth/jwt/api/activate/{uid}/{token}',
    'SEND_ACTIVATION_EMAIL': True,
    'PASSWORD_CHANGED_EMAIL_CONFIRMATION': True,
    'SET_PASSWORD_RETYPE': True,
    'SERIALIZERS': {'user_create': 'app.djoser_serializers.UserBaseCreateSerializer', 'password_reset': 'app.djoser_serializers.SendEmailResetSerializer', },
    'EMAIL': {
        'activation': 'app.djoser_email.ActivationEmail',
        'confirmation': 'djoser.email.ConfirmationEmail',
        'password_reset': 'app.djoser_email.PasswordResetEmail',
        'password_changed_confirmation': 'app.djoser_email.PasswordChangedConfirmationEmail',
        'username_changed_confirmation': 'djoser.email.UsernameChangedConfirmationEmail',
        'username_reset': 'djoser.email.UsernameResetEmail',
    },
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'AUTH_HEADER_TYPES': ('JWT', ),
    'BLACKLIST_AFTER_ROTATION': True,
}

AUTH_COOKIE = 'access'
AUTH_COOKIE_MAX_AGE = 60 * 15  # seconds
AUTH_REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days in seconds


AUTH_COOKIE_SECURE = os.getenv('AUTH_COOKIE_SECURE', 'True') == 'True'
AUTH_COOKIE_PATH = os.getenv('AUTH_COOKIE_PATH', '/')
AUTH_COOKIE_DOMAIN = os.getenv('AUTH_COOKIE_DOMAIN')
AUTH_COOKIE_SAMESITE = 'None'
AUTH_COOKIE_HTTP_ONLY = True  # True


### AXES CONFIG ###
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']
AXES_SENSITIVE_PARAMETERS = ['password', 'otp']
AXES_FAILURE_LIMIT = 20
AXES_COOLOFF_TIME = 0.25
AXES_RESET_ON_SUCCESS = True
AXES_IPWARE_META_PRECEDENCE_ORDER = ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR',]

### django-ipware. The default meta precedence order (update as needed) ###
IPWARE_META_PRECEDENCE_ORDER = (
    "CF-CONNECTING-IP",  # CloudFlare
    # Load balancers or proxies such as AWS ELB (default client is `left-most` [`<client>, <proxy1>, <proxy2>`])
    "X_FORWARDED_FOR",
    "HTTP_X_FORWARDED_FOR",  # Similar to X_FORWARDED_TO
    # Standard headers used by providers such as Amazon EC2, Heroku etc.
    "HTTP_CLIENT_IP",
    # Standard headers used by providers such as Amazon EC2, Heroku etc.
    "HTTP_X_REAL_IP",
    "HTTP_X_FORWARDED",  # Squid and others
    "HTTP_X_CLUSTER_CLIENT_IP",  # Rackspace LB and Riverbed Stingray
    "HTTP_FORWARDED_FOR",  # RFC 7239
    "HTTP_FORWARDED",  # RFC 7239
    "HTTP_CF_CONNECTING_IP",  # CloudFlare
    "X-CLIENT-IP",  # Microsoft Azure
    "X-REAL-IP",  # NGINX
    "X-CLUSTER-CLIENT-IP",  # Rackspace Cloud Load Balancers
    "X_FORWARDED",  # Squid
    "FORWARDED_FOR",  # RFC 7239
    "TRUE-CLIENT-IP",  # CloudFlare Enterprise,
    "FASTLY-CLIENT-IP",  # Firebase, Fastly
    "FORWARDED",  # RFC 7239
    "CLIENT-IP",  # Akamai and Cloudflare: True-Client-IP and Fastly: Fastly-Client-IP
    "REMOTE_ADDR",  # Default
)


### GET REDIS_HOST FROM .ENV ###
REDIS_HOST = os.getenv('REDIS_HOST')

### CACHES using django-redis settings ###
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379/10",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

### CHANNELS SETTINGS / WEBSOCKET ###
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, 6379, 0)],
        },
    },
}

### CELERY SETTINGS ###
CELERY_TASK_QUEUES = (
    Queue('celery', Exchange('celery', type='direct'), routing_key='celery'),
    Queue('high_priority', Exchange('high_priority',
          type='direct'), routing_key='high_priority'),
    Queue('low_priority', Exchange('low_priority',
          type='direct'), routing_key='low_priority'),
)

# Default queue configuration
CELERY_DEFAULT_QUEUE = 'celery'
CELERY_CELERY_EXCHANGE = 'celery'
CELERY_CELERY_ROUTING_KEY = 'celery'


### GOOGLE API KEY ###
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

### HERE API KEY ###
HERE_ID = os.environ.get('HERE_ID')
HERE_API_KEY = os.environ.get('HERE_API_KEY')


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        '__main__': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'axes.watch_login': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
