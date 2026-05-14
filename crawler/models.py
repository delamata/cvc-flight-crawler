from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FlightOffer(BaseModel):
    """Modelo canônico de uma oferta aérea coletada."""

    origin: str = Field(..., description="Código IATA de origem")
    destination: str = Field(..., description="Código IATA de destino")
    departure_date: str = Field(..., description="Data de ida no formato YYYY-MM-DD")
    return_date: Optional[str] = Field(default=None, description="Data de volta no formato YYYY-MM-DD")
    price: Optional[float] = Field(default=None, description="Preço encontrado")
    currency: str = Field(default="BRL")
    source_site: str = Field(default="cvc.com.br")
    source_url: Optional[str] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
