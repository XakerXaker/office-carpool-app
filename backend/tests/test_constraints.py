import datetime as dt
import sys
import types

from app.geo import haversine_km, evaluate_join_constraints
from app.models import TripStatus, ParticipantStatus


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


def approx(a, b, eps=1.0):
    return abs(a - b) <= eps


def run():
    passed = 0
    failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [OK]  {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    print("haversine_km")
    # Москва (Красная площадь) -> Санкт-Петербург (центр) ~ 633 км
    d = haversine_km(55.7539, 37.6208, 59.9311, 30.3609)
    check("Москва–СПБ ~633 км", approx(d, 633, 15))
    # Та же точка -> 0 км
    check("одна точка = 0", approx(haversine_km(55.75, 37.62, 55.75, 37.62), 0, 0.01))

    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
    moscow_origin = (55.751244, 37.618423)

    print("Допуск: близкая точка, та же компания, тот же город")
    user = FakeUser(2, company_id=1)
    trip = FakeTrip(driver_id=1, office_company_id=1, origin=moscow_origin, departure=future)
    res = evaluate_join_constraints(
        user=user, trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    check("разрешено присоединиться", res.allowed)
    check("нет нарушений", len(res.violations) == 0)

    print("Отказ: пассажир в другом городе за сотни км")
    res = evaluate_join_constraints(
        user=user, trip=trip,
        pickup_lat=59.9311, pickup_lng=30.3609, pickup_city="Санкт-Петербург",
    )
    check("не разрешено", not res.allowed)
    check("есть нарушение по расстоянию",
          any("слишком далеко" in v for v in res.violations))
    check("есть нарушение по городу",
          any("не совпадает с городом" in v for v in res.violations))

    print("Отказ: чужая компания")
    other = FakeUser(3, company_id=999)
    res = evaluate_join_constraints(
        user=other, trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    check("отказ по компании", any("компании" in v for v in res.violations))

    print("Отказ: нет мест")
    full = FakeTrip(driver_id=1, office_company_id=1, origin=moscow_origin,
                    departure=future, total_seats=2, taken=2)
    res = evaluate_join_constraints(
        user=user, trip=full,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    check("отказ по местам", any("мест" in v for v in res.violations))

    print("Отказ: своя поездка")
    res = evaluate_join_constraints(
        user=FakeUser(1, 1), trip=trip,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    check("отказ по собственной поездке",
          any("собственной" in v for v in res.violations))

    print("Отказ: поздно присоединяться")
    soon = FakeTrip(driver_id=1, office_company_id=1, origin=moscow_origin,
                    departure=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2))
    res = evaluate_join_constraints(
        user=user, trip=soon,
        pickup_lat=55.76, pickup_lng=37.60, pickup_city="Москва",
    )
    check("отказ по дедлайну", any("отправления" in v for v in res.violations))

    print(f"\nИтого: {passed} пройдено, {failed} провалено")
    return failed == 0


if __name__ == "__main__":
    ok = run()
