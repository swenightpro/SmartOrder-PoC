from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Singolo messaggio nella storia della conversazione (per contesto IA)."""
    role: str = Field(..., description="'user' o 'assistant'")
    content: str = Field(..., description="Testo del messaggio")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Messaggio dell'utente")
    client_id: int = Field(..., alias="client_id", description="ID cliente")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Ultimi messaggi della conversazione (max 10, per memoria IA)")


class ProductItem(BaseModel):
    """Un prodotto con quantità (un elemento della lista product_items)."""
    cod_art: str = Field(..., description="Codice articolo, deve essere presente in PRODOTTI DISPONIBILI ORA")
    quantity: float = Field(1, ge=0.001, description="Quantità (es. 2 per '2 acque', 1 se non specificata)")


class ChatResponse(BaseModel):
    message: Optional[str] = Field(None, description="Messaggio di risposta")
    response: Optional[str] = Field(None, description="Messaggio di risposta (alias)")
    product_codes: List[str] = Field(default_factory=list, description="Codici prodotti trovati (deprecato: usare product_items)")
    product_items: List[ProductItem] = Field(default_factory=list, description="Prodotti con quantità (cod_art + quantity)")
    order_confirmed: bool = Field(default=False, description="True se l'ordine è confermato e non richiede verifica aggiuntiva")
    
    def dict(self, **kwargs):
        data = super().dict(**kwargs)
        if data.get("message"):
            data["response"] = data["message"]
        elif data.get("response"):
            data["message"] = data["response"]
        # Mantieni product_codes in sync con product_items per retrocompatibilità
        if data.get("product_items") and not data.get("product_codes"):
            data["product_codes"] = [it["cod_art"] for it in data["product_items"]]
        return data


class ProductSearchParams(BaseModel):
    intent: Literal["SPECIFIC", "ADVICE", "REORDER", "CONFIRMATION"] = Field(
        default="SPECIFIC",
        description="SPECIFIC=cerca prodotto preciso, ADVICE=consiglio/categoria (es. aperitivo), REORDER=riordino, CONFIRMATION=conferma proposta"
    )
    keywords: List[str] = Field(default_factory=list, description="Parole chiave per ricerca")
    expanded_categories: List[str] = Field(
        default_factory=list,
        description="Termini espansi dall'LLM per intent ADVICE (es. aperitivo -> prosecco, spritz, patatine)"
    )
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


class BusinessDecisionResponse(BaseModel):
    message: str = Field(..., description="Messaggio di risposta all'utente")
    product_codes: List[str] = Field(default_factory=list, description="Lista di codici articolo (cod_art) dei prodotti trovati/ordinati (deprecato: usare product_items)")
    product_items: List[ProductItem] = Field(default_factory=list, description="Lista di prodotti da aggiungere: ogni elemento ha cod_art (da elenco disponibili) e quantity. Un elemento per prodotto (es. 2 acque e 1 bibita = 2 elementi in lista). Vuota se proposta senza aggiunta.")
    order_confirmed: bool = Field(default=False, description="True se l'ordine è confermato e non richiede verifica aggiuntiva, False se serve conferma dell'utente")
