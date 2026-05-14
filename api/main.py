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

DEMO_OFFERS = [
    FlightOffer(
        origin="SAO",
        destination="RIO",
        departure_date="2026-06-15",
        return_date="2026-06-20",
        price=489.90,
        currency="BRL",
        source_site="Demonstração",
        source_url="https://www.cvc.com.br",
    ),
    FlightOffer(
        origin="SAO",
        destination="SSA",
        departure_date="2026-07-10",
        return_date="2026-07-17",
        price=899.90,
        currency="BRL",
        source_site="Demonstração",
        source_url="https://www.cvc.com.br",
    ),
    FlightOffer(
        origin="BSB",
        destination="REC",
        departure_date="2026-08-05",
        return_date="2026-08-12",
        price=749.90,
        currency="BRL",
        source_site="Demonstração",
        source_url="https://www.cvc.com.br",
    ),
]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/feed", response_model=list[FlightOffer])
async def feed() -> list[FlightOffer]:
    """Retorna o feed consolidado.

    MVP inicial: retorna dados de demonstração para validar integração front + API.
    Na próxima etapa, este endpoint deve consultar o banco de dados.
    """

    return DEMO_OFFERS


@app.get("/feed/latest", response_model=list[FlightOffer])
async def latest_feed() -> list[FlightOffer]:
    """Retorna as ofertas mais recentes.

    MVP inicial: retorna dados de demonstração para validar integração front + API.
    Na próxima etapa, este endpoint deve consultar o banco de dados.
    """

    return DEMO_OFFERS
