from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


connect_args = {"check_same_thread": False}

engine = create_engine("sqlite:///./carpool.db", connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
