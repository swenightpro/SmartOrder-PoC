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
            
            # --- AGGIUNTA: FILTRO CONFERME ---
            # Se l'utente sta solo confermando, non vogliamo che il database cerchi "si" o "ok"
            conferme = ["si", "ok", "va bene", "confermo", "aggiungi", "procedi", "corretto"]
            msg_clean = user_message.lower().strip().replace("!", "").replace(".", "")
            
            if msg_clean in conferme:
                logger.info("Rilevata conferma verbale: salto estrazione keyword per mantenere il contesto precedente.")
                return ProductSearchParams(keywords=[], limit=10)
            # ---------------------------------

            response = self.client.beta.chat.completions.parse(
                model=self.model_fast,
                messages=[
                    {
                        "role": "system",
                        "content": """Sei un assistente alla ricerca prodotti.
                        - Estrai SEMPRE i termini principali del prodotto (es: 'acqua', 'birra', 'pasta').
                        - Includi marche o varianti se specificate.
                        - Se l'utente conferma o accetta una proposta precedente senza nominare nuovi prodotti, lascia keywords vuote.
                        - Se l'utente chiede 'cosa hai' o è generico, lascia keywords vuote.
                        - Non estrarre verbi, articoli o espressioni di cortesia."""
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                response_format=ProductSearchParams
            )
            
            params = response.choices[0].message.parsed
            
            # Se l'IA non estrae nulla ma il messaggio è breve e non è una conferma, lo usiamo come keyword
            if not params.keywords and len(user_message.split()) < 5 and msg_clean not in conferme:
                params.keywords = [user_message.strip()]
                
            return params
            
        except openai.RateLimitError:
            logger.error("Quota OpenAI esaurita")
            return ProductSearchParams(keywords=[], limit=10)
        except Exception as e:
            logger.error(f"Errore estrazione parametri: {e}")
            raise
    
    def make_business_decision(
        self,
        user_message: str,
        search_context: SearchContext,
        history: Optional[List[dict]] = None
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
            2. CONSIGLIO: Se l'utente è indeciso, guarda lo STORICO. Se ha già comprato un prodotto simile, SUGGERISCI quello (ma NON aggiungere al carrello finché non dice sì). Se non ha storico, suggerisci i primi 2 prodotti del catalogo spiegando perché sono validi.
            3. TROPPI RISULTATI (>3): Non elencarli tutti. Di': "Ho trovato diverse opzioni per [X], preferisci una marca specifica o un formato particolare?" e proponi 2 alternative top.
            4. CROSS-SELLING: Suggerisci solo prodotti presenti in PRODOTTI DISPONIBILI ORA e che abbiano senso (es. per birra: stuzzichini, bibite; per pasta: sugo. Non suggerire sugo per un aperitivo a base di birra).
            - SE l'utente dice "Sì", "OK", "aggiungi", "va bene" o conferma esplicitamente E tu avevi appena suggerito un prodotto specifico nel messaggio precedente, ALLORA procedi all'aggiunta (order_confirmed=TRUE, product_codes=[codice]).
            - Se stai PROPONENDO o CHIEDENDO conferma ("Vuoi aggiungerla?", "Ti va bene?", "Quale preferisci?") l'utente NON ha ancora detto sì: metti SEMPRE order_confirmed=FALSE e product_codes=[].
            - Usa la CONVERSAZIONE PRECEDENTE (se presente) per capire riferimenti ai vari messaggi precedenti.

            TONO: Cordiale, professionale, italiano naturale (evita traduzioni letterali dall'inglese).

            LOGICA FLAG (OBBLIGATORIA):
            - order_confirmed = TRUE SOLO se l'utente ha GIÀ confermato (sì, ok, aggiungi, va bene, quella, ecc.) o ha detto "il solito". Se stai chiedendo "Vuoi aggiungerla?" / "Ti va bene?" → order_confirmed = FALSE.
            - product_codes = [codice] SOLO se order_confirmed è TRUE. Se proponi senza conferma → product_codes = []."""

            # Blocco memoria: ultimi messaggi della chat per contesto
            conversation_block = ""
            if history and len(history) > 0:
                lines = []
                for m in history:
                    label = "Utente" if (m.get("role") or "").lower() == "user" else "Assistente"
                    lines.append(f"{label}: {m.get('content', '').strip()}")
                conversation_block = "--- CONVERSAZIONE PRECEDENTE ---\n" + "\n".join(lines) + "\n--- FINE CONVERSAZIONE ---\n\n"

            user_prompt = f"""{conversation_block}Messaggio Utente (attuale): "{user_message}"

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