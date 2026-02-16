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
            logger.info(f"Analisi semantica messaggio: '{user_message}'")
            
            response = self.client.beta.chat.completions.parse(
                model=self.model_fast,
                messages=[
                    {
                        "role": "system",
                        "content": """Sei un esperto di catalogo prodotti. Il tuo compito è capire COSA sta cercando l'utente.
                        
                        - Estrai parole chiave significative (marca, tipo, variante).
                        - Se l'utente chiede un consiglio generico (es. "cosa mi consigli?"), lascia keywords vuote ma identifica la categoria se possibile.
                        - Correggi eventuali errori di battitura (es. "birra peroni" invece di "birra peronni").
                        - Se l'utente vuole 'il solito', non estrarre keyword ma lascia che sia il contesto dello storico a decidere."""
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                response_format=ProductSearchParams
            )
            
            return response.choices[0].message.parsed
            
        except openai.RateLimitError:
            logger.error("Quota OpenAI esaurita")
            return ProductSearchParams(keywords=[], limit=10)
        except Exception as e:
            logger.error(f"Errore estrazione parametri: {e}")
            raise
    
    def make_business_decision(
        self,
        user_message: str,
        search_context: SearchContext
    ) -> BusinessDecisionResponse:
        try:
            logger.info("IA sta prendendo una decisione commerciale...")
            
            products_text = "\n".join([
                f"- COD: {p.cod_art} | {p.des_art} | Famiglia: {p.famiglia} | Prezzo/UM: {p.des_um}"
                for p in search_context.products[:15]
            ]) if search_context.products else "Nessun prodotto trovato in catalogo."

            history_text = "\n".join([
                f"- {h.des_art} (Cod: {h.cod_art}) ordinato {h.qta_ordinata} volte. Ultimo ordine: {h.data_ord}"
                for h in search_context.order_history[:10]
            ]) if search_context.order_history else "Il cliente non ha ordini precedenti."

            system_prompt = """Sei un ASSISTENTE ALLA VENDITA proattivo e intelligente. Il tuo obiettivo è aiutare il cliente a completare l'ordine nel minor tempo possibile, offrendo consigli pertinenti.

            REGOLE DI RAGIONAMENTO:
            1. IL 'SOLITO': Se l'utente chiede "il solito" o "come l'altra volta", cerca nello STORICO e aggiungi direttamente il prodotto più frequente o l'ultimo ordinato.
            2. CONSIGLIO: Se l'utente è indeciso, guarda lo STORICO. Se ha già comprato un prodotto simile, suggerisci quello. Se non ha storico, suggerisci i primi 2 prodotti del catalogo spiegando perché sono validi.
            3. TROPPI RISULTATI (>3): Non elencarli tutti. Di': "Ho trovato diverse opzioni per [X], preferisci una marca specifica o un formato particolare?" e proponi 2 alternative top.
            4. CROSS-SELLING: Se aggiungi un prodotto (es. Pasta), suggerisci brevemente qualcosa che si abbina (es. "Ti serve anche del sugo?").
            
            TONO: Cordiale, professionale, italiano naturale (evita traduzioni letterali dall'inglese).

            LOGICA FLAG:
            - order_confirmed = TRUE solo se hai un COD_ART certo da aggiungere.
            - product_codes = [codice] solo se order_confirmed è TRUE."""

            user_prompt = f"""Messaggio Utente: "{user_message}"

            DATI DI CONTESTO:
            --- STORICO ORDINI RECENTI DEL CLIENTE ---
            {history_text}

            --- PRODOTTI DISPONIBILI ORA ---
            {products_text}

            Prendi una decisione: aggiungi direttamente, proponi una scelta o chiedi chiarimenti."""

            response = self.client.beta.chat.completions.parse(
                model=self.model_smart,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=BusinessDecisionResponse,
                temperature=0.7
            )
            
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error(f"Errore decisione IA: {e}")
            return BusinessDecisionResponse(
                message="Scusa, ho un piccolo problema tecnico. Puoi ripetermi cosa ti serve?",
                product_codes=[],
                order_confirmed=False
            )