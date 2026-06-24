from .database import Base, SessionLocal, engine
from .auth import hash_password
from .models import Company, Office, User


OFFICES = [
    ("Главный офис (Москва-Сити)", "Пресненская наб., 12, Москва", "Москва", 55.749792, 37.537136),
    ("Офис на Тульской", "ул. Большая Тульская, 11, Москва", "Москва", 55.711306, 37.622504),
    ("Офис на Невском", "Невский проспект, 28, Санкт-Петербург", "Санкт-Петербург", 59.935554, 30.325650),
    ("Офис в Казани (Кремль)", "ул. Кремлёвская, 1, Казань", "Казань", 55.798551, 49.106324),
]

USERS = [
    ("Иван Водителев", "driver.msk@example.com", "password123", "Москва", 55.751244, 37.618423),
    ("Пётр Пассажиров", "passenger.msk@example.com", "password123", "Москва", 55.760000, 37.600000),
    ("Анна Дальняя", "passenger.spb@example.com", "password123", "Санкт-Петербург", 59.934280, 30.335099),
    ("Мария Казанская", "passenger.kzn@example.com", "password123", "Казань", 55.796127, 49.108795),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Company).first():
            print("База уже заполнена — пропускаю.")
            return

        company = Company(name="ООО «Ромашка»")
        db.add(company)
        db.flush()

        for name, address, city, lat, lng in OFFICES:
            db.add(Office(
                name=name, address=address, city=city, lat=lat, lng=lng,
                company_id=company.id,
            ))

        for full_name, email, password, city, lat, lng in USERS:
            db.add(User(
                full_name=full_name, email=email,
                password_hash=hash_password(password),
                company_id=company.id,
                home_city=city, home_lat=lat, home_lng=lng,
            ))

        db.commit()
        print("Готово. Создана компания, офисы и демо-пользователи.")
        print("Демо-логины (пароль у всех password123):")
        for _, email, *_ in USERS:
            print("  -", email)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
