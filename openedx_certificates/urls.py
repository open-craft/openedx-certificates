"""URLs for openedx_certificates."""

from django.urls import include, path
from django.views.generic import TemplateView

from .rest_api import urls as rest_api_urls

urlpatterns = [  # pragma: no cover
    # TODO: Fill in URL patterns and views here.
    # re_path(r'', TemplateView.as_view(template_name="openedx_certificates/base.html")),  # noqa: ERA001, RUF100
    path("api/", include(rest_api_urls)),
    path("validate/", TemplateView.as_view(template_name="openedx_certificates/validate.html")),
]
