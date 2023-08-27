"""
These settings are here to use during tests, because django requires them.

In a real-world use case, apps in this project are installed into other
Django applications, so these settings will not be used.
"""

from pathlib import Path


def root(path: Path) -> Path:
    """Get the absolute path of the given path relative to the project root."""
    return Path(__file__).parent.resolve() / path


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'default.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    },
}

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'openedx_certificates',
)

LOCALE_PATHS = [
    root(Path('openedx_certificates/conf/locale')),
]

ROOT_URLCONF = 'openedx_certificates.urls'

SECRET_KEY = 'insecure-secret-key'  # noqa: S105

MIDDLEWARE = (
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',  # this is required for admin
                'django.contrib.messages.context_processors.messages',  # this is required for admin
            ],
        },
    },
]
