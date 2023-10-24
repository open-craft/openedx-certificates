"""This module contains unit tests for the generate_pdf_certificate function."""
from __future__ import annotations

import io
from unittest.mock import Mock, call, patch
from uuid import uuid4

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import DefaultStorage, FileSystemStorage
from django.test import override_settings
from inmemorystorage import InMemoryStorage
from opaque_keys.edx.keys import CourseKey
from pypdf import PdfWriter

from openedx_certificates.generators import (
    _get_user_name,
    _register_font,
    _save_certificate,
    _write_text_on_template,
    generate_pdf_certificate,
)


def test_get_user_name():
    """Test the _get_user_name function."""
    user = Mock(first_name="First", last_name="Last")
    user.profile.name = "Profile Name"

    # Test when profile name is available
    assert _get_user_name(user) == "Profile Name"

    # Test when profile name is not available
    user.profile.name = None
    assert _get_user_name(user) == "First Last"


@patch("openedx_certificates.generators.ExternalCertificateAsset.get_asset_by_slug")
def test_register_font_without_custom_font(mock_get_asset_by_slug: Mock):
    """Test the _register_font falls back to the default font when no custom font is specified."""
    options = {}
    assert _register_font(options) == "Helvetica"
    mock_get_asset_by_slug.assert_not_called()


@patch("openedx_certificates.generators.ExternalCertificateAsset.get_asset_by_slug")
@patch('openedx_certificates.generators.TTFont')
@patch("openedx_certificates.generators.pdfmetrics.registerFont")
def test_register_font_with_custom_font(mock_register_font: Mock, mock_font_class: Mock, mock_get_asset_by_slug: Mock):
    """Test the _register_font registers the custom font when specified."""
    custom_font = "MyFont"
    options = {"font": custom_font}

    mock_get_asset_by_slug.return_value = "font_path"

    assert _register_font(options) == custom_font
    mock_get_asset_by_slug.assert_called_once_with(custom_font)
    mock_font_class.assert_called_once_with(custom_font, mock_get_asset_by_slug.return_value)
    mock_register_font.assert_called_once_with(mock_font_class.return_value)


@pytest.mark.parametrize(
    ("username", "course_name", "options"),
    [
        ('John Doe', 'Programming 101', {}),  # No options - use default coordinates.
        ('John Doe', 'Programming 101', {'name_y': 250, 'course_name_y': 200}),  # Custom coordinates.
    ],
)
@patch('openedx_certificates.generators.canvas.Canvas', return_value=Mock(stringWidth=Mock(return_value=10)))
def test_write_text_on_template(mock_canvas_class: Mock, username: str, course_name: str, options: dict[str, int]):
    """Test the _write_text_on_template function."""
    template_height = 300
    template_width = 200
    font = 'Helvetica'
    string_width = mock_canvas_class.return_value.stringWidth.return_value

    # Reset the mock to discard calls list from previous tests
    mock_canvas_class.reset_mock()

    template_mock = Mock()
    template_mock.mediabox = [0, 0, template_width, template_height]

    # Call the function with test parameters and mocks
    _write_text_on_template(template_mock, font, username, course_name, options)

    # Verifying that Canvas was the correct pagesize.
    # Use `call_args_list` to ignore the first argument, which is an instance of io.BytesIO.
    assert mock_canvas_class.call_args_list[0][1]['pagesize'] == (template_width, template_height)

    # Mock Canvas object retrieved from Canvas constructor call
    canvas_object = mock_canvas_class.return_value

    # Expected coordinates for drawString method, based on fixed stringWidth
    expected_name_x = (template_width - string_width) / 2
    expected_name_y = options.get('name_y', 290)
    expected_course_name_x = (template_width - string_width) / 2
    expected_course_name_y = options.get('course_name_y', 220)

    # Check the calls to setFont and drawString methods on Canvas object
    assert canvas_object.setFont.call_args_list[0] == call(font, 32)
    assert canvas_object.drawString.call_args_list[0] == call(expected_name_x, expected_name_y, username)

    assert canvas_object.setFont.call_args_list[1] == call(font, 28)
    assert canvas_object.drawString.call_args_list[1] == call(
        expected_course_name_x,
        expected_course_name_y,
        course_name,
    )


