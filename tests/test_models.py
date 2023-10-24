"""Tests for the `openedx-certificates` generators module."""

import os
import tempfile

from openedx_certificates.generators import generate_pdf_certificate


class TestGeneratePdfCertificate:
    """Tests for the `generate_pdf_certificate` function."""

    def test_generate_pdf_certificate(self):
        """Test that the function generates a PDF certificate."""
        data = {
            'username': 'Test user',
            'course_name': 'Some course',
            'template_path': 'openedx_certificates/static/certificate_templates/achievement.pdf',
            'output_path': tempfile.NamedTemporaryFile(suffix='.pdf').name,
        }
        generate_pdf_certificate(data)
        assert os.path.isfile(data['output_path'])
