import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from crawler.config import get_settings
from crawler.runner import collect_offers


async def run_once() -> None:
    """Executa uma coleta única."""

    settings = get_settings()
    logger.info("Iniciando coleta em {}", settings.cvc_base_url)
    offers = await collect_offers(settings.cvc_base_url)
    logger.info("Coleta concluída. Ofertas encontradas: {}", len(offers))


async def main() -> None:
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_once, "interval", minutes=settings.crawler_interval_min, id="cvc-flight-crawler")
    scheduler.start()

    logger.info("Scheduler iniciado. Intervalo: {} minutos", settings.crawler_interval_min)
    await run_once()

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