@override_settings(LMS_ROOT_URL="http://example.com", MEDIA_URL="media/")
@pytest.mark.parametrize(
    "storage",
    [
        (InMemoryStorage()),  # Test a real storage, without mocking.
        (Mock(spec=FileSystemStorage, exists=Mock(return_value=False))),  # Test calls in a mocked storage.
        # Test calls in a mocked storage when the file already exists.
        (Mock(spec=FileSystemStorage, exists=Mock(return_value=True))),
    ],
)
@patch('openedx_certificates.generators.ContentFile', autospec=True)
def test_save_certificate(mock_contentfile: Mock, storage: DefaultStorage | Mock):
    """Test the _save_certificate function."""
    # Mock the certificate.
    certificate = Mock(spec=PdfWriter)
    certificate_uuid = uuid4()
    output_path = f'external_certificates/{certificate_uuid}.pdf'
    pdf_bytes = io.BytesIO()
    certificate.write.return_value = pdf_bytes
    content_file = ContentFile(pdf_bytes.getvalue())
    mock_contentfile.return_value = content_file

    # Run the function.
    with patch('openedx_certificates.generators.default_storage', storage):
        url = _save_certificate(certificate, certificate_uuid)

    # Check the calls in a mocked storage.
    if isinstance(storage, Mock):
        storage.exists.assert_called_once_with(output_path)
        storage.save.assert_called_once_with(output_path, content_file)
        storage.url.assert_not_called()
        if storage.exists.return_value:
            storage.delete.assert_called_once_with(output_path)
        else:
            storage.delete.assert_not_called()

    if isinstance(storage, Mock):
        assert url == f'{settings.LMS_ROOT_URL}/media/{output_path}'
    else:
        assert url == f'/{output_path}'


@pytest.mark.parametrize(
    ("course_name", "options", "expected_template_slug"),
    [
        ('Test Course', {'template': 'template_slug'}, 'template_slug'),
        ('Test Course;Test Course', {'template': 'template_slug'}, 'template_slug'),
        (
            'Test Course;Test Course',
            {'template': 'template_slug', 'template_two-lines': 'template_two_lines_slug'},
            'template_two_lines_slug',
        ),
    ],
)
@patch(
    'openedx_certificates.generators.ExternalCertificateAsset.get_asset_by_slug',
    return_value=Mock(
        open=Mock(
            return_value=Mock(
                __enter__=Mock(return_value=Mock(read=Mock(return_value=b'pdf_data'))),
                __exit__=Mock(return_value=None),
            ),
        ),
    ),
)
@patch('openedx_certificates.generators._get_user_name')
@patch('openedx_certificates.generators.get_course_name')
@patch('openedx_certificates.generators._register_font')
@patch('openedx_certificates.generators.PdfReader')
@patch('openedx_certificates.generators.PdfWriter')
@patch(
    'openedx_certificates.generators._write_text_on_template',
    return_value=Mock(getpdfdata=Mock(return_value=b'pdf_data')),
)
@patch('openedx_certificates.generators._save_certificate', return_value='certificate_url')
def test_generate_pdf_certificate(  # noqa: PLR0913
    mock_save_certificate: Mock,
    mock_write_text_on_template: Mock,
    mock_pdf_writer: Mock,
    mock_pdf_reader: Mock,
    mock_register_font: Mock,
    mock_get_course_name: Mock,
    mock_get_user_name: Mock,
    mock_get_asset_by_slug: Mock,
    course_name: str,
    options: dict[str, str],
    expected_template_slug: str,
):
    """Test the generate_pdf_certificate function."""
    course_id = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')
    user = Mock()
    mock_get_course_name.return_value = course_name

    result = generate_pdf_certificate(course_id, user, Mock(), options)

    assert result == 'certificate_url'
    mock_get_asset_by_slug.assert_called_with(expected_template_slug)
    mock_get_user_name.assert_called_once_with(user)
    mock_get_course_name.assert_called_once_with(course_id)
    mock_register_font.assert_called_once_with(options)
    mock_pdf_reader.assert_called()
    mock_pdf_writer.assert_called()
    mock_write_text_on_template.assert_called_once()
    mock_save_certificate.assert_called_once()
