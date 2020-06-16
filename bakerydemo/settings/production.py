import os
import random
import string

import dj_database_url
import django_cache_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F403

env = os.environ.copy()

DEBUG = os.getenv('DJANGO_DEBUG', 'off') == 'on'

# DJANGO_SECRET_KEY *should* be specified in the environment. If it's not, generate an ephemeral key.
if 'DJANGO_SECRET_KEY' in os.environ:
    SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
else:
    # Use if/else rather than a default value to avoid calculating this if we don't need it
    print("WARNING: DJANGO_SECRET_KEY not found in os.environ. Generating ephemeral SECRET_KEY.")
    SECRET_KEY = ''.join([random.SystemRandom().choice(string.printable) for i in range(50)])

if 'SENTRY_DSN' in env:
    sentry_sdk.init(
        dsn=env['SENTRY_DSN'],
        integrations=[DjangoIntegration()],

        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True
    )

# Make sure Django can detect a secure connection properly on Heroku:
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Redirect all requests to HTTPS
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', 'off') == 'on'

# Accept all hostnames, since we don't know in advance which hostname will be used for any given Heroku instance.
# IMPORTANT: Set this to a real hostname when using this in production!
# See https://docs.djangoproject.com/en/1.10/ref/settings/#allowed-hosts
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(';')

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Email settings
# We use SMTP to send emails. We typically use transactional email services
# that let us use SMTP.
# https://docs.djangoproject.com/en/2.1/topics/email/

# https://docs.djangoproject.com/en/stable/ref/settings/#email-host
if "EMAIL_HOST" in env:
    EMAIL_HOST = env["EMAIL_HOST"]

# https://docs.djangoproject.com/en/stable/ref/settings/#email-port
if "EMAIL_PORT" in env:
    try:
        EMAIL_PORT = int(env["EMAIL_PORT"])
    except ValueError:
        pass

# https://docs.djangoproject.com/en/stable/ref/settings/#email-host-user
if "EMAIL_HOST_USER" in env:
    EMAIL_HOST_USER = env["EMAIL_HOST_USER"]

# https://docs.djangoproject.com/en/stable/ref/settings/#email-host-password
if "EMAIL_HOST_PASSWORD" in env:
    EMAIL_HOST_PASSWORD = env["EMAIL_HOST_PASSWORD"]

# https://docs.djangoproject.com/en/stable/ref/settings/#email-use-tls
if env.get("EMAIL_USE_TLS", "false").lower().strip() == "true":
    EMAIL_USE_TLS = True

# https://docs.djangoproject.com/en/stable/ref/settings/#email-use-ssl
if env.get("EMAIL_USE_SSL", "false").lower().strip() == "true":
    EMAIL_USE_SSL = True

# https://docs.djangoproject.com/en/stable/ref/settings/#email-subject-prefix
if "EMAIL_SUBJECT_PREFIX" in env:
    EMAIL_SUBJECT_PREFIX = env["EMAIL_SUBJECT_PREFIX"]

# SERVER_EMAIL is used to send emails to administrators.
# https://docs.djangoproject.com/en/stable/ref/settings/#server-email
# DEFAULT_FROM_EMAIL is used as a default for any mail send from the website to
# the users.
# https://docs.djangoproject.com/en/stable/ref/settings/#default-from-email
if "SERVER_EMAIL" in env:
    SERVER_EMAIL = DEFAULT_FROM_EMAIL = env["SERVER_EMAIL"]


# BASE_URL required for notification emails
BASE_URL = 'https://wagtailworkflow.torchbox.com'

db_from_env = dj_database_url.config(conn_max_age=500)
DATABASES['default'].update(db_from_env)

# AWS creds may be used for S3 and/or Elasticsearch
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION = os.getenv('AWS_REGION', '')

# configure CACHES from CACHE_URL environment variable (defaults to locmem if no CACHE_URL is set)
CACHES = {'default': django_cache_url.config()}

# Configure Elasticsearch, if present in os.environ
ELASTICSEARCH_ENDPOINT = os.getenv('ELASTICSEARCH_ENDPOINT', '')

if ELASTICSEARCH_ENDPOINT:
    from elasticsearch import RequestsHttpConnection
    WAGTAILSEARCH_BACKENDS = {
        'default': {
            'BACKEND': 'wagtail.search.backends.elasticsearch2',
            'HOSTS': [{
                'host': ELASTICSEARCH_ENDPOINT,
                'port': int(os.getenv('ELASTICSEARCH_PORT', '9200')),
                'use_ssl': os.getenv('ELASTICSEARCH_USE_SSL', 'off') == 'on',
                'verify_certs': os.getenv('ELASTICSEARCH_VERIFY_CERTS', 'off') == 'on',
            }],
            'OPTIONS': {
                'connection_class': RequestsHttpConnection,
            },
        }
    }

    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        from aws_requests_auth.aws_auth import AWSRequestsAuth
        WAGTAILSEARCH_BACKENDS['default']['HOSTS'][0]['http_auth'] = AWSRequestsAuth(
            aws_access_key=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_token=os.getenv('AWS_SESSION_TOKEN', ''),
            aws_host=ELASTICSEARCH_ENDPOINT,
            aws_region=AWS_REGION,
            aws_service='es',
        )
    elif AWS_REGION:
        # No API keys in the environ, so attempt to discover them with Boto instead, per:
        # http://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials
        # This may be useful if your credentials are obtained via EC2 instance meta data.
        from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
        WAGTAILSEARCH_BACKENDS['default']['HOSTS'][0]['http_auth'] = BotoAWSRequestsAuth(
            aws_host=ELASTICSEARCH_ENDPOINT,
            aws_region=AWS_REGION,
            aws_service='es',
        )

# Simplified static file serving.
# https://warehouse.python.org/project/whitenoise/

MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

if 'AWS_STORAGE_BUCKET_NAME' in os.environ:
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME
    AWS_AUTO_CREATE_BUCKET = True

    INSTALLED_APPS.append('storages')
    MEDIA_URL = "https://%s/" % AWS_S3_CUSTOM_DOMAIN
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

if 'GS_BUCKET_NAME' in os.environ:
    GS_BUCKET_NAME = os.getenv('GS_BUCKET_NAME')
    GS_PROJECT_ID = os.getenv('GS_PROJECT_ID')
    GS_DEFAULT_ACL = 'publicRead'
    GS_AUTO_CREATE_BUCKET = True

    INSTALLED_APPS.append('storages')
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'

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
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
    },
}
