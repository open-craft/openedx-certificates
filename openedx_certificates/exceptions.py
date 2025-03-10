"""Custom exceptions for the openedx-certificates app."""


class AssetNotFoundError(Exception):
    """Raised when the asset_slug is not found in the LearningCredentialAsset model."""


class CertificateGenerationError(Exception):
    """Raised when the certificate generation Celery task fails."""
