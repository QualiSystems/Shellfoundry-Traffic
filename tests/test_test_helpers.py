
import pytest

from shellfoundry_traffic.test_helpers import create_session_from_config, TestHelpers


@pytest.fixture()
def session():
    session = create_session_from_config()
    yield session
    # todo: delete session.


def test_session(session) -> None:
    test_helper = TestHelpers(session)
    reservation = test_helper.create_reservation(reservation_name='testing 1 2 3')
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert [r for r in reservations.Reservations if r.Name == 'testing 1 2 3']
    test_helper.end_reservation(reservation.Reservation.Id)
    reservations = test_helper.session.GetCurrentReservations(reservationOwner=test_helper.session.username)
    assert not [r for r in reservations.Reservations if r.Name == 'testing 1 2 3']
