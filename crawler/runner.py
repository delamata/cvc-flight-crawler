from playwright.async_api import async_playwright
from crawler.config import get_settings
from crawler.models import FlightOffer
from crawler.parser import parse_flight_offers


async def collect_offers(url: str | None = None) -> list[FlightOffer]:
    """Executa o navegador headless e coleta ofertas da URL informada."""

    settings = get_settings()
    target_url = url or settings.cvc_base_url

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.headless)
        page = await browser.new_page()
        await page.goto(target_url, wait_until="networkidle", timeout=settings.request_timeout_sec * 1000)
        html = await page.content()
        await browser.close()

    return parse_flight_offers(html, source_url=target_url)
