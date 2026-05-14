from bs4 import BeautifulSoup
from crawler.models import FlightOffer


def parse_flight_offers(html: str, source_url: str | None = None) -> list[FlightOffer]:
    """Extrai ofertas aéreas de um HTML.

    Este parser é intencionalmente conservador no scaffold inicial.
    Os seletores reais devem ser ajustados em `docs/ajuste-seletores.md`
    após validação do HTML retornado pelo site.
    """

    soup = BeautifulSoup(html, "html.parser")
    offers: list[FlightOffer] = []

    for card in soup.select("[data-testid='flight-card'], .flight-card, .offer-card"):
        origin = _safe_text(card, "[data-origin], .origin")
        destination = _safe_text(card, "[data-destination], .destination")
        price_text = _safe_text(card, "[data-price], .price")

        if not origin or not destination:
            continue

        offers.append(
            FlightOffer(
                origin=origin[:3].upper(),
                destination=destination[:3].upper(),
                departure_date="1900-01-01",
                price=_parse_price(price_text),
                source_url=source_url,
            )
        )

    return offers


def _safe_text(node, selector: str) -> str:
    element = node.select_one(selector)
    return element.get_text(strip=True) if element else ""


def _parse_price(value: str) -> float | None:
    if not value:
        return None

    normalized = (
        value.replace("R$", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(normalized)
    except ValueError:
        return None
