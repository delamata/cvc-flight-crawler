from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crawler.models import FlightOffer

app = FastAPI(
    title="CVC Flight Price Crawler",
    version="0.1.0",
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/feed", response_model=list[FlightOffer])
async def feed() -> list[FlightOffer]:
    """Retorna o feed consolidado.

    Scaffold inicial: substituir por consulta ao banco de dados na próxima etapa.
    """

    return []


@app.get("/feed/latest", response_model=list[FlightOffer])
async def latest_feed() -> list[FlightOffer]:
    """Retorna as ofertas mais recentes.

    Scaffold inicial: substituir por consulta ao banco de dados na próxima etapa.
    """

    return []
