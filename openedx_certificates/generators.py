"""
This module provides functions to generate certificates.

The functions prefixed with `generate_` are automatically detected by the admin page and are used to generate the
certificates for the users.

We will move this module to an external repository (a plugin).
"""

from __future__ import annotations  # noqa: I001

import io
import logging
import secrets
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage

from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from openedx_certificates.compat import get_course_name, get_default_storage_url, get_localized_certificate_date
from openedx_certificates.models import ExternalCertificateAsset

if TYPE_CHECKING:  # pragma: no cover
    from django.contrib.auth.models import User  # noqa: I001
    from uuid import UUID

log = logging.getLogger(__name__)


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


def _write_text_on_template(
    template: any,
    font: str,
    username: str,
    resource_name: str,
    options: dict[str, Any],
) -> any:
    """
    Prepare a new canvas and write the user and resource name onto it.

    :param template: Pdf template.
    :param font: Font name.
    :param username: The name of the user to generate the certificate for.
    :param resource_name: The name of the resource the learner completed (e.g. course, learning_path).
    :param options: A dictionary documented in the `generate_pdf_certificate` function.
    :returns: A canvas with written data.
    """

    def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
        """
        Convert a hexadecimal color code to an RGB tuple with floating-point values.

        :param hex_color: A hexadecimal color string, which can start with '#' and be either 3 or 6 characters long.
        :returns: A tuple representing the RGB color as (red, green, blue), with each value ranging from 0.0 to 1.0.
        """
        hex_color = hex_color.lstrip('#')
        # Expand shorthand form (e.g. "158" to "115588")
        if len(hex_color) == 3:
            hex_color = ''.join([c * 2 for c in hex_color])

        # noinspection PyTypeChecker
        return tuple(int(hex_color[i : i + 2], 16) / 255 for i in range(0, 6, 2))

    template_width, template_height = template.mediabox[2:]
    pdf_canvas = canvas.Canvas(io.BytesIO(), pagesize=(template_width, template_height))

    # Write the learner name.
    pdf_canvas.setFont(font, 32)
    name_color = options.get('name_color', '#000')
    pdf_canvas.setFillColorRGB(*hex_to_rgb(name_color))

    name_x = (template_width - pdf_canvas.stringWidth(username)) / 2
    name_y = options.get('name_y', 290)
    pdf_canvas.drawString(name_x, name_y, username)

    # Write the course name.
    pdf_canvas.setFont(font, 28)
    resource_name_color = options.get('resource_name_color', '#000')
    pdf_canvas.setFillColorRGB(*hex_to_rgb(resource_name_color))

    resource_name_y = options.get('resource_name_y', 220)
    resource_name_line_height = 28 * 1.1

    # Split the course name into lines and write each of them in the center of the template.
    for line_number, line in enumerate(resource_name.split('\n')):
        line_x = (template_width - pdf_canvas.stringWidth(line)) / 2
        line_y = resource_name_y - (line_number * resource_name_line_height)
        pdf_canvas.drawString(line_x, line_y, line)

    # Write the issue date.
    issue_date = get_localized_certificate_date()
    pdf_canvas.setFont(font, 12)
    issue_date_color = options.get('issue_date_color', '#000')
    pdf_canvas.setFillColorRGB(*hex_to_rgb(issue_date_color))

    issue_date_x = (template_width - pdf_canvas.stringWidth(issue_date)) / 2
    issue_date_y = options.get('issue_date_y', 120)
    pdf_canvas.drawString(issue_date_x, issue_date_y, issue_date)

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

    view_print_extract_permission = (
        UserAccessPermissions.PRINT
        | UserAccessPermissions.PRINT_TO_REPRESENTATION
        | UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS
    )
    certificate.encrypt('', secrets.token_hex(32), permissions_flag=view_print_extract_permission, algorithm='AES-256')

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
        url = f"{get_default_storage_url()}{output_path}"
    else:
        url = default_storage.url(output_path)

    if custom_domain := getattr(settings, 'CERTIFICATES_CUSTOM_DOMAIN', None):
        url = f"{custom_domain}/{certificate_uuid}.pdf"

    return url


def generate_pdf_certificate(
    resource_id: str,
    resource_type: str,
    user: User,
    certificate_uuid: UUID,
    options: dict[str, Any],
) -> str:
    """
    Generate a PDF certificate.

    :param resource_id: The ID of the course or learning path the learner completed.
    :param resource_type: The type of the resource ('course' or 'learning_path').
    :param certificate_uuid: The UUID of the certificate to generate.
    :param options: The custom options for the certificate.
    :returns: The URL of the saved certificate.

    Options:
      - template: The path to the PDF template file.
      - template_two_lines: The path to the PDF template file for two-line resource names.
        A two-line resource name is specified by using a semicolon as a separator.
      - font: The name of the font to use.
      - name_y: The Y coordinate of the name on the certificate (vertical position on the template).
      - name_color: The color of the name on the certificate (hexadecimal color code).
      - resource_name: Specify the resource name to use instead of the Display Name retrieved from Open edX.
      - resource_name_y: The Y coordinate of the resource name.
      - resource_name_color: The color of the resource name.
      - issue_date_y: The Y coordinate of the issue date on the certificate (vertical position on the template).
      - issue_date_color: The color of the issue date on the certificate (hexadecimal color code).
    """
    log.info("Starting certificate generation for user %s", user.id)

    username = _get_user_name(user)
    resource_name = options.get('resource_name')

    if resource_type == 'course':
        resource_name = resource_name or get_course_name(resource_id)
    elif resource_type == 'learning_path':
        if not apps.is_installed('learning_paths'):
            resource_name = ""
        try:
            LearningPath = apps.get_model('learning_paths', 'LearningPath')
            resource_name = LearningPath.objects.get(uuid=resource_id).display_name
        except Exception:  # noqa: BLE001
            resource_name = ""
    else:
        msg = f"Unsupported resource type: {resource_type}"
        raise ValueError(msg)

    # Get template from the ExternalCertificateAsset.
    # HACK: We support two-line strings by using a semicolon as a separator.
    if ';' in resource_name and (template_path := options.get('template_two_lines')):
        template_file = ExternalCertificateAsset.get_asset_by_slug(template_path)
        resource_name = resource_name.replace(';', '\n')
    else:
        template_file = ExternalCertificateAsset.get_asset_by_slug(options['template'])

    font = _register_font(options)

    # Load the PDF template.
    with template_file.open('rb') as template_file:
        template = PdfReader(template_file).pages[0]

        certificate = PdfWriter()

        # Create a new canvas, prepare the page and write the data
        pdf_canvas = _write_text_on_template(template, font, username, resource_name, options)

        overlay_pdf = PdfReader(io.BytesIO(pdf_canvas.getpdfdata()))
        template.merge_page(overlay_pdf.pages[0])
        certificate.add_page(template)

        url = _save_certificate(certificate, certificate_uuid)

        log.info("Certificate saved to %s", url)
    return url
