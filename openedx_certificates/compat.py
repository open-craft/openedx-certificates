"""
Proxies and compatibility code for edx-platform features.

This module moderates access to all edx-platform features allowing for cross-version compatibility code.
It also simplifies running tests outside edx-platform's environment by stubbing these functions in unit tests.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

import pytz
from celery import Celery
from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from django.contrib.auth.models import User
    from opaque_keys.edx.keys import CourseKey


def get_celery_app() -> Celery:
    """Get Celery app to reuse configuration and queues."""
    if getattr(settings, "TESTING", False):
        # We can ignore this in the testing environment.
        return Celery(task_always_eager=True)

    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from lms import CELERY_APP

    return CELERY_APP  # pragma: no cover


def get_course_grading_policy(course_id: CourseKey) -> dict:
    """Get the course grading policy from Open edX."""
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from xmodule.modulestore.django import modulestore

    return modulestore().get_course(course_id).grading_policy["GRADER"]


def get_course_name(course_id: CourseKey) -> str:
    """Get the course name from Open edX."""
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from openedx.core.djangoapps.content.learning_sequences.api import get_course_outline

    course_outline = get_course_outline(course_id)
    return (course_outline and course_outline.title) or str(course_id)


def get_course_enrollments(course_id: CourseKey) -> list[User]:
    """Get the course enrollments from Open edX."""
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from common.djangoapps.student.models import CourseEnrollment

    enrollments = CourseEnrollment.objects.filter(course_id=course_id, is_active=True).select_related('user')
    return [enrollment.user for enrollment in enrollments]


@contextmanager
def prefetch_course_grades(course_id: CourseKey, users: list[User]):
    """Prefetch the course grades from Open edX."""
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from lms.djangoapps.grades.api import clear_prefetched_course_grades, prefetch_course_grades

    prefetch_course_grades(course_id, users)
    try:
        yield
    finally:
        clear_prefetched_course_grades(course_id)


def get_course_grade_factory():  # noqa: ANN201
    """Get the course grade factory from Open edX."""
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

    return CourseGradeFactory()


def get_localized_certificate_date() -> str:
    """Get the localized date from Open edX."""
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from common.djangoapps.util.date_utils import strftime_localized

    date = datetime.now(pytz.timezone(settings.TIME_ZONE))
    return strftime_localized(date, settings.CERTIFICATE_DATE_FORMAT)
