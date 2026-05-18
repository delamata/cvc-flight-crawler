from typing import Any
import re

import httpx
from loguru import logger

from crawler.config import get_settings
from crawler.models import FlightOffer

PRICE_KEY_HINTS = (
    "price",
    "amount",
    "total",
    "fare",
    "tariff",
    "tarifa",
    "valor",
    "withtax",
    "withouttax",
)

PRICE_CONTAINER_KEY_HINTS = (
    "price",
    "prices",
    "pricing",
    "fare",
    "fares",
    "payment",
    "payments",
    "commercial",
    "commercials",
    "tariff",
    "tarifa",
    "valor",
    "metadata",
)

PRICE_KEY_EXCLUDES = (
    "duration",
    "flightnumber",
    "seatsleft",
    "numberofstops",
    "aircraft",
    "code",
    "class",
    "basis",
)

CURRENCY_KEYS = ("currency", "currencyCode", "currency_code", "moeda")
PREFERRED_PRICE_KEYS = (
    "minWithTax",
    "min_with_tax",
    "minimumWithTax",
    "minAmountWithTax",
    "minWithoutTax",
    "min_without_tax",
    "minimumWithoutTax",
    "minAmountWithoutTax",
    "totalWithTax",
    "totalAmountWithTax",
    "totalPrice",
    "totalAmount",
    "amount",
    "value",
    "price",
)


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in data.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _clean_token(value: str) -> str:
    token = value.strip()
    if token.lower().startswith("bearer "):
        return token.split(" ", 1)[1].strip()
    return token


