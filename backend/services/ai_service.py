from typing import Optional, List
import logging
from openai import OpenAI

from config import settings
from backend.models.schemas import (
    ProductSearchParams,
    Product,
    OrderHistoryItem,
    SearchContext
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
                        "content": """You extract product search parameters from Italian user messages for a product catalog search system.

TASK: Extract ONLY meaningful product-related information that can be used to search a product database.

EXTRACTION RULES:
1. Extract product names, brands, types, varieties, and any descriptive terms that identify specific products.
2. EXCLUDE all Italian grammatical words (articles, prepositions, common verbs, pronouns): articles (il, lo, la, gli, le, un, una, uno), prepositions (di, da, in, con, per, su, tra, fra, a, al, alla, del, della, dei, delle, dello), common verbs (vorrei, voglio, cerco, mi serve, ho, bisogno), pronouns (mi, ti, si).
3. EXCLUDE generic descriptive adjectives that don't help identify products: buon/buono/buona, bello/bella/belli/belle, nuovo/nuova, vecchio/vecchia, grande, piccolo, ottimo/ottima, migliore/migliori, and similar subjective qualifiers.
4. If user says "il solito" (the usual), return empty keywords array [].
5. Automatically correct spelling errors, expand abbreviations, and normalize variations to standard product names.
6. If a keyword is very generic (e.g., refers to a broad product category or container type that would return many results), set limit to at least 50 to ensure comprehensive search results.

CRITICAL: 
- Extract every word that is NOT a grammatical word or generic qualifier.
- Even generic product types must be extracted if they help identify the product.
- Never return an empty keywords array if the message contains any product-related words.
- Always correct spelling errors and normalize terms to their standard forms.
- Increase limit automatically for generic keywords that would match many products."""
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
            
        except Exception as e:
            logger.error(f"Errore estrazione parametri: {e}", exc_info=True)
            raise
    
    def make_business_decision(
        self,
        user_message: str,
        search_context: SearchContext
    ) -> str:
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
            
            system_prompt = """You are an expert and intelligent salesperson helping customers order products.

BUSINESS RULES (CRITICAL):
1. **Prioritize History**: If user says "il solito" (the usual), "come sempre" (as always), "quello di prima" (the previous one) and history is clear, proceed IMMEDIATELY with the order. Don't ask for confirmation if it's obvious.

2. **Trust the Search**: If user asks for a new product and search finds valid candidates, propose/add DIRECTLY the best product. Don't ask "do you want this or that?" if there's an obvious choice.

3. **Avoid Friction**: Ask for clarification ONLY if:
   - Search returns 0 results
   - There's a TOTAL ambiguity impossible to resolve
   
   If you're 20-30% uncertain, proceed anyway with the most likely option based on:
   - Customer history (if available)
   - Best-sellers or most common products
   - First search result

4. **Tone**: Be professional but friendly, like a trusted salesperson. Don't be verbose, be direct.

5. **Multiple Products Found**: 
   - If 1 product: Propose it directly ("Ti consiglio [product name]. Vuoi che lo aggiunga?")
   - If 2-10 products: LIST ALL of them with numbers and ask which one:
     Format: "Ho trovato questi prodotti:\n1. [product 1 name]\n2. [product 2 name]\n3. [product 3 name]\n...\n\nQuale preferisci?"
   - If MORE than 10 products: DO NOT list them all. Instead, ask SPECIFIC questions to narrow down the search:
     Ask targeted questions about brand, variety, format, or other distinguishing characteristics.
     The goal is to help the user narrow down their choice through targeted questions, not overwhelm them with a long list.

6. **Response Format**: 
   - If adding a product: "Perfetto! Ho aggiunto [product name] al tuo ordine."
   - If proposing single product (1 result): "Ti consiglio [product name]. Vuoi che lo aggiunga?"
   - If 2-10 products: List ALL of them with numbers and ask which one.
   - If MORE than 10 products: Ask specific questions to narrow down (brand, variety, format, etc.) instead of listing all.
   - If clarification needed (0 results): "Non ho trovato prodotti corrispondenti. Puoi essere più specifico?"
   - If confirming from history: "Come sempre, ho aggiunto [product name]."

IMPORTANT: Always respond in ITALIAN, naturally and concisely."""

            user_prompt = f"""User message: "{user_message}"

PRODUCTS FOUND (catalog search):
{products_text}

CUSTOMER ORDER HISTORY (recent orders):
{history_text}

Analyze the message and make a decision. Follow the business rules above.
If user asks for "il solito" (the usual) and history is clear, proceed directly.
If search found valid products for a new request, propose/add the best one.
Ask for clarification ONLY if necessary (0 results or total ambiguity)."""

            response = self.client.chat.completions.create(
                model=self.model_smart,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            message = response.choices[0].message.content
            logger.info(f"Risposta generata: {message}")
            return message.strip()
            
        except Exception as e:
            logger.error(f"Errore generazione risposta: {e}", exc_info=True)
            return "Mi dispiace, ho riscontrato un errore. Riprova tra un momento."
