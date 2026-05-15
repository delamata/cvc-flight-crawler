import httpx
from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from crawler.conectaas import collect_conectaas_offers
from crawler.config import get_settings
from crawler.models import FlightOffer
from crawler.parser import parse_flight_offers

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def collect_offers(url: str | None = None) -> list[FlightOffer]:
    """Coleta ofertas.

    Prioridade:
    1. ConectaAS, quando configurado via CONECTAAS_URL + CONECTAAS_TOKEN.
    2. HTML da LP da CVC como fallback legado.
    """

    settings = get_settings()

    if settings.conectaas_url and settings.conectaas_token:
        conectaas_offers = await collect_conectaas_offers()
        if conectaas_offers:
            return conectaas_offers
        logger.warning("ConectaAS configurada, mas não retornou ofertas parseáveis. Usando fallback HTML.")

    target_url = url or settings.cvc_base_url

    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_sec,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        ) as client:
            response = await client.get(target_url)
            response.raise_for_status()
            html = response.text
            offers = parse_flight_offers(html, source_url=str(response.url))

            if offers:
                logger.info("Ofertas encontradas via HTTP simples: {}", len(offers))
                return offers

            logger.warning("HTTP simples não encontrou ofertas. Usando Playwright como fallback.")
    except Exception as exc:
        logger.warning("Falha no HTTP simples: {}. Usando Playwright como fallback.", exc)

    html, final_url = await _fetch_with_playwright(target_url)
    return parse_flight_offers(html, source_url=final_url)


async def _fetch_with_playwright(target_url: str) -> tuple[str, str]:
    settings = get_settings()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=settings.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        page = await browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
        page.set_default_timeout(settings.request_timeout_sec * 1000)

        try:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=settings.request_timeout_sec * 1000,
            )
            await page.wait_for_timeout(5000)
        except PlaywrightTimeoutError:
            logger.warning("Timeout ao carregar {}. Tentando processar HTML parcial.", target_url)

        html = await page.content()
        final_url = page.url
        await browser.close()

    return html, final_url
