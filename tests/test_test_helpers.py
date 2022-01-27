"""
Test test_helpers.
"""
# pylint: disable=redefined-outer-name
import pytest
from cloudshell.api.cloudshell_api import CloudShellAPISession

from shellfoundry_traffic.test_helpers import TestHelpers, create_session_from_config

RESERVATION_NAME = "testing 1 2 3"


@pytest.fixture()
def session() -> CloudShellAPISession:
    """Yields CloudShell session."""
    session = create_session_from_config()
    return session


@pytest.fixture()
def test_helper(session: CloudShellAPISession) -> TestHelpers:
    """Yields configured TestHelper object."""
    return TestHelpers(session)


def verify_reservation(test_helper: TestHelpers) -> None:
    """Verify that reservation was created successfully."""
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert [reservation for reservation in reservations.Reservations if reservation.Name == RESERVATION_NAME]
    test_helper.end_reservation()
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert not [reservation for reservation in reservations.Reservations if reservation.Name == RESERVATION_NAME]


def test_reservation(test_helper: TestHelpers) -> None:
    """Test create_reservation for empty topology."""
    test_helper.create_reservation(RESERVATION_NAME)
    verify_reservation(test_helper)


def test_topology_reservation(test_helper: TestHelpers) -> None:
    """Test create_reservation for named topology."""
    test_helper.create_topology_reservation("Test Topology", reservation_name=RESERVATION_NAME)
    verify_reservation(test_helper)
