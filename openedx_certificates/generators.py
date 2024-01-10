"""
This module provides functions to generate certificates.

The functions prefixed with `generate_` are automatically detected by the admin page and are used to generate the
certificates for the users.

We will move this module to an external repository (a plugin).
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from openedx_certificates.compat import get_course_name
from openedx_certificates.models import ExternalCertificateAsset

log = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from uuid import UUID

    from django.contrib.auth.models import User
    from opaque_keys.edx.keys import CourseKey


def _get_user_name(user: User) -> str:
    """
    Retrieve the user's name.

    :param user: The user to generate the certificate for.
    :return: Username.
    """
    return user.profile.name or f"{user.first_name} {user.last_name}"


def _register_font(options: dict[str, Any]) -> str:
    """
    Register a custom font if specified in options. If not specified, use the default font (Helvetica).

    :param options: A dictionary containing the font.
    :returns: The font name.
    """
    if font := options.get('font'):
        pdfmetrics.registerFont(TTFont(font, ExternalCertificateAsset.get_asset_by_slug(font)))

    return font or 'Helvetica'


def _write_text_on_template(template: any, font: str, username: str, course_name: str, options: dict[str, Any]) -> any:
    """
    Prepare a new canvas and write the user and course name onto it.

    :param template: Pdf template.
    :param font: Font name.
    :param username: The name of the user to generate the certificate for.
    :param course_name: The name of the course the learner completed.
    :param options: A dictionary containing the Y coordinates for name and course name.
    :returns: A canvas with written data.
    """
    template_width, template_height = template.mediabox[2:]
    pdf_canvas = canvas.Canvas(io.BytesIO(), pagesize=(template_width, template_height))
    pdf_canvas.setFont(font, 32)
    # Write the learner name.
    name_x = (template_width - pdf_canvas.stringWidth(username)) / 2
    name_y = options.get('name_y', 290)
    pdf_canvas.drawString(name_x, name_y, username)
    # Write the course name.
    pdf_canvas.setFont(font, 28)
    course_name_x = (template_width - pdf_canvas.stringWidth(course_name)) / 2
    course_name_y = options.get('course_name_y', 220)
    pdf_canvas.drawString(course_name_x, course_name_y, course_name)
    return pdf_canvas


def _save_certificate(certificate: PdfWriter, certificate_uuid: UUID) -> str:
    """
    Save the final PDF file to BytesIO and upload it using Django default storage.

    :param certificate: Pdf certificate.
    :param certificate_uuid: The UUID of the certificate.
    :returns: The URL of the saved certificate.
    """
    # Save the final PDF file to BytesIO.
    output_path = f'external_certificates/{certificate_uuid}.pdf'
    pdf_bytes = io.BytesIO()
    certificate.write(pdf_bytes)
    pdf_bytes.seek(0)  # Rewind to start.
    # Upload with Django default storage.
    certificate_file = ContentFile(pdf_bytes.read())
    # Delete the file if it already exists.
    if default_storage.exists(output_path):
        default_storage.delete(output_path)
    default_storage.save(output_path, certificate_file)
    if isinstance(default_storage, FileSystemStorage):
        url = f"{settings.LMS_ROOT_URL}{settings.MEDIA_URL}{output_path}"
    else:
        url = default_storage.url(output_path)
    return url


def generate_pdf_certificate(course_id: CourseKey, user: User, certificate_uuid: UUID, options: dict[str, Any]) -> str:
    """
    Generate a PDF certificate.

    :param course_id: The ID of the course the learner completed.
    :param user: The user to generate the certificate for.
    :param certificate_uuid: The UUID of the certificate to generate.
    :param options: The custom options for the certificate.
    :returns: The URL of the saved certificate.

    Options:
      - template: The path to the PDF template file.
      - template_two-lines: The path to the PDF template file for two-line course names.
        A two-line course name is specified by using a semicolon as a separator.
      - font: The name of the font to use.
      - name_y: The Y coordinate of the name on the certificate (vertical position on the template).
      - course_name_y: The Y coordinate of the course name on the certificate (vertical position on the template).
    """
    log.info("Starting certificate generation for user %s", user.id)
    # Get template from the ExternalCertificateAsset.
    template_file = ExternalCertificateAsset.get_asset_by_slug(options['template'])

    username = _get_user_name(user)
    course_name = get_course_name(course_id)

    # HACK: We support two-line strings by using a semicolon as a separator.
    if ';' in course_name and (template_path := options.get('template_two-lines')):
        template_file = ExternalCertificateAsset.get_asset_by_slug(template_path)
        course_name = course_name.replace(';', '\n')

    font = _register_font(options)

    # Load the PDF template.
    with template_file.open('rb') as template_file:
        template = PdfReader(template_file).pages[0]

        certificate = PdfWriter()

        # Create a new canvas, prepare the page and write the data
        pdf_canvas = _write_text_on_template(template, font, username, course_name, options)

        overlay_pdf = PdfReader(io.BytesIO(pdf_canvas.getpdfdata()))
        template.merge_page(overlay_pdf.pages[0])
        certificate.add_page(template)

        url = _save_certificate(certificate, certificate_uuid)

        log.info("Certificate saved to %s", url)
    return url
