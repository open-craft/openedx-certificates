"""Factories for creating test data."""

from datetime import datetime

import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory
from pytz import UTC


class UserFactory(DjangoModelFactory):
    """A Factory for User objects."""

    class Meta:  # noqa: D106
        model = User
        django_get_or_create = ('email', 'username')

    _DEFAULT_PASSWORD = 'test'  # noqa: S105

    username = factory.Sequence('robot{}'.format)
    email = factory.Sequence('robot+test+{}@edx.org'.format)
    password = factory.django.Password(_DEFAULT_PASSWORD)
    first_name = factory.Sequence('Robot{}'.format)
    last_name = 'Test'
    is_staff = False
    is_active = True
    is_superuser = False
    last_login = datetime(2012, 1, 1, tzinfo=UTC)
    date_joined = datetime(2011, 1, 1, tzinfo=UTC)
