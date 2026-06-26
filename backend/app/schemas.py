import datetime

from typing import Optional, List

from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    company_id: int
    home_city: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    company_id: int
    home_city: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class OfficeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str
    city: str
    lat: float
    lng: float
    company_id: int

class TripCreate(BaseModel):
    office_id: int
    origin_address: str = Field(min_length=2, max_length=255)
    origin_city: str = Field(min_length=2, max_length=80)
    origin_lat: float = Field(ge=-90, le=90)
    origin_lng: float = Field(ge=-180, le=180)
    departure_time: datetime.datetime
    total_seats: int = Field(ge=1, le=7, default=3)

class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: str
    pickup_address: Optional[str] = None
    pickup_lat: float
    pickup_lng: float

class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    driver_id: int
    driver_name: str
    office_id: int
    office_name: str
    origin_address: str
    origin_city: str
    origin_lat: float
    origin_lng: float
    departure_time: datetime.datetime
    total_seats: int
    seats_left: int
    status: str
    est_distance_km: Optional[float] = None
    est_duration_min: Optional[int] = None
    participants: List[ParticipantOut] = []

class TripJoinRequest(BaseModel):
    pickup_address: Optional[str] = None
    pickup_city: Optional[str] = None
    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lng: float = Field(ge=-180, le=180)

class JoinCheckOut(BaseModel):
    allowed: bool
    violations: List[str] = []
    distance_to_origin_km: Optional[float] = None








