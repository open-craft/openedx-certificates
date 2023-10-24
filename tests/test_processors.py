"""This module contains unit tests for the processors module."""

import unittest
from unittest.mock import Mock, patch

import pytest
from opaque_keys.edx.keys import CourseKey

from openedx_certificates.processors import User, retrieve_course_completions, retrieve_subsection_grades


class TestProcessors(unittest.TestCase):
    """Unit tests for the processors module."""

    @pytest.mark.django_db()
    @patch('openedx_certificates.processors.get_section_grades_breakdown_view')
    @patch('openedx_certificates.processors.get_course_grading_policy')
    def test_retrieve_subsection_grades(self, mock_policy: Mock, mock_view: Mock):
        """Test that retrieve_subsection_grades returns the expected results."""
        User.objects.create(username='ecommerce_worker', is_staff=True, is_superuser=True)

        course_id = CourseKey.from_string('org/course/run')
        user_id = 1

        # Mock the response from the API view.
        mock_response = {
            'results': [
                {
                    'username': 'user1',
                    'section_breakdown': [
                        {'category': 'Category 1', 'detail': 'Detail 1', 'percent': 50},
                        {'category': 'Category 1', 'detail': 'Detail 2', 'percent': 50},
                        {'category': 'Category 2', 'detail': 'Detail 3', 'percent': 75},
                        {'category': 'Category 2', 'detail': 'Detail 4', 'percent': 25},
                        {'category': 'Exam', 'detail': 'Detail 5', 'percent': 80},
                    ],
                },
                {
                    'username': 'user2',
                    'section_breakdown': [
                        {'category': 'Category 1', 'detail': 'Detail 1', 'percent': 100},
                        {'category': 'Category 2', 'detail': 'Detail 2', 'percent': 50},
                        {'category': 'Exam', 'detail': 'Detail 3', 'percent': 70},
                    ],
                },
            ],
        }
        mock_view.return_value.get.return_value.data = mock_response

        # Mock the grading policy.
        mock_policy.return_value = [
            {'type': 'Category 1', 'weight': 0.2},
            {'type': 'Category 2', 'weight': 0.3},
            {'type': 'Exam', 'weight': 0.5},
        ]

        # TODO: Fix this.
        # This function should return a boolean if the user passed the threshold.

        # Call the function and check the results.
        expected_results = {
            'user1': 0.6,
            'user2': 0.65,
        }
        results = retrieve_subsection_grades(course_id, user_id)
        assert results == expected_results

    @pytest.mark.django_db()
    @patch('openedx_certificates.processors.CompletionDetailView')
    def test_retrieve_course_completions(self, mock_view):
        """Test that retrieve_course_completions returns the expected results."""
        User.objects.create(username='ecommerce_worker', is_staff=True, is_superuser=True)

        course_id = CourseKey.from_string('org/course/run')
        required_completion = 0.5

        # Mock the response from the API view.
        mock_response = {
            'results': [
                {'username': 'user1', 'completion': {'percent': 0.4}},
                {'username': 'user2', 'completion': {'percent': 0.6}},
                {'username': 'user3', 'completion': {'percent': 0.7}},
            ],
            'pagination': {'next': None},
        }
        mock_view.return_value.get.return_value.data = mock_response

        # Call the function and check the results.
        expected_results = ['user2', 'user3']
        results = retrieve_course_completions(course_id, required_completion)
        assert results == expected_results
