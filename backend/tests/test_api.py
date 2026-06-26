import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Company, Office, User
from app.auth import hash_password


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Перед каждым тестом создаём чистую БД с демо-данными, после — удаляем."""
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    try:
        company = Company(name="ООО «Ромашка»")
        db.add(company)
        db.flush()


        db.add(Office(name="Москва-Сити", address="Пресненская наб., 12",
                      city="Москва", lat=55.7494, lng=37.5398, company_id=company.id))
        db.add(User(full_name="Иван Водителев", email="driver@example.com",
                    password_hash=hash_password("password123"),
                    company_id=company.id, home_city="Москва",
                    home_lat=55.75, home_lng=37.61))
        db.add(User(full_name="Пётр Пассажиров", email="passenger.msk@example.com",
                    password_hash=hash_password("password123"),
                    company_id=company.id, home_city="Москва",
                    home_lat=55.76, home_lng=37.60))
        db.add(User(full_name="Семён Питерский", email="passenger.spb@example.com",
                    password_hash=hash_password("password123"),
                    company_id=company.id, home_city="Санкт-Петербург",
                    home_lat=59.93, home_lng=30.33))
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def login(email, password="password123"):
    """Войти и вернуть заголовок авторизации с токеном."""
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_moscow_trip(headers):
    """Создать поездку в московский офис со стартом в Москве."""
    office = client.get("/api/offices", headers=headers).json()[0]
    departure = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).isoformat()
    payload = {
        "office_id": office["id"],
        "origin_address": "ул. Тверская, 1",
        "origin_city": "Москва",
        "origin_lat": 55.7558,
        "origin_lng": 37.6173,
        "departure_time": departure,
        "total_seats": 3,
    }
    return client.post("/api/trips", json=payload, headers=headers)


def test_login_returns_token():
    """Вход с верными данными возвращает JWT-токен."""
    r = client.post("/api/auth/login",
                    data={"username": "driver@example.com", "password": "password123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password():
    """Неверный пароль — 401."""
    r = client.post("/api/auth/login",
                    data={"username": "driver@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token():
    """Эндпоинт /me без токена возвращает 401."""
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_register_new_user():
    """Регистрация нового пользователя возвращает 201 и токен."""
    company_id = client.get("/api/companies").json()[0]["id"]
    r = client.post("/api/auth/register", json={
        "full_name": "Новый Сотрудник",
        "email": "new@example.com",
        "password": "password123",
        "company_id": company_id,
        "home_city": "Москва",
    })
    assert r.status_code == 201
    assert "access_token" in r.json()


def test_create_trip():
    """Водитель создаёт поездку — 201 и корректные данные."""
    headers = login("driver@example.com")
    r = create_moscow_trip(headers)
    assert r.status_code == 201, r.text
    trip = r.json()
    assert trip["driver_name"] == "Иван Водителев"
    assert trip["origin_city"] == "Москва"
    assert trip["seats_left"] == 3
    assert trip["est_distance_km"] is not None


def test_passenger_same_city_can_join():
    """Пассажир из того же города присоединяется успешно."""
    driver_headers = login("driver@example.com")
    trip = create_moscow_trip(driver_headers).json()

    passenger_headers = login("passenger.msk@example.com")
    r = client.post(f"/api/trips/{trip['id']}/join", headers=passenger_headers, json={
        "pickup_address": "ул. Тверская, 10",
        "pickup_city": "Москва",
        "pickup_lat": 55.7600,
        "pickup_lng": 37.6050,
    })
    assert r.status_code == 200, r.text
    assert r.json()["seats_left"] == 2


def test_passenger_other_city_denied():
    """Пассажир из другого города получает отказ (422)."""
    driver_headers = login("driver@example.com")
    trip = create_moscow_trip(driver_headers).json()

    spb_headers = login("passenger.spb@example.com")
    r = client.post(f"/api/trips/{trip['id']}/join", headers=spb_headers, json={
        "pickup_address": "Невский пр., 28",
        "pickup_city": "Санкт-Петербург",
        "pickup_lat": 59.9343,
        "pickup_lng": 30.3351,
    })
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    violations = detail["violations"] if isinstance(detail, dict) else detail
    text = " ".join(violations)
    assert "город" in text or "далеко" in text


def test_check_preview_does_not_write():
    """Предпросмотр /check возвращает результат и ничего не записывает."""
    driver_headers = login("driver@example.com")
    trip = create_moscow_trip(driver_headers).json()

    spb_headers = login("passenger.spb@example.com")
    r = client.post(f"/api/trips/{trip['id']}/check", headers=spb_headers, json={
        "pickup_city": "Санкт-Петербург",
        "pickup_lat": 59.9343,
        "pickup_lng": 30.3351,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert len(body["violations"]) > 0

    again = client.get(f"/api/trips/{trip['id']}", headers=driver_headers).json()
    assert again["seats_left"] == 3