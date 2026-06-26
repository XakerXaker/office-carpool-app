"""
Модульные тесты движка ограничений (geo.evaluate_join_constraints).

Это самый ответственный модуль приложения: он решает, может ли пассажир
присоединиться к поездке. Тесты написаны на pytest.

Запуск из папки backend:
    python -m pytest tests/test_constraints.py -v
"""
import datetime as dt

import pytest

from app.geo import haversine_km, evaluate_join_constraints
from app.models import TripStatus


class FakeOffice:
    def __init__(self, company_id):
        self.company_id = company_id


class FakeUser:
    def __init__(self, uid, company_id):
        self.id = uid
        self.company_id = company_id


class FakeTrip:
    def __init__(self, driver_id, office_company_id, origin, departure,
                 total_seats=3, taken=0, status=TripStatus.PLANNED):
        self.driver_id = driver_id
        self.office = FakeOffice(office_company_id)
        self.origin_lat, self.origin_lng = origin
        self.origin_city = "Москва"
        self.departure_time = departure
        self.total_seats = total_seats
        self._taken = taken
        self.status = status

    @property
    def seats_left(self):
        return self.total_seats - self._taken


MOSCOW_ORIGIN = (55.751244, 37.618423)

def future_time(hours=2):
    """Время отправления в будущем (timezone-aware UTC)."""
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)


def test_haversine_moscow_spb():
    """Расстояние Москва — Санкт-Петербург ≈ 633 км."""
    d = haversine_km(55.7539, 37.6208, 59.9311, 30.3609)
    assert abs(d - 633) <= 15


def test_haversine_same_point_zero():
    """Расстояние между одной и той же точкой равно нулю."""
    assert haversine_km(55.75, 37.62, 55.75, 37.62) == pytest.approx(0, abs=0.01)

def test_deny_other_city_far_away():
    """Главный кейс: пассажир из другого города за сотни км — отказ по R7 и R8."""
    user = FakeUser(2, company_id=1)
    trip = FakeTrip(driver_id=1, office_company_id=1,
                    origin=MOSCOW_ORIGIN, departure=future_time())
    res = evaluate_join_constraints(
        user=user, trip=trip,
        pickup_lat=59.9311, pickup_lng=30.3609, pickup_city="Санкт-Петербург",
    )
    assert res.allowed is False
    assert any("слишком далеко" in v for v in res.violations)
    assert any("не совпадает с городом" in v for v in res.violations)


def test_deny_other_company():
    """Пассажир из другой компании — отказ по R6."""
    other = FakeUser(3, company_id=999)
    trip = FakeTrip(driver_id=1, office_company_id=1,
                    origin=MOSCOW_ORIGIN, departure=future_time())
    res = evaluate_join_constraints(
        user=other, trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    assert res.allowed is False
    assert any("компании" in v for v in res.violations)


def test_deny_no_seats():
    """Нет свободных мест — отказ по R3."""
    user = FakeUser(2, company_id=1)
    full = FakeTrip(driver_id=1, office_company_id=1, origin=MOSCOW_ORIGIN,
                    departure=future_time(), total_seats=2, taken=2)
    res = evaluate_join_constraints(
        user=user, trip=full,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    assert res.allowed is False
    assert any("мест" in v for v in res.violations)


def test_deny_own_trip():
    """Водитель не может присоединиться к своей поездке — отказ по R4."""
    trip = FakeTrip(driver_id=1, office_company_id=1,
                    origin=MOSCOW_ORIGIN, departure=future_time())
    res = evaluate_join_constraints(
        user=FakeUser(1, 1), trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    assert res.allowed is False
    assert any("собственной" in v for v in res.violations)


def test_deny_already_joined():
    """Повторная запись в ту же поездку — отказ по R5."""
    user = FakeUser(2, company_id=1)
    trip = FakeTrip(driver_id=1, office_company_id=1,
                    origin=MOSCOW_ORIGIN, departure=future_time())
    res = evaluate_join_constraints(
        user=user, trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
        already_joined=True,
    )
    assert res.allowed is False
    assert any("уже записаны" in v for v in res.violations)


def test_deny_past_cutoff():
    """До отправления меньше порога — отказ по R2."""
    user = FakeUser(2, company_id=1)
    soon = FakeTrip(driver_id=1, office_company_id=1, origin=MOSCOW_ORIGIN,
                    departure=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2))
    res = evaluate_join_constraints(
        user=user, trip=soon,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    assert res.allowed is False
    assert any("отправления" in v for v in res.violations)


def test_deny_cancelled_trip():
    """Поездка не в статусе «запланирована» — отказ по R1."""
    user = FakeUser(2, company_id=1)
    trip = FakeTrip(driver_id=1, office_company_id=1, origin=MOSCOW_ORIGIN,
                    departure=future_time(), status=TripStatus.CANCELLED)
    res = evaluate_join_constraints(
        user=user, trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    assert res.allowed is False
    assert any("статус" in v for v in res.violations)