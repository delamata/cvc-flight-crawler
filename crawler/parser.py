import re
import unicodedata
from urllib.parse import parse_qs, urljoin, urlparse

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

OFFER_TITLE_PATTERN = re.compile(
    r"(?:^|\b)(aereo|pacote)\s+(.+?)\s+saindo\s+de\s+([^\|\n\r]+)",
    re.IGNORECASE,
)

FULL_TEXT_PATTERN = re.compile(
    r"(?:aereo|pacote)\s+(.+?)\s+saindo\s+de\s+(.+?)\s+"
    r"(?:aereo|hospedagem|saida|check|desconto|a partir|r\$|voando|ate|\d+\s+dias)",
    re.IGNORECASE,
)

ROUTE_STOP_PATTERN = re.compile(
    r"\s{2,}|\s+saida\b|\s+check\b|\s+a partir\b|\s+r\$|"
    r"\s+aereo\b|\s+hospedagem\b|\s+voando\b|\s+ate\b|"
    r"\s+desconto\b|\s+\d+\s+dias\b|\s+em ate\b|\s+total\b",
    re.IGNORECASE,
)


def parse_flight_offers(html: str, source_url: str | None = None) -> list[FlightOffer]:
    """Extrai ofertas da LP de promoções da CVC."""

    soup = BeautifulSoup(html, "html.parser")

    offers = _parse_cvc_segmented_offer_cards(soup, source_url=source_url)
    if offers:
        return offers

    offers = _parse_promotions_page(soup, source_url=source_url)
    if offers:
        return offers

    return _parse_generic_cards(soup, source_url=source_url)


def _parse_cvc_segmented_offer_cards(
    soup: BeautifulSoup,
    source_url: str | None = None,
) -> list[FlightOffer]:
    """Extrai cards da estrutura real da LP: bloco-oferta-segmentado-2-botoes."""

    offers: list[FlightOffer] = []

    for card in soup.select(".bloco-oferta-segmentado-2-botoes-card-infos"):
        destination_city = _safe_text(card, ".bloco-oferta-segmentado-2-botoes-card-produto strong")
        origin_text = _safe_text(card, ".bloco-oferta-segmentado-2-botoes-card-categoria")
        origin_city = _extract_origin_from_category(origin_text)

        card_text = card.get_text(" ", strip=True)
        price_text = _safe_text(card, ".bloco-oferta-segmentado-2-botoes-card-comerciais") or card_text
        price = _extract_price(price_text)
        departure_date = _extract_departure_date(card_text)

        primary_link = card.select_one("a.botao-card-compre-no-site[href], a[href*='/passagens/'][href]")
        offer_url = urljoin(source_url or "https://www.cvc.com.br", primary_link.get("href")) if primary_link else source_url

        href_origin, href_destination, href_departure, href_return = _extract_route_from_offer_url(offer_url)

        origin = href_origin or _city_to_iata(origin_city or "sao paulo")
        destination = href_destination or _city_to_iata(destination_city)
        departure_date = href_departure or departure_date

        if not origin or not destination or not departure_date:
            continue

        offers.append(
            FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=href_return,
                price=price,
                currency="BRL",
                source_site="cvc.com.br/lp/promocoes",
                source_url=offer_url,
            )
        )

    return _dedupe_offers(offers)


def _extract_origin_from_category(value: str) -> str | None:
    normalized = _normalize(value)
    if "saindo de " in normalized:
        return normalized.split("saindo de ", 1)[1].strip()
    return normalized or None


def _extract_route_from_offer_url(offer_url: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    if not offer_url:
        return None, None, None, None

    parsed = urlparse(offer_url)
    match = re.search(r"/search/([A-Z]{3})/([A-Z]{3})", parsed.path, re.IGNORECASE)
    origin = match.group(1).upper() if match else None
    destination = match.group(2).upper() if match else None

    query = parse_qs(parsed.query)
    departure = _normalize_iso_date(query.get("Date1", [None])[0])
    return_date = _normalize_iso_date(query.get("Date2", [None])[0])

    return origin, destination, departure, return_date


def _normalize_iso_date(value: str | None) -> str | None:
    if not value:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        day, month, year = value.split("/")
        return f"{year}-{month}-{day}"

    return None


def _parse_promotions_page(soup: BeautifulSoup, source_url: str | None = None) -> list[FlightOffer]:
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    offers: list[FlightOffer] = []

    for idx, line in enumerate(lines):
        title = _clean_text(line)
        route_match = _extract_route(title)

        if not route_match:
            continue

        origin_city, destination_city = route_match
        window = " ".join(lines[idx : idx + 16])
        offer = _build_offer(origin_city, destination_city, window, source_url)

        if offer:
            offers.append(offer)

    if offers:
        return _dedupe_offers(offers)

    return _parse_full_text(" ".join(lines), source_url=source_url)


def _parse_full_text(text: str, source_url: str | None = None) -> list[FlightOffer]:
    normalized_text = _normalize(text)
    offers: list[FlightOffer] = []

    for match in FULL_TEXT_PATTERN.finditer(normalized_text):
        destination_city = _clean_route_piece(match.group(1))
        origin_city = _clean_route_piece(match.group(2))
        window = normalized_text[match.start() : match.end() + 600]
        offer = _build_offer(origin_city, destination_city, window, source_url)

        if offer:
            offers.append(offer)

    return _dedupe_offers(offers)


def _build_offer(
    origin_city: str | None,
    destination_city: str | None,
    window: str,
    source_url: str | None,
) -> FlightOffer | None:
    if not destination_city:
        return None

    departure_date = _extract_departure_date(window)
    price = _extract_price(window)
    origin = _city_to_iata(origin_city or "sao paulo")
    destination = _city_to_iata(destination_city)

    if not origin or not destination or not departure_date:
        return None

    return FlightOffer(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=None,
        price=price,
        currency="BRL",
        source_site="cvc.com.br/lp/promocoes",
        source_url=source_url,
    )


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


def _extract_route(title: str) -> tuple[str | None, str | None] | None:
    normalized = _normalize(title)
    match = OFFER_TITLE_PATTERN.search(normalized)

    if not match:
        return None

    destination = _clean_route_piece(match.group(2))
    origin = _clean_route_piece(match.group(3))

    return origin, destination


def _clean_route_piece(value: str) -> str:
    value = ROUTE_STOP_PATTERN.split(value, maxsplit=1)[0]
    return _clean_text(value)


def _extract_departure_date(text: str) -> str | None:
    normalized = _normalize(text)
    match = re.search(r"(?:saida|check[- ]?in):?\s*(\d{2}/\d{2}/\d{4})", normalized)
    if not match:
        return None

    day, month, year = match.group(1).split("/")
    return f"{year}-{month}-{day}"


def _extract_price(text: str) -> float | None:
    normalized = _normalize(text)
    match = re.search(r"r\$\s*([0-9\.]+(?:,[0-9]{2})?)", normalized)
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
        .replace("r$", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(normalized)
    except ValueError:
        return None
