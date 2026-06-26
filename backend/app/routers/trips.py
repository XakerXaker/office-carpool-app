import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..geo import evaluate_join_constraints
from ..models import (
    Office, ParticipantStatus, Trip, TripParticipant, TripStatus, User
)
from ..schemas import (
    JoinCheckOut, ParticipantOut, TripCreate, TripJoinRequest, TripOut
)
from ..yandex import estimate_route

router = APIRouter(prefix="/api/trips", tags=["trips"])


def to_trip_out(trip: Trip) -> TripOut:
    return TripOut(
        id=trip.id,
        driver_id=trip.driver_id,
        driver_name=trip.driver.full_name,
        office_id=trip.office_id,
        office_name=trip.office.name,
        origin_address=trip.origin_address,
        origin_city=trip.origin_city,
        origin_lat=trip.origin_lat,
        origin_lng=trip.origin_lng,
        departure_time=trip.departure_time,
        total_seats=trip.total_seats,
        seats_left=trip.seats_left,
        status=trip.status.value,
        est_distance_km=trip.est_distance_km,
        est_duration_min=trip.est_duration_min,
        participants=[ParticipantOut.model_validate(p) for p in trip.participants],
    )


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    office = db.get(Office, payload.office_id)
    if not office:
        raise HTTPException(status_code=404, detail="Офис не найден")

    if office.company_id != current.company_id:
        raise HTTPException(status_code=403, detail="Офис принадлежит другой компании")
    departure = payload.departure_time
    if departure.tzinfo is not None:
        departure = departure.astimezone(dt.timezone.utc).replace(tzinfo=None)
    if departure <= dt.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Время отправления должно быть в будущем")

    dist_km, dur_min, _src = estimate_route(
        payload.origin_lat, payload.origin_lng, office.lat, office.lng
    )

    trip = Trip(
        driver_id=current.id,
        office_id=office.id,
        origin_address=payload.origin_address,
        origin_city=payload.origin_city,
        origin_lat=payload.origin_lat,
        origin_lng=payload.origin_lng,
        departure_time=departure,
        total_seats=payload.total_seats,
        est_distance_km=dist_km,
        est_duration_min=dur_min,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return to_trip_out(trip)


@router.get("", response_model=List[TripOut])
def list_trips(
    office_id: Optional[int] = Query(None),
    city: Optional[str] = Query(None),
    only_open: bool = Query(True, description="Только запланированные со свободными местами"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = db.query(Trip).join(Office, Trip.office_id == Office.id)
    if office_id:
        q = q.filter(Trip.office_id == office_id)
    if city:
        q = q.filter(Trip.origin_city == city)
    q = q.filter(Office.company_id == current.company_id)
    if only_open:
        q = q.filter(Trip.status == TripStatus.PLANNED)
    trips = q.order_by(Trip.departure_time).all()
    result = [to_trip_out(t) for t in trips]
    if only_open:
        result = [t for t in result if t.seats_left > 0]
    return result


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    return to_trip_out(trip)


def _already_joined(db: Session, trip_id: int, user_id: int) -> bool:
    existing = (
        db.query(TripParticipant)
        .filter(
            TripParticipant.trip_id == trip_id,
            TripParticipant.user_id == user_id,
            TripParticipant.status != ParticipantStatus.REJECTED,
        )
        .first()
    )
    return existing is not None


@router.post("/{trip_id}/check", response_model=JoinCheckOut)
def check_join(
    trip_id: int,
    payload: TripJoinRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")

    res = evaluate_join_constraints(
        user=current,
        trip=trip,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        pickup_city=payload.pickup_city,
        already_joined=_already_joined(db, trip_id, current.id),
    )
    return JoinCheckOut(
        allowed=res.allowed,
        violations=res.violations,
        distance_to_origin_km=res.distance_to_origin_km,
    )


@router.post("/{trip_id}/join", response_model=TripOut)
def join_trip(
    trip_id: int,
    payload: TripJoinRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")

    res = evaluate_join_constraints(
        user=current,
        trip=trip,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        pickup_city=payload.pickup_city,
        already_joined=_already_joined(db, trip_id, current.id),
    )
    if not res.allowed:
        raise HTTPException(status_code=422, detail={"violations": res.violations})

    participant = TripParticipant(
        trip_id=trip.id,
        user_id=current.id,
        pickup_address=payload.pickup_address,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        status=ParticipantStatus.REQUESTED,
    )
    db.add(participant)
    db.commit()
    db.refresh(trip)
    return to_trip_out(trip)


@router.delete("/{trip_id}/leave", response_model=TripOut)
def leave_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    p = (
        db.query(TripParticipant)
        .filter(TripParticipant.trip_id == trip_id, TripParticipant.user_id == current.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Вы не участвуете в этой поездке")
    db.delete(p)
    db.commit()
    db.refresh(trip)
    return to_trip_out(trip)


@router.post("/{trip_id}/participants/{participant_id}/decision", response_model=TripOut)
def decide_participant(
    trip_id: int,
    participant_id: int,
    decision: str = Query(..., pattern="^(confirm|reject)$"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if trip.driver_id != current.id:
        raise HTTPException(status_code=403, detail="Только водитель управляет заявками")
    p = db.get(TripParticipant, participant_id)
    if not p or p.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if decision == "confirm":
        if trip.seats_left <= 0 and p.status != ParticipantStatus.CONFIRMED:
            raise HTTPException(status_code=422, detail="Нет свободных мест")
        p.status = ParticipantStatus.CONFIRMED
    else:
        p.status = ParticipantStatus.REJECTED
    db.commit()
    db.refresh(trip)
    return to_trip_out(trip)


@router.post("/{trip_id}/cancel", response_model=TripOut)
def cancel_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if trip.driver_id != current.id:
        raise HTTPException(status_code=403, detail="Только водитель может отменить поездку")
    trip.status = TripStatus.CANCELLED
    db.commit()
    db.refresh(trip)
    return to_trip_out(trip)