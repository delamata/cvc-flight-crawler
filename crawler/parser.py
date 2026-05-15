import re
import unicodedata

from bs4 import BeautifulSoup

from crawler.models import FlightOffer

CITY_TO_IATA = {
    "bariloche": "BRC",
    "lisboa": "LIS",
    "santiago": "SCL",
    "madri": "MAD",
    "lima": "LIM",
    "orlando": "MCO",
    "cartagena": "CTG",
    "buenos aires": "EZE",
    "rio de janeiro": "RIO",
    "porto alegre": "POA",
    "porto seguro": "BPS",
    "fortaleza": "FOR",
    "recife": "REC",
    "maceio": "MCZ",
    "natal": "NAT",
    "sao paulo": "SAO",
    "salvador": "SSA",
    "florianopolis": "FLN",
    "curitiba": "CWB",
    "gramado": "CXJ",
    "porto de galinhas": "REC",
}


def parse_flight_offers(html: str, source_url: str | None = None) -> list[FlightOffer]:
    """Extrai ofertas da LP de promoções da CVC.

    A página `lp/promocoes` não expõe cards com classes simples como `.flight-card`.
    Por isso, o parser usa o texto renderizado e identifica blocos com padrões como:
    - "Aéreo Bariloche Saindo de São Paulo"
    - "Pacote Rio de Janeiro Saindo de São Paulo"
    - "Saída: 16/06/2026"
    - "a partir de R$ 1.539"
    """

    soup = BeautifulSoup(html, "html.parser")
    offers = _parse_promotions_page(soup, source_url=source_url)

    if offers:
        return offers

    return _parse_generic_cards(soup, source_url=source_url)


def _parse_promotions_page(soup: BeautifulSoup, source_url: str | None = None) -> list[FlightOffer]:
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    offers: list[FlightOffer] = []

    for idx, line in enumerate(lines):
        title = _clean_text(line)

        if not _is_offer_title(title):
            continue

        window = " ".join(lines[idx : idx + 12])
        origin_city, destination_city = _extract_route(title)
        departure_date = _extract_departure_date(window)
        price = _extract_price(window)

        if not destination_city or not departure_date:
            continue

        origin = _city_to_iata(origin_city or "sao paulo")
        destination = _city_to_iata(destination_city)

        if not origin or not destination:
            continue

        offers.append(
            FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=None,
                price=price,
                currency="BRL",
                source_site="cvc.com.br/lp/promocoes",
                source_url=source_url,
            )
        )

    return _dedupe_offers(offers)


def _parse_generic_cards(soup: BeautifulSoup, source_url: str | None = None) -> list[FlightOffer]:
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


def _is_offer_title(title: str) -> bool:
    lowered = _normalize(title)
    return (
        (lowered.startswith("aereo ") or lowered.startswith("pacote "))
        and " saindo de " in lowered
    )


def _extract_route(title: str) -> tuple[str | None, str | None]:
    normalized = _normalize(title)
    normalized = re.sub(r"^(aereo|pacote)\s+", "", normalized).strip()

    if " saindo de " not in normalized:
        return None, None

    destination, origin = normalized.split(" saindo de ", 1)
    return origin.strip(), destination.strip()


def _extract_departure_date(text: str) -> str | None:
    match = re.search(r"(?:Saída|Saida|Check-in|Check in):?\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if not match:
        return None

    day, month, year = match.group(1).split("/")
    return f"{year}-{month}-{day}"


def _extract_price(text: str) -> float | None:
    match = re.search(r"R\$\s*([0-9\.]+(?:,[0-9]{2})?)", text)
    if not match:
        return None

    return _parse_price(match.group(1))


def _city_to_iata(city: str) -> str | None:
    normalized = _normalize(city)
    return CITY_TO_IATA.get(normalized)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value.lower()).strip()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _dedupe_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
    seen: set[tuple[str, str, str, float | None]] = set()
    unique: list[FlightOffer] = []

    for offer in offers:
        key = (offer.origin, offer.destination, offer.departure_date, offer.price)
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)

    return unique


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
