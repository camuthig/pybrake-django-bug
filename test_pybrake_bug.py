import copy

from django.contrib.auth.models import AnonymousUser
from django.core.handlers.base import BaseHandler
from django.core.handlers.exception import convert_exception_to_response
from django.db import connection
from django.test import TestCase
from django.test import RequestFactory
from pybrake.django import AirbrakeMiddleware
from pybrake.global_notifier import get_global_notifier
from pybrake.notifier import Notifier
import pytest

@pytest.fixture(name='notifier', scope='function')
def patched_notifier():
    """
    Patch the global notifier with a clean state that doesn't actually do any notifying.

    Skipping the notification steps on the routes and errors is a quality-of-life improvement here because it means that
    valid project keys are not needed to test this functionality.

    The originally cached value is saved and put back into place after the test is finished.
    """
    original = get_global_notifier()

    get_global_notifier.cache_clear()

    notifier = get_global_notifier()
    def noop_notify(notice):
        return notice
    notifier._send_notice_sync = noop_notify
    notifier.routes.notify = noop_notify

    yield notifier

    notifier = original

def assert_notifies_exception(notifier: Notifier, e_info: 'ExceptionInfo'):
    """Validate that the notifier would not filter out the given exception."""
    notice = notifier.build_notice(e_info.value)
    notice, ok = notifier._filter_notice(notice)
    assert ok


@pytest.mark.django_db
def test_without_performance_monitoring(notifier, client):
    notifier.config['performance_stats'] = False

    with pytest.raises(Exception) as e_info:
        # It is important that this go through the standard middleware flow, rather than testing by directly passing
        # a fake request to the __call__ function of the middleware. Because of how Django handles the middleware
        # chain, the middleware classes do not usually appear in the traceback of exceptions.
        # This does not hold true for the extra calls to pybrake functions if the performance monitoring is enabled, though.
        client.get('/err/')

    assert_notifies_exception(notifier, e_info)


@pytest.mark.django_db
def test_with_performance_monitoring(notifier, client):
    notifier.config['performance_stats'] = True

    with pytest.raises(Exception) as e_info:
        client.get('/err/')

    assert_notifies_exception(notifier, e_info)