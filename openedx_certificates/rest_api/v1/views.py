from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from openedx_certificates.models import LearningCredential

from .serializers import LearningCredentialSerializer


@api_view(['GET'])
def get_certificate_metadata(request, uuid):
    """
    Retrieve certificate metadata by its UUID.

    Args:
        request (HttpRequest): The request object.
        uuid (UUID): The UUID of the certificate to retrieve.

    Returns:
        Response: A JSON response containing the certificate metadata if found,
                  otherwise an error message.

    Responses:
        200 OK: Successfully retrieved the certificate metadata.
        404 Not Found: Certificate not found or not valid.

    Example:
        GET /api/certificate/123e4567-e89b-12d3-a456-426614174000/

        Response:
        {
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Sample Certificate",
            "issued_date": "2023-01-01",
            "expiry_date": "2024-01-01",
        }
    """
    try:
        certificate = LearningCredential.objects.get(uuid=uuid)
    except LearningCredential.DoesNotExist:
        return Response({'error': 'Certificate not found or not valid'}, status=status.HTTP_404_NOT_FOUND)

    serializer = LearningCredentialSerializer(certificate)
    return Response(serializer.data, status=status.HTTP_200_OK)
