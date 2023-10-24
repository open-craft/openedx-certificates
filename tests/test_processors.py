"""Tests for the certificate processors."""
from __future__ import annotations

from unittest.mock import Mock, call, patch

import pytest
from django.http import QueryDict
from opaque_keys.edx.keys import CourseKey

# noinspection PyProtectedMember
from openedx_certificates.processors import (
    _are_grades_passing_criteria,
    _get_category_weights,
    _get_grades_by_format,
    _prepare_request_to_completion_aggregator,
    retrieve_course_completions,
    retrieve_subsection_grades,
)


@patch(
    'openedx_certificates.processors.get_course_grading_policy',
    return_value=[{'type': 'Homework', 'weight': 0.15}, {'type': 'Exam', 'weight': 0.85}],
)
def test_get_category_weights(mock_get_course_grading_policy: Mock):
    """Check that the course grading policy is retrieved and the category weights are calculated correctly."""
    course_id = Mock(spec=CourseKey)
    assert _get_category_weights(course_id) == {'homework': 0.15, 'exam': 0.85}
    mock_get_course_grading_policy.assert_called_once_with(course_id)


@patch('openedx_certificates.processors.prefetch_course_grades')
@patch('openedx_certificates.processors.get_course_grade_factory')
def test_get_grades_by_format(mock_get_course_grade_factory: Mock, mock_prefetch_course_grades: Mock):
    """Test that grades are retrieved for each user and categorized by assignment types."""
    course_id = Mock(spec=CourseKey)
    users = [Mock(name="User1", id=101), Mock(name="User2", id=102)]

    mock_read_grades = Mock()
    mock_read_grades.return_value.graded_subsections_by_format.return_value = {
        'Homework': {'subsection1': Mock(graded_total=Mock(earned=50.0, possible=100.0))},
        'Exam': {'subsection2': Mock(graded_total=Mock(earned=90.0, possible=100.0))},
    }
    mock_get_course_grade_factory.return_value.read = mock_read_grades

    result = _get_grades_by_format(course_id, users)

    assert result == {101: {'homework': 50.0, 'exam': 90.0}, 102: {'homework': 50.0, 'exam': 90.0}}
    mock_prefetch_course_grades.assert_called_once_with(course_id, users)
    mock_get_course_grade_factory.assert_called_once()

    mock_read_grades.assert_has_calls(
        [
            call(users[0], course_key=course_id),
            call().graded_subsections_by_format(),
            call(users[1], course_key=course_id),
            call().graded_subsections_by_format(),
        ],
    )


_are_grades_passing_criteria_test_data = [
    (
        "All grades are passing",
        {"homework": 90, "lab": 90, "exam": 90},
        {"homework": 85, "lab": 80, "exam": 60, "total": 50},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        True,
    ),
    (
        "The homework grade is failing",
        {"homework": 80, "lab": 90, "exam": 70},
        {"homework": 85, "lab": 80, "exam": 60, "total": 50},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        False,
    ),
    (
        "The total grade is failing",
        {"homework": 90, "lab": 90, "exam": 70},
        {"homework": 85, "lab": 80, "exam": 60, "total": 300},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        False,
    ),
    (
        "Only the total grade is required",
        {"homework": 90, "lab": 90, "exam": 70},
        {"total": 50},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        True,
    ),
    (
        "Total grade is not required",
        {"homework": 90, "lab": 90, "exam": 70},
        {"homework": 85, "lab": 80},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        True,
    ),
    (
        "Required grades are not defined",
        {"homework": 80, "lab": 90, "exam": 70},
        {},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        True,
    ),
    (
        "User has no grades",
        {},
        {"homework": 85, "lab": 80, "exam": 60, "total": 240},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        False,
    ),
    ("User has no grades and the required grades are not defined", {}, {}, {}, True),
    (
        "User has no grades in a required category",
        {"homework": 90, "lab": 85},
        {"homework": 85, "lab": 80, "exam": 60},
        {"homework": 0.3, "lab": 0.3, "exam": 0.4},
        False,
    ),
]


@pytest.mark.parametrize(
    ('desc', 'user_grades', 'required_grades', 'category_weights', 'expected'),
    _are_grades_passing_criteria_test_data,
    ids=[i[0] for i in _are_grades_passing_criteria_test_data],
)
def test_are_grades_passing_criteria(
    desc: str,  # noqa: ARG001
    user_grades: dict[str, float],
    required_grades: dict[str, float],
    category_weights: dict[str, float],
    expected: bool,  # noqa: FBT001
):
    """Test that the user grades are compared to the required grades correctly."""
    assert _are_grades_passing_criteria(user_grades, required_grades, category_weights) == expected


def test_are_grades_passing_criteria_invalid_grade_category():
    """Test that an exception is raised if user grades contain a category that is not defined in the grading policy."""
    with pytest.raises(ValueError, match='unknown_category'):
        _are_grades_passing_criteria(
            {"homework": 90, "unknown_category": 90},
            {"total": 175},
            {"homework": 0.5, "lab": 0.5},
        )


