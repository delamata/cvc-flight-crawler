from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from crawler.config import get_settings
from crawler.models import FlightOffer
from crawler.parser import parse_flight_offers


async def collect_offers(url: str | None = None) -> list[FlightOffer]:
    """Executa o navegador headless e coleta ofertas da URL informada.

    Usa `domcontentloaded` em vez de `networkidle` para evitar timeout em páginas
    que mantêm requisições abertas, comportamento comum em sites modernos.
    """

    settings = get_settings()
    target_url = url or settings.cvc_base_url
    browser = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=settings.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.set_default_timeout(settings.request_timeout_sec * 1000)

        try:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=settings.request_timeout_sec * 1000,
            )
            await page.wait_for_timeout(3000)
        except PlaywrightTimeoutError:
            logger.warning("Timeout ao carregar {}. Tentando processar HTML parcial.", target_url)

        html = await page.content()
        await browser.close()

    return parse_flight_offers(html, source_url=target_url)