def _nested_value(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return _first_value(value, keys)
    return value


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace("R$", "").strip()
    text = text.replace(".", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def _normalize_date(value: Any) -> str | None:
    value = _nested_value(value, ("date", "datetime", "time", "departureDate", "arrivalDate"))
    if not value:
        return None

    text = str(value)[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text

    if len(text) == 10 and text[2] == "/" and text[5] == "/":
        day, month, year = text.split("/")
        return f"{year}-{month}-{day}"

    return None


def _normalize_iata(value: Any) -> str | None:
    value = _nested_value(value, ("iata", "code", "airportCode"))
    if not value:
        return None

    text = str(value).strip().upper()
    if len(text) >= 3:
        return text[:3]

    return None


def _normalize_price(value: Any) -> float | None:
    if isinstance(value, dict):
        for key in PREFERRED_PRICE_KEYS:
            direct = _first_value(value, (key,))
            price = _normalize_price(direct)
            if price is not None and price > 0:
                return price
        return None

    if isinstance(value, str):
        for key in PREFERRED_PRICE_KEYS:
            pattern = rf"{re.escape(key)}\s*=\s*([0-9]+(?:[\.,][0-9]+)?)"
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                price = _parse_number(match.group(1))
                if price is not None and price > 0:
                    return price

    return _parse_number(value)


def _find_price_anywhere(obj: Any) -> float | None:
    """Busca preço dentro de um subobjeto explicitamente relacionado a preço."""

    if isinstance(obj, dict):
        direct_price = _normalize_price(obj)
        if direct_price is not None and direct_price > 0:
            return direct_price

        for key, value in obj.items():
            key_normalized = str(key).lower().replace("_", "")
            if any(excluded in key_normalized for excluded in PRICE_KEY_EXCLUDES):
                continue

            if any(hint in key_normalized for hint in PRICE_KEY_HINTS):
                price = _normalize_price(value)
                if price is not None and price > 0:
                    return price

            price = _find_price_anywhere(value)
            if price is not None:
                return price

    elif isinstance(obj, list):
        for item in obj:
            price = _find_price_anywhere(item)
            if price is not None:
                return price

    return None


def _find_price_local(item: dict[str, Any]) -> float | None:
    """Busca preço no objeto atual ou em campos filhos explicitamente de preço."""

    candidates: list[tuple[int, float]] = []

    # Caso específico ConectaAS: metadata.price contém minWithTax/minWithoutTax.
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        metadata_price = _normalize_price(metadata.get("price"))
        if metadata_price is not None and metadata_price > 0:
            candidates.append((10, metadata_price))

    for key, value in item.items():
        key_normalized = str(key).lower().replace("_", "")
        if any(excluded in key_normalized for excluded in PRICE_KEY_EXCLUDES):
            continue

        if any(hint in key_normalized for hint in PRICE_KEY_HINTS):
            price = _normalize_price(value)
            if price is not None and price > 0:
                score = 1
                if "minwithtax" in key_normalized:
                    score += 8
                if "min" in key_normalized:
                    score += 5
                if "total" in key_normalized:
                    score += 3
                if "price" in key_normalized or "amount" in key_normalized:
                    score += 2
                candidates.append((score, price))

        if any(hint in key_normalized for hint in PRICE_CONTAINER_KEY_HINTS):
            price = _find_price_anywhere(value)
            if price is not None and price > 0:
                score = 2
                if "metadata" in key_normalized:
                    score += 6
                if "price" in key_normalized or "fare" in key_normalized:
                    score += 2
                candidates.append((score, price))

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    return candidates[0][1]


def _find_currency_local(item: dict[str, Any]) -> str | None:
    direct = _first_value(item, CURRENCY_KEYS)
    if direct:
        return str(direct).upper()[:3]

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        price_value = metadata.get("price")
        if isinstance(price_value, dict):
            currency = _first_value(price_value, CURRENCY_KEYS)
            if currency:
                return str(currency).upper()[:3]
        if isinstance(price_value, str):
            match = re.search(r"currency\s*=\s*([A-Za-z]{3})", price_value, re.IGNORECASE)
            if match:
                return match.group(1).upper()

    for key, value in item.items():
        key_normalized = str(key).lower().replace("_", "")
        if any(hint in key_normalized for hint in PRICE_CONTAINER_KEY_HINTS) and isinstance(value, dict):
            nested = _first_value(value, CURRENCY_KEYS)
            if nested:
                return str(nested).upper()[:3]

    return None


def _segment_to_offer(item: dict[str, Any], price: float | None, currency: str) -> FlightOffer | None:
    origin_raw = _first_value(item, ("origin", "originCode", "originIata", "departure", "departureCode", "from", "fromIata"))
    destination_raw = _first_value(item, ("destination", "destinationCode", "destinationIata", "arrival", "arrivalCode", "to", "toIata"))
    departure_raw = _first_value(item, ("departureDate", "date", "date1", "outboundDate", "departureTime", "departure")) or origin_raw

    origin = _normalize_iata(origin_raw)
    destination = _normalize_iata(destination_raw)
    departure_date = _normalize_date(departure_raw)

    if not origin or not destination or not departure_date:
        return None

    return FlightOffer(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=None,
        price=price,
        currency=currency,
        source_site="ConectaAS",
        source_url="ConectaAS airAvailability",
    )


def _extract_offers_from_json(payload: Any) -> list[FlightOffer]:
    """Extrai ofertas propagando preço do objeto pai para os segmentos filhos."""

    offers: list[FlightOffer] = []

    def visit(obj: Any, inherited_price: float | None = None, inherited_currency: str = "BRL") -> None:
        if isinstance(obj, dict):
            local_price = _find_price_local(obj)
            local_currency = _find_currency_local(obj)

            current_price = local_price if local_price is not None else inherited_price
            current_currency = local_currency or inherited_currency or "BRL"

            offer = _segment_to_offer(obj, current_price, current_currency)
            if offer:
                offers.append(offer)
                return

            for value in obj.values():
                visit(value, current_price, current_currency)

        elif isinstance(obj, list):
            for item in obj:
                visit(item, inherited_price, inherited_currency)

    visit(payload)
    return _dedupe_offers(offers)


def _dedupe_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
    seen: set[tuple[str, str, str, str | None, float | None]] = set()
    unique: list[FlightOffer] = []

    for offer in offers:
        key = (offer.origin, offer.destination, offer.departure_date, offer.return_date, offer.price)
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)

    return unique


def _build_params() -> dict[str, Any]:
    settings = get_settings()
    return {
        "pax": [settings.conectaas_pax, settings.conectaas_pax],
        "maxResults": _safe_int(settings.conectaas_max_results, 100),
        "maxNumberOfStops": _safe_int(settings.conectaas_max_number_of_stops, 1),
        "routes": settings.conectaas_routes,
        "businessClass": settings.conectaas_business_class or "ALSO",
    }


def _build_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {_clean_token(settings.conectaas_token)}",
    }


async def collect_conectaas_offers() -> list[FlightOffer]:
    settings = get_settings()

    if not settings.conectaas_url:
        logger.warning("CONECTAAS_URL não configurada.")
        return []

    if not settings.conectaas_token:
        logger.warning("CONECTAAS_TOKEN não configurado.")
        return []

    async with httpx.AsyncClient(timeout=settings.request_timeout_sec, follow_redirects=True) as client:
        response = await client.get(settings.conectaas_url, params=_build_params(), headers=_build_headers())
        response.raise_for_status()
        payload = response.json()

    offers = _extract_offers_from_json(payload)
    logger.info("Ofertas extraídas da ConectaAS: {}", len(offers))
    return offers


async def debug_conectaas() -> dict[str, Any]:
    settings = get_settings()

    if not settings.conectaas_url:
        return {"configured": False, "message": "CONECTAAS_URL não configurada"}

    if not settings.conectaas_token:
        return {"configured": False, "message": "CONECTAAS_TOKEN não configurado"}

    async with httpx.AsyncClient(timeout=settings.request_timeout_sec, follow_redirects=True) as client:
        response = await client.get(settings.conectaas_url, params=_build_params(), headers=_build_headers())

    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text_preview": response.text[:1000]}

    offers = _extract_offers_from_json(payload)

    if isinstance(payload, dict):
        top_level_type = "object"
        top_level_keys = list(payload.keys())[:50]
    elif isinstance(payload, list):
        top_level_type = "array"
        top_level_keys = []
    else:
        top_level_type = type(payload).__name__
        top_level_keys = []

    priced_offers = [offer for offer in offers if offer.price is not None]

    return {
        "configured": True,
        "status_code": response.status_code,
        "final_url": str(response.url),
        "params_used": _build_params(),
        "top_level_type": top_level_type,
        "top_level_keys": top_level_keys,
        "parsed_offers": len(offers),
        "priced_offers": len(priced_offers),
        "parsed_preview": [offer.model_dump(mode="json") for offer in offers[:10]],
        "payload_preview": payload if isinstance(payload, (dict, list)) else str(payload)[:1000],
    }
