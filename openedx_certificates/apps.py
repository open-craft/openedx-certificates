"""openedx_certificates Django application initialization."""

from __future__ import annotations

from typing import ClassVar

from django.apps import AppConfig

from edx_django_utils.plugins.constants import PluginSettings, PluginURLs


class OpenedxCertificatesConfig(AppConfig):
    """Configuration for the openedx_certificates Django application."""

    name = 'openedx_certificates'

    # https://edx.readthedocs.io/projects/edx-django-utils/en/latest/plugins/how_tos/how_to_create_a_plugin_app.html
    plugin_app: ClassVar[dict[str, dict[str, dict]]] = {
        PluginSettings.CONFIG: {
            'lms.djangoapp': {
                'common': {PluginSettings.RELATIVE_PATH: f'{PluginSettings.DEFAULT_RELATIVE_PATH}.common'},
                'production': {PluginSettings.RELATIVE_PATH: f'{PluginSettings.DEFAULT_RELATIVE_PATH}.production'},
            },
        },
        PluginURLs.CONFIG: {
            'lms.djangoapp': {
                PluginURLs.NAMESPACE: name,
                PluginURLs.APP_NAME: name,
                PluginURLs.REGEX: rf'^{name}/',

            },
        },
    }
