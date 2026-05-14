import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from crawler.config import get_settings
from crawler.database import init_db
from crawler.repository import save_offers
from crawler.runner import collect_offers


async def run_once() -> None:
    """Executa uma coleta única e grava as ofertas no banco."""

    settings = get_settings()
    logger.info("Iniciando coleta em {}", settings.cvc_base_url)

    offers = await collect_offers(settings.cvc_base_url)
    saved = await save_offers(offers)

    logger.info(
        "Coleta concluída. Ofertas encontradas: {} | Ofertas gravadas: {}",
        len(offers),
        saved,
    )


async def main() -> None:
    settings = get_settings()
    await init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_once, "interval", minutes=settings.crawler_interval_min, id="cvc-flight-crawler")
    scheduler.start()

    logger.info("Scheduler iniciado. Intervalo: {} minutos", settings.crawler_interval_min)
    await run_once()

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
