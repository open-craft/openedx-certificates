from rest_framework import serializers

from openedx_certificates.models import LearningCredential


class LearningCredentialSerializer(serializers.ModelSerializer):
    """Serializer that returns certificate metadata."""
    class Meta:  # noqa: D106
        model = LearningCredential
        fields = ('uuid', 'user_full_name', 'modified', 'learning_context_key', 'status', 'invalidation_reason')
