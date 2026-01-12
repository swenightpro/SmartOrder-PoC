from typing import Optional, List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="Messaggio dell'utente")
    client_id: int = Field(..., alias="client_id", description="ID cliente")


class ChatResponse(BaseModel):
    message: Optional[str] = Field(None, description="Messaggio di risposta")
    response: Optional[str] = Field(None, description="Messaggio di risposta (alias)")
    
    def dict(self, **kwargs):
        data = super().dict(**kwargs)
        if data.get("message"):
            data["response"] = data["message"]
        elif data.get("response"):
            data["message"] = data["response"]
        return data


class ProductSearchParams(BaseModel):
    keywords: List[str] = Field(default_factory=list, description="Parole chiave per ricerca")
    categoria: Optional[str] = Field(None, description="Categoria prodotto")
    tipo_um: Optional[str] = Field(None, description="Tipo unità di misura")
    min_price: Optional[float] = Field(None, description="Prezzo minimo")
    max_price: Optional[float] = Field(None, description="Prezzo massimo")
    limit: int = Field(20, description="Numero massimo risultati")


class Product(BaseModel):
    cod_art: str
    des_art: str
    des_um: Optional[str] = None
    pezzi_conf: Optional[float] = None
    des_tipo_um: Optional[str] = None
    stato: Optional[str] = None
    linea: Optional[str] = None
    settore: Optional[str] = None
    famiglia: Optional[str] = None
    sottofamiglia: Optional[str] = None


class OrderHistoryItem(BaseModel):
    cod_art: str
    des_art: Optional[str] = None
    data_ord: str
    qta_ordinata: float
    des_um: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row: dict):
        data = dict(row)
        if 'data_ord' in data and hasattr(data['data_ord'], 'isoformat'):
            data['data_ord'] = data['data_ord'].isoformat()
        elif 'data_ord' in data and data['data_ord'] is not None:
            data['data_ord'] = str(data['data_ord'])
        return cls(**data)


class SearchContext(BaseModel):
    products: List[Product] = Field(default_factory=list)
    order_history: List[OrderHistoryItem] = Field(default_factory=list)
    search_params: ProductSearchParams
