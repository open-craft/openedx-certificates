"""API functions for the Open edX Certificates app."""

from __future__ import annotations

import logging

from django.contrib.auth.models import User
from opaque_keys.edx.keys import CourseKey

from .models import ExternalCertificate, ExternalCertificateCourseConfiguration
from .tasks import generate_certificate_for_user_task

logger = logging.getLogger(__name__)


def get_eligible_users_by_certificate_type(course_id: CourseKey, user_id: int = None) -> dict[str, list[User]]:
    """
    Retrieve eligible users for each certificate type in the given course.

    :param course_id: The key of the course for which to check eligibility.
    :param user_id: Optional. If provided, will check eligibility for the specific user.
    :return: A dictionary with certificate type as the key and eligible users as the value.
    """
    certificate_configs = ExternalCertificateCourseConfiguration.objects.filter(course_id=course_id)

    if not certificate_configs:
        return {}

    eligible_users_by_type = {}
    for certificate_config in certificate_configs:
        user_ids = certificate_config.get_eligible_user_ids(user_id)
        filtered_user_ids = certificate_config.filter_out_user_ids_with_certificates(user_ids)

        if user_id:
            eligible_users_by_type[certificate_config.certificate_type.name] = list(set(filtered_user_ids) & {user_id})
        else:
            eligible_users_by_type[certificate_config.certificate_type.name] = filtered_user_ids

    return eligible_users_by_type


def get_user_certificates_by_type(course_id: CourseKey, user_id: int) -> dict[str, dict[str, str]]:
    """
    Retrieve the available certificates for a given user in a course.

    :param course_id: The course ID for which to retrieve certificates.
    :param user_id: The ID of the user for whom certificates are being retrieved.
    :return: A dict where keys are certificate types and values are dicts with the download link and status.
    """
    certificates = ExternalCertificate.objects.filter(user_id=user_id, course_id=course_id)

    return {cert.certificate_type: {'download_url': cert.download_url, 'status': cert.status} for cert in certificates}


def generate_certificate_for_user(course_id: CourseKey, certificate_type: str, user_id: int, force: bool = False):
    """
    Generate a certificate for a user in a course.

    :param course_id: The course ID for which to generate the certificate.
    :param certificate_type: The type of certificate to generate.
    :param user_id: The ID of the user for whom the certificate is being generated.
    :param force: If True, will generate the certificate even if the user is not eligible.
    """
    certificate_config = ExternalCertificateCourseConfiguration.objects.get(
        course_id=course_id, certificate_type__name=certificate_type
    )

    if not certificate_config:
        logger.error('No course configuration found for course %s', course_id)
        return

    if not force and not certificate_config.get_eligible_user_ids(user_id):
        logger.error('User %s is not eligible for the certificate in course %s', user_id, course_id)
        raise ValueError('User is not eligible for the certificate.')

    generate_certificate_for_user_task.delay(certificate_config.id, user_id)
