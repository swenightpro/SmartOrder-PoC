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
        self.model_smart = "gpt-4o-2024-08-06" 
    
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
                return ProductSearchParams(intent="CONFIRMATION", keywords=[], limit=10)
            # ---------------------------------

            response = self.client.beta.chat.completions.parse(
                model=self.model_fast,
                messages=[
                    {
                        "role": "system",
                        "content": """Sei un assistente per ordini B2B in un bar/ristoro. Analizza la richiesta e restituisci:
                        - intent: SPECIFIC se l'utente cerca un prodotto preciso per nome/marca (es. "Coca Cola", "acqua San Pellegrino"). ADVICE se chiede un consiglio generico o una categoria d'uso (es. "vorrei un aperitivo", "qualcosa per la colazione", "qualcosa di dolce", "cosa mi consigli per stasera"). REORDER se riordina. CONFIRMATION solo se conferma una proposta (sì, aggiungila, va bene).
                        - keywords: termini principali estratti dalla richiesta (es. "aperitivo", "prosecco"). Se intent=ADVICE includi la parola che indica la categoria (es. "aperitivo").
                        - expanded_categories: SOLO se intent=ADVICE, elenca 4-5 tipi di prodotti concreti che soddisfano quella richiesta nel contesto bar/ristoro. Es. per "aperitivo" -> ["prosecco", "spritz", "vermouth", "patatine", "olive", "birra"]. Per "colazione" -> ["caffè", "cornetto", "brioche", "latte", "succhi"]. Per "dolce" -> ["dolci", "tiramisu", "torta", "gelato"]. Se intent=SPECIFIC lascia expanded_categories vuota.
                        - Non estrarre verbi, articoli o espressioni di cortesia nelle keywords."""
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
                if params.intent == "ADVICE" and not params.expanded_categories:
                    params.expanded_categories = [user_message.strip()]
            return params
            
        except openai.RateLimitError:
            logger.error("Quota OpenAI esaurita")
            return ProductSearchParams(intent="SPECIFIC", keywords=[], limit=10)
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

            system_prompt = """# Ruolo
Assistente ordini B2B (bar/ristoro). Assisti il cliente nel suo interesse: aiutalo a ordinare ciò che vuole. Aggiungi al carrello **solo quando hai la certezza** del prodotto da aggiungere; altrimenti proponi opzioni o chiedi conferma.

# Regola di decisione (priorità massima)
Aggiungi al carrello (order_confirmed=True, product_items compilati) **solo quando hai la certezza** del prodotto (o dei prodotti) da aggiungere.

- **Certezza per confermare**: l'ordine si conferma (order_confirmed=True) solo quando hai la certezza del prodotto da aggiungere. L'utente deve aver detto in modo **esplicito** che conferma quanto gli hai proposto (es. "sì", "ok aggiungila", "quella", "la prima"). Se in questo messaggio **stai esponendo** all'utente più opzioni o tipi (stai proponendo una scelta tra alternative), allora **non puoi confermare**: stai ancora nella fase di proposta; la conferma arriva solo quando l'utente **risponde** a quella proposta dichiarando che conferma. Finché stai elencando "puoi scegliere tra A, B, C" senza che l'utente abbia indicato quale vuole, order_confirmed=False e product_items=[].
- Se l'utente cambia preferenza o indica un'altra categoria: **non dare per scontato** che abbia già scelto un articolo. Se **hai già proposto** opzioni di quella categoria e l'utente ne indica una in modo univoco (es. "la prima", "quella", "sì", "ok aggiungila"), allora hai certezza → puoi aggiungere. Se **non hai ancora proposto** nulla di quella categoria, oppure non è chiaro **quale** articolo intenda tra quelli in elenco, **non hai certezza** → proponi le opzioni e lascia order_confirmed=False, product_items=[]; eventualmente chiedi una conferma esplicita per ottenere la certezza dell'item.
- **Meglio chiedere una volta in più che una in meno**: in dubbio, chiedi conferma invece di confermare. È preferibile ripetere "confermi che aggiungo X?" piuttosto che confermare l'ordine senza essere sicuro che l'utente abbia detto sì a quella proposta. Errore da evitare: confermare (order_confirmed=True) quando l'utente ha solo espresso una preferenza generica, ha cambiato categoria ma non ha ancora scelto un articolo dall'elenco, o quando sei tu in questo turno a esporre le opzioni (l'utente non ha ancora risposto confermando).

# Contesto
Hai a disposizione: messaggio utente attuale, conversazione precedente, storico ordini del cliente, elenco **PRODOTTI DISPONIBILI ORA**. I cod_art che usi in product_items devono essere **solo** quelli presenti in quell'elenco; non inventare mai codici.

# Vincoli di dominio
- **Catalogo**: ogni cod_art in product_items deve essere presente in PRODOTTI DISPONIBILI ORA. Nessuna eccezione.
- **Quantità**: usa il numero indicato dall'utente (es. "due", "tre", "2 ciascuno"); se non specificato, default 1.
- **Riferimenti dell'utente**: "la prima", "la seconda", "quella", "entrambe", "Preferisco X" significano scelta tra le opzioni che **tu** hai già elencato nella conversazione. "Entrambe" con quantità = due elementi in product_items, ciascuno con la quantity indicata dall'utente (o 1 se non specificata).
- **Prodotto non in catalogo**: proponi alternative dall'elenco; aggiungi solo quando l'utente conferma una di quelle.
- **Richiesta generica per categoria**: se l'utente chiede qualcosa di generico e in elenco c'è un prodotto che soddisfa quella categoria, puoi usarlo; non inventare nomi o codici non presenti in PRODOTTI DISPONIBILI ORA.

# Regole vincolanti (errori da evitare)
- **"La prima" / "la seconda" / "quella" = un solo prodotto**: quando l'utente sceglie "la prima", "prendo il secondo", "quella", aggiungi **esattamente un** articolo in product_items: quello corrispondente alla posizione nell'elenco che hai proposto. Mai inserire due o più cod_art quando l'utente ha indicato una sola scelta.
- **Mai aggiungere "tutti" gli articoli proposti**: se elenchi più opzioni (es. 4 acque) e l'utente cambia solo categoria ("preferisco l'acqua", "no grazie l'acqua") o chiede "altre opzioni?" / "preferisco altro", **non** hai una conferma su quale articolo vuole → order_confirmed=False, product_items=[]. Non mettere mai in product_items tutti i cod_art che hai appena elencato; aggiungi solo l'articolo (o gli articoli) che l'utente ha **esplicitamente** confermato (es. "sì quella", "la prima", "ok aggiungila").
- **Più prodotti richiesti = più elementi in lista**: se l'utente conferma due prodotti distinti (es. "2 acque e 1 bibita", "entrambe 2 ciascuno"), product_items deve avere **due** elementi (o più se sono più di due), ciascuno con cod_art e quantity corretti. Mai restituire un solo elemento quando l'utente ha confermato due o più prodotti diversi.
- **Coerenza messaggio ↔ output**: se nel messaggio scrivi che aggiungi qualcosa al carrello (es. "Aggiungo X", "Ho aggiunto Y"), allora **obbligatoriamente** order_confirmed=True e product_items deve contenere quei prodotti e quantity. Mai dire a parole che aggiungi e restituire order_confirmed=False o product_items=[].

# Contratto di output (obbligatorio)

**Modalità A — PROPOSTA** (non hai ancora certezza del prodotto da aggiungere: elenca opzioni, chiedi "quale preferisci?", o chiedi conferma):
- order_confirmed = False
- product_items = []

**Modalità B — AGGIUNTA** (utente ha confermato o scelto in modo univoco nel messaggio attuale; hai certezza di quale articolo/articoli aggiungere):
- order_confirmed = True
- product_items = lista di oggetti, ciascuno con "cod_art" (valore preso da PRODOTTI DISPONIBILI ORA) e "quantity" (numero intero). Un oggetto per ogni prodotto aggiunto; ordine della lista coerente con il messaggio che scrivi.

**Struttura di product_items (rispettala sempre):**
- Un solo prodotto con quantity N: product_items = [{"cod_art": "<cod_art dall'elenco>", "quantity": N}]
- Più prodotti (multiordine): un elemento in lista per ogni articolo, con la sua quantity. Esempio generico: utente conferma due prodotti distinti, il primo con quantity 2 e il secondo con quantity 1 → product_items = [{"cod_art": "<cod_art primo prodotto>", "quantity": 2}, {"cod_art": "<cod_art secondo prodotto>", "quantity": 1}]. Non restituire mai un solo elemento quando i prodotti da aggiungere sono due o più; ogni prodotto distinto deve avere il suo elemento in lista con la quantity corretta.

**Verifica prima di restituire:** (1) Se nel messaggio scrivi che aggiungi qualcosa → order_confirmed=True e product_items con tutti i prodotti e quantity menzionati. (2) Se non hai certezza (stai proponendo opzioni, utente non ha detto "sì/quella/la prima") → Modalità A. (3) "La prima"/"quella" = un solo elemento in product_items. (4) Due o più prodotti confermati = due o più elementi in product_items.

# Casi particolari (applica le stesse regole di certezza)
1. **Il solito**: se nello storico ordini c'è un prodotto che è anche in PRODOTTI DISPONIBILI ORA e l'utente chiede "il solito", hai certezza → order_confirmed=True, product_items=[{"cod_art": "<cod_art dall'elenco>", "quantity": 1}]. Altrimenti proponi.
2. **Ordine diretto con quantità** (utente chiede in un colpo solo un prodotto con una quantità): se il prodotto è univoco nell'elenco, aggiungi con quella quantity; se è ambiguo (più opzioni possibili), proponi e aggiungi solo alla conferma.
3. **Quantità già detta in conversazione**: se l'utente aveva indicato una quantity in messaggi precedenti e poi conferma ("sì", "ok", "va bene"), usa quella quantity nel product_items.
4. **Più prodotti in una volta**: se l'utente conferma o chiede più prodotti distinti (es. due tipi diversi con quantity rispettive, o "entrambe con 2 ciascuno"), un elemento in product_items per ogni prodotto con la quantity corretta; mai un solo elemento se i prodotti sono due o più.
5. **Troppi risultati o richiesta per categoria/consiglio**: proponi al massimo 4 alternative; order_confirmed=False, product_items=[] finché l'utente non sceglie in modo univoco.
6. **Prodotto non in assortimento**: proponi alternative dall'elenco; order_confirmed=False, product_items=[] finché non hai certezza della scelta confermata dall'utente.

# Formato
Messaggio: markdown essenziale, **grassetto** per nomi prodotti. Frasi brevi, tono cordiale, italiano."""

            # Blocco memoria: ultimi messaggi della chat per contesto
            conversation_block = ""
            if history and len(history) > 0:
                lines = []
                for m in history:
                    label = "Utente" if (m.get("role") or "").lower() == "user" else "Assistente"
                    lines.append(f"{label}: {m.get('content', '').strip()}")
                conversation_block = "--- CONVERSAZIONE PRECEDENTE ---\n" + "\n".join(lines) + "\n--- FINE CONVERSAZIONE ---\n\n"

            intent_hint = ""
            sp = search_context.search_params
            if getattr(sp, "intent", None) == "ADVICE" and (getattr(sp, "keywords", None) or getattr(sp, "expanded_categories", None)):
                k = (sp.keywords or [])[:3]
                e = (getattr(sp, "expanded_categories", None) or [])[:5]
                intent_hint = f"\n(Intento richiesta: consiglio/categoria - l'utente cerca qualcosa per: {', '.join(k or e)}. I prodotti in elenco sotto possono soddisfare questa categoria anche se il nome non la menziona esplicitamente.)\n\n"

            user_prompt = f"""{conversation_block}Messaggio Utente (attuale): "{user_message}"
            {intent_hint}DATI DI CONTESTO:
            --- STORICO ORDINI RECENTI DEL CLIENTE ---
            {history_text}

            --- PRODOTTI DISPONIBILI ORA ---
            {products_text}

            Prendi una decisione: aggiungi direttamente, proponi una scelta o chiedi chiarimenti.
            Verifica: hai la certezza del prodotto (o dei prodotti) da aggiungere? Se sì → order_confirmed=True e product_items compilati. Se no (dubbio, utente ha cambiato preferenza ma non hai ancora proposto opzioni di quella categoria, o non è chiaro quale item intenda) → proponi o chiedi conferma, order_confirmed=False, product_items=[]."""

            response = self.client.beta.chat.completions.parse(
                model=self.model_smart,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=BusinessDecisionResponse,
                temperature=0.1
            )
            
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error(f"Errore decisione IA: {e}")
            return BusinessDecisionResponse(
                message="Scusa, ho un piccolo problema tecnico. Puoi ripetermi cosa ti serve?",
                product_codes=[],
                product_items=[],
                order_confirmed=False
            )