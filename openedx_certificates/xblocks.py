from __future__ import annotations

import logging

from xblock.core import XBlock
from xblock.fields import Scope, String
from xblock.fragment import Fragment

try:
    from xblock.utils.resources import ResourceLoader
    from xblock.utils.settings import ThemableXBlockMixin, XBlockWithSettingsMixin
    from xblock.utils.studio_editable import StudioEditableXBlockMixin
except ModuleNotFoundError:  # For backward compatibility with releases older than Quince.
    from xblockutils.resources import ResourceLoader
    from xblockutils.settings import ThemableXBlockMixin, XBlockWithSettingsMixin
    from xblockutils.studio_editable import StudioEditableXBlockMixin

from .api import generate_certificate_for_user, get_eligible_users_by_certificate_type, get_user_certificates_by_type

loader = ResourceLoader(__name__)
logger = logging.getLogger(__name__)


class CertificatesXBlock(StudioEditableXBlockMixin, XBlock):
    """
    XBlock that displays the certificate eligibility status and allows eligible users to generate certificates.
    """

    display_name = String(
        help='The display name for this component.',
        scope=Scope.content,
        display_name="Display name",
        default='Certificates',
    )

    def student_view(self, context) -> Fragment:
        """
        Main view for the student. Displays the certificate eligibility or ineligibility status.
        """
        fragment = Fragment()
        eligible_types = False
        certificates = []

        if not (is_author_mode := getattr(self.runtime, 'is_author_mode', False)):
            certificates = self.get_certificates()
            eligible_types = self.get_eligible_certificate_types()

            # Filter out the eligible types that already have a certificate generated
            for cert_type in certificates.keys():
                if cert_type in eligible_types:
                    del eligible_types[cert_type]

        fragment.add_content(
            loader.render_django_template(
                'public/html/certificates_xblock.html',
                {
                    'certificates': certificates,
                    'eligible_types': eligible_types,
                    'is_author_mode': is_author_mode,
                },
            )
        )

        fragment.add_css_url(self.runtime.local_resource_url(self, "public/css/certificates_xblock.css"))
        fragment.add_javascript_url(self.runtime.local_resource_url(self, "public/js/certificates_xblock.js"))
        fragment.initialize_js('CertificatesXBlock')
        return fragment

    def get_eligible_certificate_types(self) -> dict[str, bool]:
        """
        Retrieve the eligibility status for each certificate type.
        """
        eligible_users = get_eligible_users_by_certificate_type(self.runtime.course_id, user_id=self.scope_ids.user_id)

        return {certificate_type: bool(users) for certificate_type, users in eligible_users.items()}

    def get_certificates(self) -> dict[str, dict[str, str]]:
        """
        Retrieve the certificates for the current user in the current course.
        """
        return get_user_certificates_by_type(self.runtime.course_id, self.scope_ids.user_id)

    @XBlock.json_handler
    def generate_certificate(self, data, suffix='') -> dict[str, str]:
        """
        Handler for generating a certificate for a specific type.
        """
        certificate_type = data.get('certificate_type')
        if not certificate_type:
            return {'status': 'error', 'message': 'No certificate type specified.'}

        course_id = self.runtime.course_id
        user_id = self.scope_ids.user_id
        logger.info(
            'Generating a certificate for user %s in course %s with type %s.', user_id, course_id, certificate_type
        )

        try:
            generate_certificate_for_user(course_id, certificate_type, user_id)
        except ValueError as e:
            return {'status': 'error', 'message': str(e)}
        return {'status': 'success'}
