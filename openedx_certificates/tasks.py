"""Asynchronous Celery tasks."""

from __future__ import annotations

import logging

from openedx_certificates.compat import get_celery_app
from openedx_certificates.models import LearningCredentialConfiguration

app = get_celery_app()
log = logging.getLogger(__name__)


@app.task
def generate_certificate_for_user_task(course_config_id: int, user_id: int):
    """
    Celery task for processing a single user's certificate.

    This function retrieves a configuration based on learning_context_key and certificate_type_id,
    retrieves the data using the retrieval_func specified in the associated credential type object,
    and passes this data to the function specified in the generation_func field.

    :param course_config_id: The ID of the configuration object to process.
    :param user_id: The ID of the user to process the certificate for.
    """
    course_config = LearningCredentialConfiguration.objects.get(id=course_config_id)
    course_config.generate_certificate_for_user(user_id, generate_certificate_for_user_task.request.id)


@app.task
def generate_certificates_for_course_task(course_config_id: int):
    """
    Celery task for processing a single course's certificates.

    This function retrieves a configuration based on course_id and certificate_type_id,
    retrieves the data using the retrieval_func specified in the associated credential type object,
    and passes this data to the function specified in the generation_func field.

    :param course_config_id: The ID of the configuration object to process.
    """
    course_config = LearningCredentialConfiguration.objects.get(id=course_config_id)
    user_ids = course_config.get_eligible_user_ids()
    log.info("The following users are eligible in %s: %s", course_config.learning_context_key, user_ids)
    filtered_user_ids = course_config.filter_out_user_ids_with_certificates(user_ids)
    log.info("The filtered users eligible in %s: %s", course_config.learning_context_key, filtered_user_ids)

    for user_id in filtered_user_ids:
        generate_certificate_for_user_task.delay(course_config_id, user_id)


@app.task
def generate_all_certificates_task():
    """
    Celery task for initiating the processing of certificates for all enabled courses.

    This function fetches all enabled configuration objects,
    and initiates a separate Celery task (process_certificate_for_course) for each of them.
    """
    course_config_ids = LearningCredentialConfiguration.get_enabled_configurations().values_list('id', flat=True)
    for config_id in course_config_ids:
        generate_certificates_for_course_task.delay(config_id)
