from typing import Optional, List
import logging
import openai
from openai import OpenAI

from config import settings
from models.schemas import (
    ProductSearchParams,
    Product,
    OrderHistoryItem,
    SearchContext,
    BusinessDecisionResponse
)

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model_fast = "gpt-4o-mini"
        self.model_smart = "gpt-4o"
    
    def extract_search_params(self, user_message: str) -> ProductSearchParams:
        try:
            logger.info(f"Estrazione parametri: '{user_message}'")
            
            response = self.client.beta.chat.completions.parse(
                model=self.model_fast,
                messages=[
                    {
                        "role": "system",
                        "content": """Extract product search parameters from Italian user messages.

Extract: product names, brands, types, varieties, descriptive terms that identify products.

Exclude grammatical words:
- Articles: il, lo, la, gli, le, un, una, uno
- Prepositions: di, da, in, con, per, su, tra, fra, a, al, alla, del, della, dei, delle, dello
- Common verbs: vorrei, voglio, cerco, mi serve, ho, bisogno
- Pronouns: mi, ti, si

Exclude generic adjectives: buono/buona, bello/bella, nuovo/nuova, vecchio/vecchia, grande, piccolo, ottimo, migliore.

Special cases:
- Correct spelling errors and normalize variations
- Generic keywords (broad categories) → set limit to at least 50

Always extract meaningful product terms, even if generic. Never return empty keywords if message contains product-related words."""
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                response_format=ProductSearchParams
            )
            
            message = response.choices[0].message
            if message.parsed:
                params = message.parsed
                
                if not params.keywords or len(params.keywords) == 0:
                    logger.warning(f"Keywords vuote dal messaggio: '{user_message}'")
                
                logger.info(f"Parametri estratti: keywords={params.keywords}, categoria={params.categoria}, limit={params.limit}")
                return params
            else:
                logger.error(f"Modello ha rifiutato: {message.refusal}")
                raise ValueError(f"Modello ha rifiutato la richiesta: {message.refusal}")
        
        except openai.RateLimitError as e:
            logger.error(f"Credito OpenAI esaurito o limite raggiunto: {e}")
            return ProductSearchParams(keywords=[], categoria=None, limit=10)
        except Exception as e:
            logger.error(f"Errore estrazione parametri: {e}", exc_info=True)
            raise
    
    def make_business_decision(
        self,
        user_message: str,
        search_context: SearchContext
    ) -> BusinessDecisionResponse:
        try:
            logger.info(f"Generazione risposta - prodotti: {len(search_context.products)}, storico: {len(search_context.order_history)}")
            
            products_text = ""
            num_products = len(search_context.products)
            if search_context.products:
                if num_products > 10:
                    products_text = f"[Trovati {num_products} prodotti totali, mostro i primi 10 come esempio]\n"
                    products_text += "\n".join([
                        f"- {p.cod_art}: {p.des_art} ({p.des_um or 'N/A'}, {p.famiglia or 'N/A'})"
                        for p in search_context.products[:10]
                    ])
                    products_text += f"\n[Nota: ci sono altri {num_products - 10} prodotti simili disponibili]"
                else:
                    products_text = "\n".join([
                        f"- {p.cod_art}: {p.des_art} ({p.des_um or 'N/A'}, {p.famiglia or 'N/A'})"
                        for p in search_context.products
                    ])
            else:
                products_text = "Nessun prodotto trovato."
            
            history_text = ""
            if search_context.order_history:
                history_text = "\n".join([
                    f"- {h.cod_art}: {h.des_art or 'N/A'} (ordinato il {h.data_ord}, qty: {h.qta_ordinata})"
                    for h in search_context.order_history[:5]
                ])
            else:
                history_text = "Nessun ordine storico."
            
            system_prompt = """You are an expert salesperson helping customers order products. Be professional, friendly, and direct.

DECISION RULES:
1. Exactly 1 product found: Add immediately without asking. Set order_confirmed=TRUE, include cod_art in product_codes. Response: "Perfetto! Ho aggiunto [product name] al tuo ordine."

2. 2-10 products: List ALL with numbers (1. [name], 2. [name], ...) and ask "Quale preferisci?". Set order_confirmed=FALSE.

3. >10 products: Ask specific questions to narrow down (brand, variety, format, etc.). Don't list all. Set order_confirmed=FALSE.

4. 0 products: Ask for clarification. Set order_confirmed=FALSE.

5. Uncertainty (20-30%): Proceed with most likely option based on history, best-sellers, or first result. Don't ask for confirmation unless total ambiguity.

ORDER_CONFIRMED FLAG:
- TRUE: Adding directly (1 product found), proceeding without user confirmation
- FALSE: Asking user to choose, listing options, or need clarification

PRODUCT_CODES:
- Include cod_art when adding/confirming products
- Empty [] when asking for choice or clarification

Always respond in ITALIAN, naturally and concisely."""

            user_prompt = f"""User message: "{user_message}"

NUMBER OF PRODUCTS FOUND: {num_products}

PRODUCTS FOUND:
{products_text}

ORDER HISTORY:
{history_text}

DECISION:
- If products = 1: Add directly, order_confirmed=TRUE, include cod_art
- If products = 0: Ask for clarification
- If products > 1: List all (2-10) or ask questions (>10)

Make decision based on rules above."""

            response = self.client.beta.chat.completions.parse(
                model=self.model_smart,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=BusinessDecisionResponse,
                temperature=0.7,
                max_tokens=500
            )
            
            message = response.choices[0].message
            if message.parsed:
                result = message.parsed
                logger.info(f"Risposta generata: message='{result.message}', product_codes={result.product_codes}")
                return result
            else:
                logger.error(f"Modello ha rifiutato: {message.refusal}")
                return BusinessDecisionResponse(
                    message="Mi dispiace, ho riscontrato un errore. Riprova tra un momento.",
                    product_codes=[]
                )

        except openai.RateLimitError as e:
            logger.error(f"Credito OpenAI esaurito: {e}")
            return BusinessDecisionResponse(
                message="Spiacente, il servizio di Intelligenza Artificiale non è al momento disponibile (credito esaurito). Contatta l'amministratore.",
                product_codes=[],
                order_confirmed=False
            )    

        except Exception as e:
            logger.error(f"Errore generazione risposta: {e}", exc_info=True)
            return BusinessDecisionResponse(
                message="Mi dispiace, ho riscontrato un errore. Riprova tra un momento.",
                product_codes=[]
            )
