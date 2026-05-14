from sqlalchemy import desc, insert, select

from crawler.database import flight_offers, get_session_factory, init_db
from crawler.models import FlightOffer


async def save_offers(offers: list[FlightOffer]) -> int:
    """Salva ofertas coletadas no banco de dados."""

    if not offers:
        return 0

    await init_db()
    session_factory = get_session_factory()

    payload = [
        {
            "origin": offer.origin,
            "destination": offer.destination,
            "departure_date": offer.departure_date,
            "return_date": offer.return_date,
            "price": offer.price,
            "currency": offer.currency,
            "source_site": offer.source_site,
            "source_url": offer.source_url,
            "collected_at": offer.collected_at,
        }
        for offer in offers
    ]

    async with session_factory() as session:
        await session.execute(insert(flight_offers), payload)
        await session.commit()

    return len(payload)


async def get_latest_offers(limit: int = 50) -> list[FlightOffer]:
    """Busca as ofertas mais recentes gravadas no banco."""

    await init_db()
    session_factory = get_session_factory()

    query = (
        select(flight_offers)
        .order_by(desc(flight_offers.c.collected_at), desc(flight_offers.c.id))
        .limit(limit)
    )

    async with session_factory() as session:
        result = await session.execute(query)
        rows = result.mappings().all()

    return [
        FlightOffer(
            origin=row["origin"],
            destination=row["destination"],
            departure_date=row["departure_date"],
            return_date=row["return_date"],
            price=row["price"],
            currency=row["currency"],
            source_site=row["source_site"],
            source_url=row["source_url"],
            collected_at=row["collected_at"],
        )
        for row in rows
    ]
