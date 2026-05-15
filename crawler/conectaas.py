from typing import Any

import httpx
from loguru import logger

from crawler.config import get_settings
from crawler.models import FlightOffer


def _walk_values(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_values(item)


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
    value = _nested_value(value, ("amount", "total", "value", "price"))
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _extract_offers_from_json(payload: Any) -> list[FlightOffer]:
    """Extrai ofertas de uma resposta JSON da ConectaAS.

    Suporta estruturas aninhadas como:
    `departure: {iata, date}` e `arrival: {iata, date}`.
    """

    offers: list[FlightOffer] = []

    origin_keys = ("origin", "originCode", "originIata", "departure", "departureCode", "from", "fromIata")
    destination_keys = ("destination", "destinationCode", "destinationIata", "arrival", "arrivalCode", "to", "toIata")
    departure_keys = ("departureDate", "date", "date1", "outboundDate", "departureTime", "departure")
    return_keys = ("returnDate", "date2", "inboundDate")
    price_keys = ("price", "amount", "total", "totalPrice", "fare", "value")
    currency_keys = ("currency", "currencyCode")

    for item in _walk_values(payload):
        origin_raw = _first_value(item, origin_keys)
        destination_raw = _first_value(item, destination_keys)
        departure_raw = _first_value(item, departure_keys) or origin_raw

        origin = _normalize_iata(origin_raw)
        destination = _normalize_iata(destination_raw)
        departure_date = _normalize_date(departure_raw)
        return_date = _normalize_date(_first_value(item, return_keys))
        price = _normalize_price(_first_value(item, price_keys))
        currency = str(_first_value(item, currency_keys) or "BRL").upper()[:3]

        if not origin or not destination or not departure_date:
            continue

        offers.append(
            FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                price=price,
                currency=currency,
                source_site="ConectaAS",
                source_url="ConectaAS airAvailability",
            )
        )

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

    return {
        "configured": True,
        "status_code": response.status_code,
        "final_url": str(response.url),
        "params_used": _build_params(),
        "top_level_type": top_level_type,
        "top_level_keys": top_level_keys,
        "parsed_offers": len(offers),
        "parsed_preview": [offer.model_dump(mode="json") for offer in offers[:10]],
        "payload_preview": payload if isinstance(payload, (dict, list)) else str(payload)[:1000],
    }
