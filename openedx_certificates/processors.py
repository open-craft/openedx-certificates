"""
This module contains processors for certificate criteria.

The functions prefixed with `retrieve_` are automatically detected by the admin page and are used to retrieve the
IDs of the users that meet the criteria for the certificate type.

We will move this module to an external repository (a plugin).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from completion_aggregator.api.v1.views import CompletionDetailView
from django.contrib.auth import get_user_model
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from openedx_certificates.compat import (
    get_course_enrollments,
    get_course_grade_factory,
    get_course_grading_policy,
    prefetch_course_grades,
)

if TYPE_CHECKING:  # pragma: no cover
    from django.contrib.auth.models import User
    from opaque_keys.edx.keys import CourseKey
    from rest_framework.views import APIView


log = logging.getLogger(__name__)


def _get_category_weights(course_id: CourseKey) -> dict[str, float]:
    """
    Retrieve the course grading policy and return the weight of each category.

    :param course_id: The course ID to get the grading policy for.
    :returns: A dictionary with the weight of each category.
    """
    log.debug('Getting the course grading policy.')
    grading_policy = get_course_grading_policy(course_id)
    log.debug('Finished getting the course grading policy.')

    # Calculate the total weight of the non-exam categories
    log.debug(grading_policy)

    category_weight_ratios = {category['type'].lower(): category['weight'] for category in grading_policy}

    log.debug(category_weight_ratios)
    return category_weight_ratios


def _get_grades_by_format(course_id: CourseKey, users: list[User]) -> dict[int, dict[str, int]]:
    """
    Get the grades for each user, categorized by assignment types.

    :param course_id: The course ID.
    :param users: The users to get the grades for.
    :returns: A dictionary with the grades for each user, categorized by assignment types.
    """
    log.debug('Getting the grades for each user.')

    grades = {}

    with prefetch_course_grades(course_id, users):
        course_grade_factory = get_course_grade_factory()

        for user in users:
            grades[user.id] = {}
            course_grade = course_grade_factory.read(user, course_key=course_id)
            for assignment_type, subsections in course_grade.graded_subsections_by_format().items():
                assignment_earned = 0
                assignment_possible = 0
                log.debug(subsections)
                for subsection in subsections.values():
                    assignment_earned += subsection.graded_total.earned
                    assignment_possible += subsection.graded_total.possible
                grade = (assignment_earned / assignment_possible) * 100 if assignment_possible > 0 else 0
                grades[user.id][assignment_type.lower()] = grade

    log.debug('Finished getting the grades for each user.')
    return grades


def _are_grades_passing_criteria(
    user_grades: dict[str, float],
    required_grades: dict[str, float],
    category_weights: dict[str, float],
) -> bool:
    """
    Determine whether the user received passing grades in all required categories.

    :param user_grades: The grades of the user, divided by category.
    :param required_grades: The required grades for each category.
    :param category_weights: The weight of each category.
    :returns: Whether the user received passing grades in all required categories.
    :raises ValueError: If a category weight is not found.
    """
    # If user does not have a grade for a category (except for the "total" category), it means that they did not
    # attempt it. Therefore, they should not be eligible for the certificate.
    if not all(category in user_grades for category in required_grades if category != 'total'):
        return False

    total_score = 0
    for category, score in user_grades.items():
        if score < required_grades.get(category, 0):
            return False

        if category not in category_weights:
            msg = "Category weight '%s' was not found in the course grading policy."
            raise ValueError(msg, category)
        total_score += score * category_weights[category]

    return total_score >= required_grades.get('total', 0)


def retrieve_subsection_grades(course_id: CourseKey, options: dict[str, Any]) -> list[int]:
    """
    Retrieve the users that have passing grades in all required categories.

    :param course_id: The course ID.
    :param options: The custom options for the certificate.

    Options:
      - required_grades: A dictionary of required grades for each category, where the keys are the category names and
        the values are the minimum required grades. The grades are percentages, so they should be in the range [0, 1].
        See the following example::

          {
            "required_grades": {
              "Homework": 0.4,
              "Exam": 0.9,
              "Total": 0.8
            }
          }

        It means that the user must receive at least 40% in the Homework category and 90% in the Exam category.
        The "Total" key is a special value used to specify the minimum required grade for all categories in the course.
        Let's assume that we have the following grading policy (the percentages are the weights of each category):
        1. Homework: 20%
        2. Lab: 10%
        3. Exam: 70%
        The grades for the Total category will be calculated as follows:
        total_grade = (homework_grade * 0.2) + (lab_grade * 0.1) + (exam_grade * 0.7)
    """
    required_grades: dict[str, int] = options['required_grades']
    required_grades = {key.lower(): value * 100 for key, value in required_grades.items()}

    users = get_course_enrollments(course_id)
    grades = _get_grades_by_format(course_id, users)
    log.debug(grades)
    weights = _get_category_weights(course_id)

    eligible_users = []
    for user_id, user_grades in grades.items():
        if _are_grades_passing_criteria(user_grades, required_grades, weights):
            eligible_users.append(user_id)

    return eligible_users


def _prepare_request_to_completion_aggregator(course_id: CourseKey, query_params: dict, url: str) -> APIView:
    """
    Prepare a request to the Completion Aggregator API.

    :param course_id: The course ID.
    :param query_params: The query parameters to use in the request.
    :param url: The URL to use in the request.
    :returns: The view with the prepared request.
    """
    log.debug('Preparing the request for retrieving the completion.')

    # The URL does not matter, as we do not retrieve any data from the path.
    django_request = APIRequestFactory().get(url, query_params)
    django_request.course_id = course_id
    drf_request = Request(django_request)  # convert django.core.handlers.wsgi.WSGIRequest to DRF request

    view = CompletionDetailView()
    view.request = drf_request

    # HACK: Bypass the API permissions.
    staff_user = get_user_model().objects.filter(is_staff=True).first()
    view._effective_user = staff_user  # noqa: SLF001

    log.debug('Finished preparing the request for retrieving the completion.')
    return view


def retrieve_course_completions(course_id: CourseKey, options: dict[str, Any]) -> list[int]:
    """
    Retrieve the course completions for all users through the Completion Aggregator API.

    Options:
      - required_completion: The minimum required completion percentage. The default value is 0.9.
    """
    # If it turns out to be too slow, we can:
    # 1. Modify the Completion Aggregator to emit a signal/event when a user achieves a certain completion threshold.
    # 2. Get this data from the `Aggregator` model. Filter by `aggregation name == 'course'`, `course_key`, `percent`.

    required_completion = options.get('required_completion', 0.9)

    url = f'/completion-aggregator/v1/course/{course_id}/'
    query_params = {'page_size': 1000, 'page': 1}

    # TODO: Extract the logic of this view into an API. The current approach is very hacky.
    view = _prepare_request_to_completion_aggregator(course_id, query_params.copy(), url)
    completions = []

    while True:
        # noinspection PyUnresolvedReferences
        response = view.get(view.request, str(course_id))
        log.debug(response.data)
        completions.extend(
            res['username'] for res in response.data['results'] if res['completion']['percent'] >= required_completion
        )
        if not response.data['pagination']['next']:
            break
        query_params['page'] += 1
        view = _prepare_request_to_completion_aggregator(course_id, query_params.copy(), url)

    return list(get_user_model().objects.filter(username__in=completions).values_list('id', flat=True))