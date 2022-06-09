"""Fixtures and testing utilities for :pypi:`pytest <pytest>`."""
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Mapping, Sequence, Union

import pytest

if TYPE_CHECKING:
    from celery import Celery

    from pytest_celery.contrib.testing.worker import WorkController
else:
    Celery = WorkController = object


NO_WORKER = os.environ.get("NO_WORKER")

# pylint: disable=redefined-outer-name
# Well, they're called fixtures....


def pytest_configure(config):
    """Register additional pytest configuration."""
    # add the pytest.mark.celery() marker registration to the pytest.ini [markers] section
    # this prevents pytest 4.5 and newer from issuing a warning about an unknown marker
    # and shows helpful marker documentation when running pytest --markers.
    config.addinivalue_line("markers", "celery(**overrides): override celery configuration for a test case")


@contextmanager
def _create_app(enable_logging=False, use_trap=False, parameters=None, **config):
    # type: (Any, Any, Any, **Any) -> Celery
    """Utility context used to setup Celery app for pytest fixtures."""

    from pytest_celery.contrib.testing.app import TestApp, setup_default_app

    parameters = {} if not parameters else parameters
    test_app = TestApp(set_as_current=False, enable_logging=enable_logging, config=config, **parameters)
    with setup_default_app(test_app, use_trap=use_trap):
        yield test_app


@pytest.fixture
def use_celery_app_trap():
    # type: () -> bool
    """You can override this fixture to enable the app trap.

    The app trap raises an exception whenever something attempts
    to use the current or default apps.
    """
    return False


@pytest.fixture
def celery_includes():
    # type: () -> Sequence[str]
    """You can override this include modules when a worker start.

    You can have this return a list of module names to import,
    these can be task modules, modules registering signals, and so on.
    """
    return ()


@pytest.fixture
def celery_worker_pool():
    # type: () -> Union[str, Any]
    """You can override this fixture to set the worker pool.

    The "solo" pool is used by default, but you can set this to
    return e.g. "prefork".
    """
    return "solo"


@pytest.fixture
def celery_parameters():
    # type: () -> Mapping[str, Any]
    """Redefine this fixture to change the init parameters of test Celery app.

    The dict returned by your fixture will then be used
    as parameters when instantiating :class:`~celery.Celery`.
    """
    return {}


@pytest.fixture
def celery_worker_parameters():
    # type: () -> Mapping[str, Any]
    """Redefine this fixture to change the init parameters of Celery workers.

    This can be used e. g. to define queues the worker will consume tasks from.

    The dict returned by your fixture will then be used
    as parameters when instantiating :class:`~celery.worker.WorkController`.
    """
    return {}


@pytest.fixture()
def celery_app(request, celery_config, celery_parameters, celery_enable_logging, use_celery_app_trap):
    """Fixture creating a Celery application instance."""
    mark = request.node.get_closest_marker("celery")
    config = dict(celery_config, **mark.kwargs if mark else {})
    with _create_app(
        enable_logging=celery_enable_logging, use_trap=use_celery_app_trap, parameters=celery_parameters, **config
    ) as app:
        yield app


@pytest.fixture()
def celery_worker(request, celery_app, celery_includes, celery_worker_pool, celery_worker_parameters):
    # type: (Any, Celery, Sequence[str], str, Any) -> WorkController
    """Fixture: Start worker in a thread, stop it when the test returns."""
    from pytest_celery.contrib.testing import worker

    if not NO_WORKER:
        for module in celery_includes:
            celery_app.loader.import_task_module(module)
        with worker.start_worker(celery_app, pool=celery_worker_pool, **celery_worker_parameters) as w:
            yield w


@pytest.fixture()
def depends_on_current_app(celery_app):
    """Fixture that sets app as current."""
    celery_app.set_current()
