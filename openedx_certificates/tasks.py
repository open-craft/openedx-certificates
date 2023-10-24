"""Asynchronous Celery tasks."""

from __future__ import annotations

from openedx_certificates.compat import get_celery_app
from openedx_certificates.models import ExternalCertificateCourseConfiguration

app = get_celery_app()


@app.task
def generate_certificate_for_user_task(course_config_id: int, user_id: int):
    """
    Celery task for processing a single user's certificate.

    This function retrieves an ExternalCertificateCourse object based on course_id and certificate_type_id,
    retrieves the data using the retrieval_func specified in the associated ExternalCertificateType object,
    and passes this data to the function specified in the generation_func field.

    :param course_config_id: The ID of the ExternalCertificateCourseConfiguration object to process.
    :param user_id: The ID of the user to process the certificate for.
    """
    course_config = ExternalCertificateCourseConfiguration.objects.get(id=course_config_id)
    course_config.generate_certificate_for_user(user_id, generate_certificate_for_user_task.request.id)


@app.task
def generate_certificates_for_course_task(course_config_id: int):
    """
    Celery task for processing a single course's certificates.

    This function retrieves an ExternalCertificateCourse object based on course_id and certificate_type_id,
    retrieves the data using the retrieval_func specified in the associated ExternalCertificateType object,
    and passes this data to the function specified in the generation_func field.

    :param course_config_id: The ID of the ExternalCertificateCourseConfiguration object to process.
    """
    course_config = ExternalCertificateCourseConfiguration.objects.get(id=course_config_id)
    user_ids = course_config.get_eligible_user_ids()
    for name in user_ids:
        generate_certificate_for_user_task.apply_async(course_config_id, name)


@app.task
def generate_all_certificates_task():
    """
    Celery task for initiating the processing of certificates for all enabled courses.

    This function fetches all enabled ExternalCertificateCourse objects,
    and initiates a separate Celery task (process_certificate_for_course) for each of them.
    """
    course_config_ids = ExternalCertificateCourseConfiguration.get_enabled_configurations().values_list('id', flat=True)
    for config_id in course_config_ids:
        generate_certificates_for_course_task.delay(config_id)
