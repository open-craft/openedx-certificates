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
from pypdf.constants import UserAccessPermissions

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


@patch("openedx_certificates.generators.LearningCredentialAsset.get_asset_by_slug")
def test_register_font_without_custom_font(mock_get_asset_by_slug: Mock):
    """Test the _register_font falls back to the default font when no custom font is specified."""
    options = {}
    assert _register_font(options) == "Helvetica"
    mock_get_asset_by_slug.assert_not_called()


@patch("openedx_certificates.generators.LearningCredentialAsset.get_asset_by_slug")
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
    ("course_name", "options", "expected"),
    [
        ('Programming 101', {}, {}),  # No options - use default coordinates and colors.
        (
            'Programming 101',
            {
                'name_y': 250,
                'course_name_y': 200,
                'issue_date_y': 150,
                'name_color': '123',
                'course_name_color': '#9B192A',
                'issue_date_color': '#f59a8e',
            },
            {
                'name_color': (17 / 255, 34 / 255, 51 / 255),
                'course_name_color': (155 / 255, 25 / 255, 42 / 255),
                'issue_date_color': (245 / 255, 154 / 255, 142 / 255),
            },
        ),  # Custom coordinates and colors.
        ('Programming\n101\nAdvanced Programming', {}, {}),  # Multiline course name.
    ],
)
@patch('openedx_certificates.generators.canvas.Canvas', return_value=Mock(stringWidth=Mock(return_value=10)))
def test_write_text_on_template(mock_canvas_class: Mock, course_name: str, options: dict[str, int], expected: dict):
    """Test the _write_text_on_template function."""
    username = 'John Doe'
    course_name = 'Programming 101'
    template_height = 300
    template_width = 200
    font = 'Helvetica'
    string_width = mock_canvas_class.return_value.stringWidth.return_value
    test_date = 'April 1, 2021'

    # Reset the mock to discard calls list from previous tests
    mock_canvas_class.reset_mock()

    template_mock = Mock()
    template_mock.mediabox = [0, 0, template_width, template_height]

    # Call the function with test parameters and mocks
    with patch('openedx_certificates.generators.get_localized_certificate_date', return_value=test_date):
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
    expected_issue_date_x = (template_width - string_width) / 2
    expected_issue_date_y = options.get('issue_date_y', 120)

    # Expected colors for setFillColorRGB method
    expected_name_color = expected.get('name_color', (0, 0, 0))
    expected_course_name_color = expected.get('course_name_color', (0, 0, 0))
    expected_issue_date_color = expected.get('issue_date_color', (0, 0, 0))

    # The number of calls to drawString should be 2 (name and issue date) + number of lines in course name.
    assert canvas_object.drawString.call_count == 3 + course_name.count('\n')

    # Check the calls to setFont, setFillColorRGB and drawString methods on Canvas object
    assert canvas_object.setFont.call_args_list[0] == call(font, 32)
    assert canvas_object.setFillColorRGB.call_args_list[0] == call(*expected_name_color)
    assert canvas_object.drawString.call_args_list[0] == call(expected_name_x, expected_name_y, username)
    assert mock_canvas_class.return_value.stringWidth.mock_calls[0][1] == (username,)

    assert canvas_object.setFont.call_args_list[1] == call(font, 28)
    assert canvas_object.setFillColorRGB.call_args_list[1] == call(*expected_course_name_color)

    assert canvas_object.setFont.call_args_list[2] == call(font, 12)
    assert canvas_object.setFillColorRGB.call_args_list[2] == call(*expected_issue_date_color)

    for line_number, line in enumerate(course_name.split('\n')):
        assert mock_canvas_class.return_value.stringWidth.mock_calls[line_number + 1][1] == (line,)
        assert canvas_object.drawString.mock_calls[1 + line_number][1] == (
            expected_course_name_x,
            expected_course_name_y - (line_number * 28 * 1.1),
            line,
        )

    assert mock_canvas_class.return_value.stringWidth.mock_calls[-1][1] == (test_date,)
    assert canvas_object.drawString.mock_calls[-1][1] == (expected_issue_date_x, expected_issue_date_y, test_date)