@patch('openedx_certificates.processors.get_course_enrollments')
@patch('openedx_certificates.processors._get_grades_by_format')
@patch('openedx_certificates.processors._get_category_weights')
@patch('openedx_certificates.processors._are_grades_passing_criteria')
def test_retrieve_subsection_grades(
    mock_are_grades_passing_criteria: Mock,
    mock_get_category_weights: Mock,
    mock_get_grades_by_format: Mock,
    mock_get_course_enrollments: Mock,
):
    """Test that the function returns the eligible users."""
    course_id = Mock(spec=CourseKey)
    options = {
        'required_grades': {
            'homework': 0.4,
            'exam': 0.9,
            'total': 0.8,
        },
    }
    users = [Mock(name="User1", id=101), Mock(name="User2", id=102)]
    grades = {
        101: {'homework': 0.5, 'exam': 0.9},
        102: {'homework': 0.3, 'exam': 0.95},
    }
    required_grades = {'homework': 40.0, 'exam': 90.0, 'total': 80.0}
    weights = {'homework': 0.2, 'exam': 0.7, 'lab': 0.1}

    mock_get_course_enrollments.return_value = users
    mock_get_grades_by_format.return_value = grades
    mock_get_category_weights.return_value = weights
    mock_are_grades_passing_criteria.side_effect = [True, False]

    result = retrieve_subsection_grades(course_id, options)

    assert result == [101]
    mock_get_course_enrollments.assert_called_once_with(course_id)
    mock_get_grades_by_format.assert_called_once_with(course_id, users)
    mock_get_category_weights.assert_called_once_with(course_id)
    mock_are_grades_passing_criteria.assert_has_calls(
        [
            call(grades[101], required_grades, weights),
            call(grades[102], required_grades, weights),
        ],
    )


def test_prepare_request_to_completion_aggregator():
    """Test that the request to the completion aggregator API is prepared correctly."""
    course_id = Mock(spec=CourseKey)
    query_params = {'param1': 'value1', 'param2': 'value2'}
    url = '/test_url/'

    with patch('openedx_certificates.processors.get_user_model') as mock_get_user_model, patch(
        'openedx_certificates.processors.CompletionDetailView',
    ) as mock_view_class:
        staff_user = Mock(is_staff=True)
        mock_get_user_model().objects.filter().first.return_value = staff_user

        view = _prepare_request_to_completion_aggregator(course_id, query_params, url)

        mock_view_class.assert_called_once()
        assert view.request.course_id == course_id
        # noinspection PyUnresolvedReferences
        assert view._effective_user is staff_user
        assert isinstance(view, mock_view_class.return_value.__class__)

        # Create a QueryDict from the query_params dictionary.
        query_params_qdict = QueryDict('', mutable=True)
        query_params_qdict.update(query_params)
        assert view.request.query_params.urlencode() == query_params_qdict.urlencode()


@patch('openedx_certificates.processors._prepare_request_to_completion_aggregator')
@patch('openedx_certificates.processors.get_user_model')
def test_retrieve_course_completions(mock_get_user_model: Mock, mock_prepare_request_to_completion_aggregator: Mock):
    """Test that we retrieve the course completions for all users and return IDs of users who meet the criteria."""
    course_id = Mock(spec=CourseKey)
    options = {'required_completion': 0.8}
    completions_page1 = {
        'pagination': {'next': '/completion-aggregator/v1/course/{course_id}/?page=2&page_size=1000'},
        'results': [
            {'username': 'user1', 'completion': {'percent': 0.9}},
        ],
    }
    completions_page2 = {
        'pagination': {'next': None},
        'results': [
            {'username': 'user2', 'completion': {'percent': 0.7}},
            {'username': 'user3', 'completion': {'percent': 0.8}},
        ],
    }

    mock_view_page1 = Mock()
    mock_view_page1.get.return_value.data = completions_page1
    mock_view_page2 = Mock()
    mock_view_page2.get.return_value.data = completions_page2
    mock_prepare_request_to_completion_aggregator.side_effect = [mock_view_page1, mock_view_page2]

    def filter_side_effect(*_args, **kwargs) -> list[int]:
        """
        A mock side effect function for User.objects.filter().

        It allows testing this code without a database access.

        :returns: The user IDs corresponding to the provided usernames.
        """
        usernames = kwargs['username__in']

        values_list_mock = Mock()
        values_list_mock.return_value = [username_id_map[username] for username in usernames]
        queryset_mock = Mock()
        queryset_mock.values_list = values_list_mock

        return queryset_mock

    username_id_map = {"user1": 1, "user2": 2, "user3": 3}
    mock_user_model = Mock()
    mock_user_model.objects.filter.side_effect = filter_side_effect
    mock_get_user_model.return_value = mock_user_model

    result = retrieve_course_completions(course_id, options)

    assert result == [1, 3]
    mock_prepare_request_to_completion_aggregator.assert_has_calls(
        [
            call(course_id, {'page_size': 1000, 'page': 1}, f'/completion-aggregator/v1/course/{course_id}/'),
            call(course_id, {'page_size': 1000, 'page': 2}, f'/completion-aggregator/v1/course/{course_id}/'),
        ],
    )
    mock_view_page1.get.assert_called_once_with(mock_view_page1.request, str(course_id))
    mock_view_page2.get.assert_called_once_with(mock_view_page2.request, str(course_id))
    mock_user_model.objects.filter.assert_called_once_with(username__in=['user1', 'user3'])
