"""Asynchronous Celery tasks."""

from __future__ import annotations

import logging

from openedx_certificates.compat import get_celery_app
from openedx_certificates.models import ExternalCertificateConfiguration

app = get_celery_app()
log = logging.getLogger(__name__)


@app.task
def generate_certificate_for_user_task(cert_config_id: int, user_id: int):
    """
    Celery task for processing a single user's certificate.

    This function retrieves an ExternalCertificateCourse object based on course_id and certificate_type_id,
    retrieves the data using the retrieval_func specified in the associated ExternalCertificateType object,
    and passes this data to the function specified in the generation_func field.

    :param cert_config_id: The ID of the ExternalCertificateConfiguration object to process.
    :param user_id: The ID of the user to process the certificate for.
    """
    cert_config = ExternalCertificateConfiguration.objects.get(id=cert_config_id)
    cert_config.generate_certificate_for_user(user_id, generate_certificate_for_user_task.request.id)


@app.task
def generate_certificates_task(config_id: int):
    """
    Celery task for processing certificates.

    This function retrieves an ExternalCertificateConfig object based on config_id and certificate_type_id,
    retrieves the data using the retrieval_func specified in the associated ExternalCertificateType object,
    and passes this data to the function specified in the generation_func field.

    :param config_id: The ID of the ExternalCertificateConfiguration object to process.
    """
    resource_config = ExternalCertificateConfiguration.objects.get(id=config_id)
    user_ids = resource_config.get_eligible_user_ids()
    log.info("The following users are eligible in %s: %s", resource_config.resource_id, user_ids)
    filtered_user_ids = resource_config.filter_out_user_ids_with_certificates(user_ids)
    log.info("The filtered users eligible in %s: %s", resource_config.resource_id, filtered_user_ids)

    for user_id in filtered_user_ids:
        generate_certificate_for_user_task.delay(config_id, user_id)


@app.task
def generate_all_certificates_task():
    """
    Celery task for initiating the processing of certificates for all enabled resources.

    This function fetches all enabled ExternalCertificateConfiguration objects,
    and initiates a separate Celery task (process_certificate_for_resource) for each of them.
    """
    resource_config_ids = ExternalCertificateConfiguration.get_enabled_configurations().values_list('id', flat=True)
    for config_id in resource_config_ids:
        generate_certificates_task.delay(config_id)
