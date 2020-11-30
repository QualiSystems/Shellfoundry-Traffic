
import pytest

from shellfoundry_traffic.test_helpers import create_session_from_config, TestHelpers

RESERVATION_NAME = 'testing 1 2 3'


@pytest.fixture()
def session():
    session = create_session_from_config()
    yield session
    # todo: delete session.


def test_reservation(session) -> None:
    test_helper = TestHelpers(session)
    test_helper.create_reservation(RESERVATION_NAME)
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert [r for r in reservations.Reservations if r.Name == RESERVATION_NAME]
    test_helper.end_reservation()
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert not [r for r in reservations.Reservations if r.Name == RESERVATION_NAME]


def test_topology_reservation(session) -> None:
    test_helper = TestHelpers(session)
    test_helper.create_topology_reservation('Test Topology', reservation_name=RESERVATION_NAME)
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert [r for r in reservations.Reservations if r.Name == RESERVATION_NAME]
    test_helper.end_reservation()
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert not [r for r in reservations.Reservations if r.Name == RESERVATION_NAME]
