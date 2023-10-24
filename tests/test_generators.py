"""This module contains unit tests for the generate_pdf_certificate function."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from openedx_certificates.generators import generate_pdf_certificate


class TestGeneratePdfCertificate(unittest.TestCase):
    """Unit tests for the generate_pdf_certificate function."""

    def test_generate_pdf_certificate(self):
        """Generate a PDF certificate and check that it contains the correct data."""
        data = {
            'username': 'Test user',
            'course_name': 'Some course',
            'template_path': 'openedx_certificates/static/certificate_templates/achievement.pdf',
        }

        # Generate the PDF certificate.
        with tempfile.NamedTemporaryFile(suffix='.pdf') as certificate_file:
            data['output_path'] = certificate_file.name
            generate_pdf_certificate(data)

            assert Path(data['output_path']).exists()

            pdf_reader = PdfReader(certificate_file)
            page = pdf_reader.pages[0]
            text = page.extract_text()
            assert data['username'] in text
            assert data['course_name'] in text
