from django.urls import path

from .views import get_certificate_metadata

urlpatterns = [
    path('metadata/<uuid:uuid>/', get_certificate_metadata, name='get_certificate_metadata'),
]
