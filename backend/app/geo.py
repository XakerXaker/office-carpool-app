import datetime as dt
import math
from dataclasses import dataclass, field
from typing import List

from .models import Trip, TripStatus, User, ParticipantStatus


EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass
class ConstraintResult:
    """Результат проверки ограничений."""
    allowed: bool
    violations: List[str] = field(default_factory=list)
    distance_to_origin_km: float | None = None


def evaluate_join_constraints(
    *,
    user: User,
    trip: Trip,
    pickup_lat: float,
    pickup_lng: float,
    pickup_city: str | None,
    now: dt.datetime | None = None,
    already_joined: bool = False,
) -> ConstraintResult:
    """
    Проверить, может ли пользователь присоединиться к поездке.

    Набор правил:
      R1. Поездка должна быть в статусе PLANNED.
      R2. До отправления должно оставаться не меньше 10.
      R3. В машине должны быть свободные места.
      R4. Пользователь не может присоединиться к собственной поездке.
      R5. Пользователь не должен быть уже записан в эту поездку.
      R6. (опц.) Пассажир и водитель — из одной компании.
      R7. (опц.) Город посадки совпадает с городом старта поездки.
      R8. Точка посадки в пределах 1 км от точки старта.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    violations: List[str] = []

    # R1
    if trip.status != TripStatus.PLANNED:
        violations.append("Поездка недоступна для присоединения (статус не «запланирована»).")

    # R2
    departure = trip.departure_time
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    cutoff = departure - dt.timedelta(minutes=10)
    if now >= cutoff:
        violations.append(
            f"Присоединение закрыто: до отправления менее "
            f"10 минут."
        )

    # R3
    if trip.seats_left <= 0:
        violations.append("Нет свободных мест в машине.")

    # R4
    if trip.driver_id == user.id:
        violations.append("Нельзя присоединиться к собственной поездке.")

    # R5
    if already_joined:
        violations.append("Вы уже записаны в эту поездку.")


    if user.company_id != trip.office.company_id:
            violations.append("Поездка доступна только сотрудникам той же компании.")

    # R7 — один город
    if pickup_city:
        a = pickup_city.strip().lower()
        b = trip.origin_city.strip().lower()
        same_city = a == b or (a and b and (a in b or b in a))
        if not same_city:
            violations.append(
                f"Город посадки «{pickup_city}» не совпадает с городом поездки "
                f"«{trip.origin_city}»."
            )

    # R8 — радиус посадки
    distance = haversine_km(pickup_lat, pickup_lng, trip.origin_lat, trip.origin_lng)
    if distance > 1:
        violations.append(
            f"Точка посадки слишком далеко от старта поездки: "
            f"{distance:.1f} км при допустимых {1:.0f} км."
        )

    return ConstraintResult(
        allowed=len(violations) == 0,
        violations=violations,
        distance_to_origin_km=round(distance, 2),
    )