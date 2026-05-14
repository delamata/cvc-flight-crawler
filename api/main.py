from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crawler.database import init_db
from crawler.models import FlightOffer
from crawler.repository import get_latest_offers

app = FastAPI(
    title="CVC Flight Price Crawler",
    version="0.2.0",
    description="API para consulta de ofertas aéreas coletadas pelo crawler.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://delamata.github.io",
        "https://delamata.github.io/cvc-flight-crawler",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/feed", response_model=list[FlightOffer])
async def feed() -> list[FlightOffer]:
    """Retorna o feed consolidado a partir do banco de dados."""

    return await get_latest_offers(limit=500)


@app.get("/feed/latest", response_model=list[FlightOffer])
async def latest_feed() -> list[FlightOffer]:
    """Retorna as ofertas mais recentes gravadas no banco de dados."""

    return await get_latest_offers(limit=50)
