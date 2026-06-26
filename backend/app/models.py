import datetime
import enum
from typing import List

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base


class TripStatus(str, enum.Enum):
    PLANNED   = "planned"
    DEPARTED  = "departed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ParticipantStatus(str, enum.Enum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    REJECTED  = "rejected"


class Company(Base):
    __tablename__ = "companies"

    id:   Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    users:   Mapped[List["User"]]   = relationship("User",   back_populates="company")
    offices: Mapped[List["Office"]] = relationship("Office", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id:            Mapped[int]   = mapped_column(primary_key=True)
    full_name:     Mapped[str]   = mapped_column(nullable=False)
    email:         Mapped[str]   = mapped_column(unique=True, nullable=False, index=True)
    password_hash: Mapped[str]   = mapped_column(nullable=False)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)

    home_city: Mapped[str | None]   = mapped_column(nullable=True)
    home_lat:  Mapped[float | None] = mapped_column(nullable=True)
    home_lng:  Mapped[float | None] = mapped_column(nullable=True)

    company          = relationship("Company", back_populates="users")
    trips_as_driver  = relationship("Trip",    back_populates="driver")
    participations   = relationship("TripParticipant", back_populates="user")


class Office(Base):
    __tablename__ = "offices"

    id:      Mapped[int]   = mapped_column(primary_key=True)
    name:    Mapped[str]   = mapped_column(nullable=False)
    address: Mapped[str]   = mapped_column(nullable=False)
    city:    Mapped[str]   = mapped_column(nullable=False, index=True)
    lat:     Mapped[float] = mapped_column(nullable=False)
    lng:     Mapped[float] = mapped_column(nullable=False)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    company = relationship("Company", back_populates="offices")
    trips   = relationship("Trip",    back_populates="office")


class Trip(Base):
    __tablename__ = "trips"

    id:        Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"),   nullable=False)
    office_id: Mapped[int] = mapped_column(ForeignKey("offices.id"), nullable=False)

    origin_address: Mapped[str]   = mapped_column(nullable=False)
    origin_city:    Mapped[str]   = mapped_column(nullable=False, index=True)
    origin_lat:     Mapped[float] = mapped_column(nullable=False)
    origin_lng:     Mapped[float] = mapped_column(nullable=False)

    departure_time: Mapped[datetime.datetime] = mapped_column(nullable=False)
    total_seats:    Mapped[int]               = mapped_column(nullable=False, default=3)
    status:         Mapped[TripStatus]        = mapped_column(nullable=False, default=TripStatus.PLANNED)

    est_distance_km:  Mapped[float | None] = mapped_column(nullable=True)
    est_duration_min: Mapped[int | None]   = mapped_column(nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)

    driver       = relationship("User",            back_populates="trips_as_driver")
    office       = relationship("Office",          back_populates="trips")
    participants = relationship("TripParticipant", back_populates="trip",
                                cascade="all, delete-orphan")

    @property
    def confirmed_count(self) -> int:
        return sum(
            1 for p in self.participants
            if p.status in (ParticipantStatus.REQUESTED, ParticipantStatus.CONFIRMED)
        )

    @property
    def seats_left(self) -> int:
        return max(0, self.total_seats - self.confirmed_count)


class TripParticipant(Base):
    __tablename__ = "trip_participants"
    __table_args__ = (
        UniqueConstraint("trip_id", "user_id", name="uq_trip_user"),
    )

    id:      Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    pickup_address: Mapped[str | None] = mapped_column(nullable=True)
    pickup_lat:     Mapped[float]      = mapped_column(nullable=False)
    pickup_lng:     Mapped[float]      = mapped_column(nullable=False)

    status:    Mapped[ParticipantStatus]  = mapped_column(nullable=False,
                                                          default=ParticipantStatus.REQUESTED)
    joined_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)

    trip = relationship("Trip", back_populates="participants")
    user = relationship("User", back_populates="participations")