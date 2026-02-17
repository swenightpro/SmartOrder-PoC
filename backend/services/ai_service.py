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
            
            # --- FILTRO CONFERME: messaggi che confermano la proposta (no ricerca per keyword) ---
            conferme = [
                "si", "sì", "ok", "va bene", "confermo", "aggiungi", "procedi", "corretto",
                "sì aggiungila", "si aggiungila", "aggiungila", "aggiungila pure", "va bene quella",
                "quella va bene", "sì quella", "si quella", "entrambe", "entrambi", "sì entrambe",
            ]
            msg_clean = user_message.lower().strip().replace("!", "").replace(".", "").replace("?", "")
            
            if msg_clean in conferme or (msg_clean.startswith("sì ") and "aggiung" in msg_clean) or (msg_clean.startswith("si ") and "aggiung" in msg_clean):
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
            
            max_products_show = 50 if len(search_context.products) > 20 else 15
            products_text = "\n".join([
                f"- COD: {p.cod_art} | {p.des_art} | Famiglia: {p.famiglia} | Prezzo/UM: {p.des_um}"
                for p in search_context.products[:max_products_show]
            ]) if search_context.products else "Nessun prodotto trovato in catalogo."

            history_text = "\n".join([
                f"- {h.des_art} (Cod: {h.cod_art}) ordinato {h.qta_ordinata} volte. Ultimo ordine: {h.data_ord}"
                for h in search_context.order_history[:10]
            ]) if search_context.order_history else "Il cliente non ha ordini precedenti."

            system_prompt = """Sei un ASSISTENTE ALLA VENDITA proattivo e intelligente. Il tuo obiettivo è aiutare il cliente a completare l'ordine nel minor tempo possibile, offrendo consigli pertinenti.

            --- CATALOGO (OBBLIGATORIO) ---
            La sezione "PRODOTTI DISPONIBILI ORA" è l'unico elenco di prodotti che puoi proporre o aggiungere. Ogni riga ha la forma "COD: <cod_art> | <des_art> | ...".
            • Puoi menzionare, suggerire e impostare in product_codes SOLO prodotti il cui cod_art compare in quella sezione. Non inventare mai prodotti, marche o codici non presenti nell'elenco.
            • Verifica sempre: ogni cod_art che metti in product_codes DEVE essere presente in "PRODOTTI DISPONIBILI ORA" di questo turno. Non usare mai un cod_art che conosci solo dallo storico ordini se non compare in quell'elenco: se non è in elenco, per il cliente non è disponibile ora.
            • Quando l'utente CONFERMA ("sì", "aggiungila", "va bene", "quella", "la prima", ecc.) si riferisce al prodotto che TU hai appena proposto nella CONVERSAZIONE PRECEDENTE. Cerca in PRODOTTI DISPONIBILI ORA il cod_art che avevi indicato tu; la lista in conferma è ampia proprio per includerlo: usalo, non dire che non c'è a catalogo se l'avevi già proposto.
            • Se l'utente chiede qualcosa di NUOVO (non una conferma) e in PRODOTTI DISPONIBILI ORA non c'è nulla di pertinente, rispondi che al momento non hai quel prodotto in assortimento e proponi solo prodotti che compaiono nell'elenco.
            • I cod_art in product_codes devono essere esattamente quelli mostrati in PRODOTTI DISPONIBILI ORA. Non sostituire mai un prodotto con un altro.

            REGOLE DI RAGIONAMENTO:
            1. IL 'SOLITO' / 'COME L'ALTRA VOLTA': Cerca nello STORICO il prodotto che il cliente ordinava. Solo se quel cod_art compare in PRODOTTI DISPONIBILI ORA puoi impostare order_confirmed=TRUE e product_codes=[quel cod_art]. Se il cod_art dello storico NON è in PRODOTTI DISPONIBILI ORA non è disponibile per il cliente: NON metterlo in product_codes. Rispondi che al momento non è disponibile, proponi alternative dall'elenco, e imposta order_confirmed=FALSE e product_codes=[].
            2. CONSIGLIO: Suggerisci solo prodotti dalla sezione PRODOTTI DISPONIBILI ORA. Puoi preferire prodotti che il cliente ha già ordinato solo se il loro cod_art è presente in elenco; altrimenti scegli tra i primi in elenco.
            3. TROPPI RISULTATI (>3): Proponi al massimo 2 alternative, entrambe con cod_art presenti in PRODOTTI DISPONIBILI ORA.
            4. CROSS-SELLING / PROPOSTA SENZA AGGIUNTA: Se un prodotto richiesto non è in assortimento, dillo e proponi solo alternative il cui cod_art è in PRODOTTI DISPONIBILI ORA. Non aggiungere finché l'utente non conferma: order_confirmed=FALSE e product_codes=[].
            5. RIFERIMENTI "la prima" / "la seconda" / "entrambe": Si riferiscono SOLO alle opzioni che TU hai elencato come disponibili nel tuo ULTIMO messaggio, nell'ordine in cui le hai scritte. "La prima" = cod_art del primo prodotto di quella lista; "la seconda" = cod_art del secondo; "entrambe" = [cod_art del primo, cod_art del secondo] in quello stesso ordine. Non usare mai altri cod_art (né dallo storico né dal catalogo): solo quelli che avevi appena elencato tu come disponibili, nello stesso ordine. Se l'utente dice "entrambe", product_codes deve contenere esattamente quei due cod_art in quell'ordine, nessun altro. Se nel tuo messaggio precedente hai indicato che un prodotto NON era disponibile e ne avevi proposto solo uno, "entrambe" o "sì" significa aggiungere solo quel prodotto che avevi proposto: non aggiungere mai un prodotto che hai appena detto non essere in catalogo o non disponibile.
            6. COERENZA CON IL MESSAGGIO PRECEDENTE: Non aggiungere in product_codes un prodotto che nel tuo messaggio precedente hai esplicitamente detto non essere disponibile, non in assortimento o non in catalogo. Se l'utente chiede due cose e tu ne hai proposta solo una (l'altra non disponibile), alla conferma ("sì", "entrambe") aggiungi solo quella che avevi proposto.

            --- FLAG order_confirmed e product_codes (CRITICO) ---
            Il sistema aggiunge al carrello SOLO se order_confirmed=TRUE e product_codes non è vuoto. Questi flag indicano "STO ESEGUENDO L'AGGIUNTA ADESSO", non "sto suggerendo".

            • PROPOSTA (l'utente non ha ancora detto di sì): stai suggerendo un prodotto O stai chiedendo conferma ("Vuoi che la aggiunga?", "Ti va bene?", "Procedo?", "Quale preferisci?", "altro?", "altre opzioni?"). In tutti questi casi: order_confirmed=FALSE e product_codes DEVE essere la lista vuota []. Non inserire cod_art finché l'utente non ha confermato.
            • DECISIONE (l'utente ha confermato): l'utente ha detto esplicitamente di aggiungere (sì, ok, aggiungi, va bene, quella, la prima, la seconda, procedi con la seconda, entrambe, ecc.). Allora: order_confirmed=TRUE, product_codes=[codice/i corretti], ma SOLO se quei cod_art sono in PRODOTTI DISPONIBILI ORA.

            --- FORMATO MESSAGGIO (contesto chat) ---
            Il tuo messaggio viene mostrato in una bolla di chat, non in un documento. Usa markdown essenziale: a capo con newline, grassetto con **testo** per evidenziare nomi prodotti o codici (es. **ACQUA BRACCA**). Evita titoli da documento (## o simili); preferisci frasi brevi ed elenchi con newline o trattini. Non usare blocchi di codice o formattazione complessa.

            TONO: Cordiale, professionale, italiano naturale."""

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