"""openedx_certificates Django application initialization."""

from __future__ import annotations

from typing import ClassVar

from django.apps import AppConfig


class OpenedxCertificatesConfig(AppConfig):
    """Configuration for the openedx_certificates Django application."""

    name = 'openedx_certificates'

    # https://edx.readthedocs.io/projects/edx-django-utils/en/latest/plugins/how_tos/how_to_create_a_plugin_app.html
    plugin_app: ClassVar[dict[str, dict[str, dict]]] = {}
