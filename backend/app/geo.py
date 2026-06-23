import datetime as dt
import math
from dataclasses import dataclass, field
from typing import List

from .models import Trip, TripStatus, User


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
    now = now or dt.datetime.now
    violations: List[str] = []

    if trip.status != TripStatus.PLANNED:
        violations.append("Поездка недоступна для присоединения (статус не «запланирована»).")

    cutoff = trip.departure_time - dt.timedelta(minutes=10)
    if now >= cutoff:
        violations.append(
            "Присоединение закрыто: до отправления менее "
            "10 минут."
        )

    if trip.seats_left <= 0:
        violations.append("Нет свободных мест в машине.")

    if trip.driver_id == user.id:
        violations.append("Нельзя присоединиться к собственной поездке.")

    if already_joined:
        violations.append("Вы уже записаны в эту поездку.")

    if user.company_id != trip.office.company_id:
        violations.append("Поездка доступна только сотрудникам той же компании.")

    if pickup_city:
        if pickup_city.strip().lower() != trip.origin_city.strip().lower():
            violations.append(
                f"Город посадки «{pickup_city}» не совпадает с городом поездки "
                f"«{trip.origin_city}»."
            )

    distance = haversine_km(pickup_lat, pickup_lng, trip.origin_lat, trip.origin_lng)
    if distance > 15:
        violations.append(
            f"Точка посадки слишком далеко от старта поездки: "
            f"{distance:.1f} км при допустимых {15:.0f} км."
        )

    return ConstraintResult(
        allowed=len(violations) == 0,
        violations=violations,
        distance_to_origin_km=round(distance, 2),
    )
