"""
Nesta Deal Hunter Szczecin - Główny punkt startowy aplikacji
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (v4.15, Sekcja 1.1).
FastAPI + GZip + Uvicorn + SQLite WAL + Modułowe Routery.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import init_db, engine
from app.core.scheduler import start_scheduler, stop_scheduler
from app.models.listing import Listing
from app.ingestion.pipeline import process_raw_listing

# Modularne Routery Domenowe (Sekcja 1.1)
from app.routers.feed import router as feed_router
from app.routers.scout import router as scout_router
from app.routers.benchmarks import router as benchmarks_router
from app.routers.sources import router as sources_router
from app.routers.tracker import router as tracker_router
from app.routers.system import router as system_router
from app.routers.manual import router as manual_router

def seed_sample_listings():
    """Wprowadza przykładowe oferty wyłącznie w środowisku deweloperskim (Sekcja 1.2)"""
    if not settings.is_dev_env:
        return

    with Session(engine) as session:
        count = len(session.exec(select(Listing)).all())
        if count == 0:
            sample_offers = [
                {
                    "source": "infoludek",
                    "title": "Śródmieście, ul. Śląska – 2 pokoje w kamienicy, piece kaflowe",
                    "district": "Śródmieście",
                    "street": "ul. Śląska",
                    "area_m2": 48.5,
                    "price_pln": 235000.0,
                    "rooms": 2,
                    "floor": 2,
                    "total_floors": 4,
                    "building_type": "Kamienica",
                    "has_elevator": False,
                    "has_balcony": True,
                    "balcony_type": "Balkon",
                    "heating_source": "piece kaflowe",
                    "admin_rent": 380.0,
                    "description": "Przedwojenna kamienica z zadbaną klatką schodową. Dwa rozkładowe pokoje, balkon od cichego podwórza. W lokalu zachowane piece kaflowe, gaz w klatce, możliwość natychmiastowej instalacji kotła 2-funkcyjnego. Spadek, pilna sprzedaż od właściciela.",
                    "url": "https://ogloszenia.infoludek.pl/ogloszenia/szczecin-slaska-48m"
                },
                {
                    "source": "olx",
                    "title": "Pogodno, ul. Mickiewicza – 54 m², wysoki parter, balkon",
                    "district": "Pogodno",
                    "street": "ul. Mickiewicza",
                    "area_m2": 54.0,
                    "price_pln": 320000.0,
                    "rooms": 3,
                    "floor": 1,
                    "total_floors": 3,
                    "building_type": "Kamienica",
                    "has_elevator": False,
                    "has_balcony": True,
                    "balcony_type": "Loggia",
                    "heating_source": "gazowe (kocioł 2-f)",
                    "admin_rent": 420.0,
                    "description": "Mieszkanie w willowej części Pogodna. 3 pokoje, loggia, ogrzewanie gazowe. Do remontu generalnego pod klienta premium. Bardzo pożądana lokalizacja.",
                    "url": "https://www.olx.pl/d/oferta/pogodno-mickiewicza-54m"
                }
            ]
            for offer in sample_offers:
                process_raw_listing(offer, session)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicjalizacja bazy SQLite i benchmarków
    init_db()
    seed_sample_listings()

    # Uruchomienie schedulera w tle (co 30 minut)
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# 1. Kompresja i wydajność (Sekcja 1.1)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. Bezpieczeństwo CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Montowanie assetów statycznych
static_path = Path(__file__).resolve().parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# 4. Rejestracja modularnych routerów domenowych (Sekcja 1.1)
app.include_router(system_router)
app.include_router(feed_router)
app.include_router(scout_router)
app.include_router(benchmarks_router)
app.include_router(sources_router)
app.include_router(tracker_router)
app.include_router(manual_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
