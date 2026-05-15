import httpx
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from crawler.config import get_settings
from crawler.database import init_db
from crawler.models import FlightOffer
from crawler.parser import parse_flight_offers
from crawler.repository import get_latest_offers, save_offers
from crawler.runner import collect_offers

APP_VERSION = "0.3.4"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

app = FastAPI(
    title="CVC Flight Price Crawler",
    version=APP_VERSION,
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


def verify_admin_key(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
) -> None:
    """Protege endpoints administrativos com API_SECRET_KEY."""

    settings = get_settings()
    expected_key = settings.api_secret_key
    provided_key = x_api_key or api_key

    if not expected_key or expected_key == "troque_esta_chave_em_producao":
        raise HTTPException(
            status_code=500,
            detail="API_SECRET_KEY não configurada no ambiente de produção.",
        )

    if provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Chave administrativa inválida.")


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "crawler_url": settings.cvc_base_url,
    }


@app.post("/admin/collect", dependencies=[Depends(verify_admin_key)])
async def collect_now() -> dict[str, int | str]:
    """Dispara uma coleta manual e grava o resultado no banco."""

    try:
        offers = await collect_offers()
        saved = await save_offers(offers)
    except Exception as exc:
        logger.exception("Erro ao executar coleta manual")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Erro ao executar coleta manual.",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        ) from exc

    return {
        "status": "ok",
        "collected": len(offers),
        "saved": saved,
    }


@app.get("/admin/debug-http", dependencies=[Depends(verify_admin_key)])
async def debug_http() -> dict[str, object]:
    """Diagnóstico protegido para validar o HTML recebido no Render."""

    settings = get_settings()

    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_sec,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        ) as client:
            response = await client.get(settings.cvc_base_url)
            html = response.text
    except Exception as exc:
        logger.exception("Erro no debug HTTP")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Erro ao baixar página via HTTP.",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        ) from exc

    soup = BeautifulSoup(html, "html.parser")
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    candidates = [
        line
        for line in lines
        if "Aéreo" in line or "Aereo" in line or "Pacote" in line or "Saída" in line or "Saida" in line or "R$" in line
    ][:100]
    parsed = parse_flight_offers(html, source_url=str(response.url))

    return {
        "status_code": response.status_code,
        "final_url": str(response.url),
        "html_length": len(html),
        "text_lines": len(lines),
        "candidate_lines": len(candidates),
        "parsed_offers": len(parsed),
        "sample_candidates": candidates[:30],
    }


@app.get("/feed", response_model=list[FlightOffer])
async def feed() -> list[FlightOffer]:
    """Retorna o feed consolidado a partir do banco de dados."""

    return await get_latest_offers(limit=500)


@app.get("/feed/latest", response_model=list[FlightOffer])
async def latest_feed() -> list[FlightOffer]:
    """Retorna as ofertas mais recentes gravadas no banco de dados."""

    return await get_latest_offers(limit=50)