@override_settings(LMS_ROOT_URL="https://example.com", MEDIA_URL="media/")
@pytest.mark.parametrize(
    "storage",
    [
        (InMemoryStorage()),  # Test a real storage, without mocking.
        (Mock(spec=FileSystemStorage, exists=Mock(return_value=False))),  # Test calls in a mocked storage.
        # Test calls in a mocked storage when the file already exists.
        (Mock(spec=FileSystemStorage, exists=Mock(return_value=True))),
    ],
)
@patch('openedx_certificates.generators.secrets.token_hex', return_value='test_token')
@patch('openedx_certificates.generators.ContentFile', autospec=True)
def test_save_certificate(mock_contentfile: Mock, mock_token_hex: Mock, storage: DefaultStorage | Mock):
    """Test the _save_certificate function."""
    # Mock the certificate.
    certificate = Mock(spec=PdfWriter)
    certificate_uuid = uuid4()
    output_path = f'external_certificates/{certificate_uuid}.pdf'
    pdf_bytes = io.BytesIO()
    certificate.write.return_value = pdf_bytes
    content_file = ContentFile(pdf_bytes.getvalue())
    mock_contentfile.return_value = content_file

    # Expected values for the encrypt method
    expected_pdf_permissions = (
        UserAccessPermissions.PRINT
        | UserAccessPermissions.PRINT_TO_REPRESENTATION
        | UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS
    )

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

    # Check the calls to certificate.encrypt
    certificate.encrypt.assert_called_once_with(
        '',
        mock_token_hex(),
        permissions_flag=expected_pdf_permissions,
        algorithm='AES-256',
    )

    # Allow specifying a custom domain for certificates.
    with override_settings(CERTIFICATES_CUSTOM_DOMAIN='https://example2.com'):
        url = _save_certificate(certificate, certificate_uuid)
        assert url == f'https://example2.com/{certificate_uuid}.pdf'


@pytest.mark.parametrize(
    ("course_name", "options", "expected_template_slug", "expected_course_name"),
    [
        # Default.
        ('Test Course', {'template': 'template_slug'}, 'template_slug', 'Test Course'),
        # Specify a different template for two-line course names and replace semicolon with newline in course name.
        (
            'Test Course; Test Course',
            {'template': 'template_slug', 'template_two_lines': 'template_two_lines_slug'},
            'template_two_lines_slug',
            'Test Course\n Test Course',
        ),
        # Do not replace semicolon with newline when the `template_two_lines` option is not specified.
        ('Test Course; Test Course', {'template': 'template_slug'}, 'template_slug', 'Test Course; Test Course'),
        # Override course name.
        ('Test Course', {'template': 'template_slug', 'course_name': 'Override'}, 'template_slug', 'Override'),
        # Ignore empty course name override.
        ('Test Course', {'template': 'template_slug', 'course_name': ''}, 'template_slug', 'Test Course'),
    ],
)
@patch(
    'openedx_certificates.generators.LearningCredentialAsset.get_asset_by_slug',
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
    expected_course_name: str,
):
    """Test the generate_pdf_certificate function."""
    course_id = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')
    user = Mock()
    mock_get_course_name.return_value = course_name

    result = generate_pdf_certificate(course_id, user, Mock(), options)

    assert result == 'certificate_url'
    mock_get_asset_by_slug.assert_called_with(expected_template_slug)
    mock_get_user_name.assert_called_once_with(user)
    if options.get('course_name'):
        mock_get_course_name.assert_not_called()
    else:
        mock_get_course_name.assert_called_once_with(course_id)
    mock_register_font.assert_called_once_with(options)
    assert mock_pdf_reader.call_count == 2
    mock_pdf_writer.assert_called_once_with()

    mock_write_text_on_template.assert_called_once()
    _, args, _kwargs = mock_write_text_on_template.mock_calls[0]
    assert args[-2] == expected_course_name
    assert args[-1] == options

    mock_save_certificate.assert_called_once()
