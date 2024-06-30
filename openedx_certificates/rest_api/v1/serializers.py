from rest_framework import serializers

from openedx_certificates.models import ExternalCertificate


class ExternalCertificateSerializer(serializers.ModelSerializer):
    """Serializer that returns certificate metadata."""
    class Meta:  # noqa: D106
        model = ExternalCertificate
        fields = ('uuid', 'user_full_name', 'modified', 'course_id', 'status', 'invalidation_reason')
