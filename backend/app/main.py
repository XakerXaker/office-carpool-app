import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import auth as auth_router
from .routers import offices as offices_router
from .routers import trips as trips_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Совместные поездки в офис",
    description="Бэкенд приложения для карпулинга сотрудников одной компании.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(offices_router.router)
app.include_router(trips_router.router)


@app.get("/api/config", tags=["meta"])
def client_config():
    return {
        "yandex_js_api_key": "YANDEX_API_KEY",
        "max_pickup_radius_km": "15",
        "require_same_city": "true",
        "require_same_company": "true",
    }


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
