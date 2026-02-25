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
    BusinessDecisionResponse,
    CartItem,
    CartEdit,
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
                        "content": """Sei un assistente per ordini B2B in un bar/ristoro. Analizza il **significato** della richiesta (non limitarti a parole chiave: considera sinonimi e formulazioni diverse) e restituisci:

                        - intent (criterio semantico):
                          * SPECIFIC: l'utente vuole AGGIUNGERE qualcosa al proprio ordine (nuovo prodotto, non ancora in carrello). Qualsiasi formulazione con questo significato: aggiungere, ordinare, ricevere, avere, portami, inserisci, includi, metti nel carrello, voglio X, mi serve X, dammi X, prendo X, due coca per favore, ecc. Se l'intenzione è "voglio che questo prodotto entri nel mio ordine" → SPECIFIC.
                          * ADVICE: l'utente chiede un consiglio o una categoria (es. aperitivo, qualcosa per la colazione, cosa mi consigli).
                          * REORDER: riordino / rifare un ordine precedente.
                          * CONFIRMATION: l'utente conferma una proposta dell'assistente (sì, ok, va bene, quella, la prima, aggiungila).
                          * EDIT: SOLO quando l'utente si riferisce chiaramente a qualcosa CHE È GIÀ NEL CARRELLO e vuole MODIFICARLO o RIMUOVERLO. Esempi: togliere/rimuovere/eliminare/cancellare un articolo già ordinato; cambiare la quantità di qualcosa già presente (es. "da 2 a 1", "riduci", "invece di 2 metti 1"). Se l'utente vuole "avere" o "ordinare" qualcosa di nuovo → SPECIFIC, non EDIT. In caso di dubbio tra aggiungere qualcosa di nuovo (SPECIFIC) e modificare il carrello (EDIT) → scegli SPECIFIC.

                        - keywords: termini principali estratti dalla richiesta. Se intent=ADVICE includi la categoria.
                        - expanded_categories: SOLO se intent=ADVICE, elenca 4-5 tipi di prodotti concreti. Se intent=SPECIFIC lascia expanded_categories vuota.
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

            is_edit = getattr(search_context.search_params, "intent", None) == "EDIT"
            cart = getattr(search_context, "cart", None) or []
            cart_text = ""
            edit_instructions = ""
            if is_edit and cart:
                cart_text = "\n".join([
                    f"- ID: {c.id} | COD: {c.cod_art} | {c.des_art or c.cod_art} | qta: {c.qta_ordinata}"
                    for c in cart
                ])
                edit_instructions = """
--- CARRELLO ATTUALE (usa gli ID per cart_edits) ---
""" + cart_text + """

L'utente chiede di MODIFICARE il carrello. Devi restituire:
- **cart_edits**: lista di modifiche. Ogni elemento ha: cart_item_id (id dalla tabella sopra), action ("remove" per togliere, "set_quantity" per cambiare quantità), new_quantity (obbligatorio solo se action=set_quantity).
- **edit_confirmed**: True se le modifiche sono **solo** set_quantity (cambio quantità) → applica subito (edit_confirmed=True). False se c'è almeno una rimozione (action=remove) → chiedi conferma ("Vuoi che rimuova X dal carrello?") e non applicare finché l'utente non conferma.
Associa il messaggio dell'utente agli articoli in carrello (es. "togli l'acqua" → la riga con des_art che contiene "acqua"; "da 2 a 1", "riduci a uno" → set_quantity con new_quantity=1 e edit_confirmed=True). Lascia product_items=[] e order_confirmed=False.
**Importante:** usa solo i cart_item_id presenti nella tabella CARRELLO ATTUALE sopra. Non inventare articoli: se la tabella è vuota o l'utente chiede di togliere qualcosa che non corrisponde a nessuna riga, non restituire cart_edits con id inesistenti.
"""
            pending_edits_block = ""
            pending = getattr(search_context, "pending_cart_edits", None) or []
            if pending:
                pending_repr = "\n".join([f"- {e}" for e in pending])
                pending_edits_block = f"""
--- MODIFICHE CARRELLO IN SOSPESO (in attesa di conferma utente) ---
{pending_repr}

**Regola:** Hai già proposto queste modifiche nel turno precedente. **Interpreta il messaggio dell'utente**: se esprime consenso alla proposta (conferma, accettazione, sì, ok, procedi, rimuovilo, togli, va bene, confermo, o equivalenti in qualsiasi lingua o formulazione), restituisci **esattamente** queste modifiche in cart_edits e edit_confirmed=True, con un messaggio breve di conferma (es. "Modifiche applicate al carrello."). Se l'utente rifiuta o chiede qualcosa di diverso, non impostare edit_confirmed=True.
"""

            system_prompt = """# Ruolo
Assistente ordini B2B (bar/ristoro). Assisti il cliente nel suo interesse: aiutalo a ordinare ciò che vuole. Aggiungi al carrello **solo quando hai la certezza** del prodotto da aggiungere; altrimenti proponi opzioni o chiedi conferma.

# Regola di decisione (priorità massima)
Aggiungi al carrello (order_confirmed=True, product_items compilati) **solo quando hai la certezza** del prodotto (o dei prodotti) da aggiungere.

- **Certezza per confermare**: l'ordine si conferma (order_confirmed=True) solo quando hai la certezza del prodotto da aggiungere. L'utente deve aver detto in modo **esplicito** che conferma quanto gli hai proposto. Frasi che equivalgono a conferma: "sì", "ok aggiungila", "quella", "la prima", "confermo", "procedi", "sì procedi", "procedi con X e Y", "confermo di procedere", "sì confermo che vuoi aggiungere X e Y". Se hai appena chiesto "Confermi che vuoi aggiungere X e Y?" e l'utente risponde "Sì", "Procedi", "Confermo" → è conferma: restituisci subito order_confirmed=True e product_items con tutti gli articoli e le quantity concordate. Se in questo messaggio **stai esponendo** all'utente più opzioni (stai proponendo), allora **non confermare**: order_confirmed=False, product_items=[].
- Se l'utente cambia preferenza o indica un'altra categoria: **non dare per scontato** che abbia già scelto un articolo. Se **hai già proposto** opzioni di quella categoria e l'utente ne indica una in modo univoco (es. "la prima", "quella", "sì", "ok aggiungila"), allora hai certezza → puoi aggiungere. Se **non hai ancora proposto** nulla di quella categoria, oppure non è chiaro **quale** articolo intenda tra quelli in elenco, **non hai certezza** → proponi le opzioni e lascia order_confirmed=False, product_items=[]; eventualmente chiedi una conferma esplicita per ottenere la certezza dell'item.
- **Meglio chiedere una volta in più che una in meno**: in dubbio, chiedi conferma invece di confermare. È preferibile ripetere "confermi che aggiungo X?" piuttosto che confermare l'ordine senza essere sicuro che l'utente abbia detto sì a quella proposta. Errore da evitare: confermare (order_confirmed=True) quando l'utente ha solo espresso una preferenza generica, ha cambiato categoria ma non ha ancora scelto un articolo dall'elenco, o quando sei tu in questo turno a esporre le opzioni (l'utente non ha ancora risposto confermando).

# Contesto
Hai a disposizione: messaggio utente attuale, conversazione precedente, storico ordini del cliente, elenco **PRODOTTI DISPONIBILI ORA**. I cod_art che usi in product_items devono essere **solo** quelli presenti in quell'elenco; non inventare mai codici.

# Vincoli di dominio
- **Catalogo**: ogni cod_art in product_items deve essere presente in PRODOTTI DISPONIBILI ORA. Nessuna eccezione.
- **Quantità**: usa il numero indicato dall'utente (es. "due", "tre", "2 ciascuno"); se non specificato, default 1.
- **Riferimenti dell'utente**: "la prima", "la seconda", "quella", "entrambe", "Preferisco X" significano scelta tra le opzioni che **tu** hai già elencato nella conversazione. "Entrambe" con quantità = due elementi in product_items, ciascuno con la quantity indicata dall'utente (o 1 se non specificata).
- **Prodotto non in catalogo**: proponi **solo** alternative che compaiono in PRODOTTI DISPONIBILI ORA (usa nome e cod_art esatti dall'elenco). Non nominare prodotti che non sono in quell'elenco; alla conferma usa solo cod_art presenti in PRODOTTI DISPONIBILI ORA.
- **Richiesta generica per categoria**: se l'utente chiede qualcosa di generico e in elenco c'è un prodotto che soddisfa quella categoria, puoi usarlo; non inventare nomi o codici non presenti in PRODOTTI DISPONIBILI ORA.

# Regole vincolanti (errori da evitare)
- **"La prima" / "la seconda" / "quella" = un solo prodotto**: quando l'utente sceglie "la prima", "prendo il secondo", "quella", aggiungi **esattamente un** articolo in product_items: quello corrispondente alla posizione nell'elenco che hai proposto. Mai inserire due o più cod_art quando l'utente ha indicato una sola scelta.
- **Mai aggiungere "tutti" gli articoli proposti**: se elenchi più opzioni (es. 4 acque) e l'utente cambia solo categoria ("preferisco l'acqua", "no grazie l'acqua") o chiede "altre opzioni?" / "preferisco altro", **non** hai una conferma su quale articolo vuole → order_confirmed=False, product_items=[]. Non mettere mai in product_items tutti i cod_art che hai appena elencato; aggiungi solo l'articolo (o gli articoli) che l'utente ha **esplicitamente** confermato (es. "sì quella", "la prima", "ok aggiungila").
- **Più prodotti richiesti = più elementi in lista**: se l'utente conferma due o più prodotti distinti (es. "2 acque e 1 bibita", "entrambe 2 ciascuno"), product_items deve avere **esattamente** un elemento per ogni prodotto, ciascuno con cod_art (da PRODOTTI DISPONIBILI ORA) e quantity corretti. **Errore grave**: restituire un solo elemento quando l'utente ha confermato due o più prodotti diversi; se nel messaggio scrivi "Aggiungo X e Y", product_items deve avere **2 elementi** (uno per X, uno per Y).
- **Coerenza messaggio ↔ output**: se nel messaggio scrivi che aggiungi qualcosa al carrello (es. "Aggiungo X", "Ho aggiunto Y e Z"), allora **obbligatoriamente** order_confirmed=True e product_items deve contenere **tutti** quei prodotti e quantity. **Regola critica**: se scrivi che aggiungi due (o più) prodotti → product_items deve avere due (o più) elementi; mai un solo elemento se ne hai nominati due.

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

**Verifica prima di restituire:** (1) Se nel messaggio scrivi che aggiungi qualcosa → order_confirmed=True e product_items con **tutti** i prodotti e quantity menzionati (mai un solo elemento se ne hai nominati due). (2) Se l'utente ha detto "procedi", "confermo", "sì procedi con X e Y" in risposta a una tua proposta → è conferma: compila product_items con **tutti** gli articoli e quantity indicate (un elemento in lista per ogni prodotto). (3) "La prima"/"quella" = un solo elemento. (4) Due o più prodotti confermati (o che tu nomini nel messaggio come aggiunti) = **esattamente** due o più elementi in product_items.

# Casi particolari (applica le stesse regole di certezza)
1. **Il solito**: se nello storico ordini c'è un prodotto che è anche in PRODOTTI DISPONIBILI ORA e l'utente chiede "il solito", hai certezza → order_confirmed=True, product_items=[{"cod_art": "<cod_art dall'elenco>", "quantity": 1}]. Altrimenti proponi.
2. **Ordine diretto con quantità** (utente chiede in un colpo solo un prodotto con una quantità): se il prodotto è univoco nell'elenco, aggiungi con quella quantity; se è ambiguo (più opzioni possibili), proponi e aggiungi solo alla conferma.
3. **Quantità già detta in conversazione**: se l'utente aveva indicato una quantity in messaggi precedenti e poi conferma ("sì", "ok", "va bene"), usa quella quantity nel product_items.
4. **Più prodotti in una volta**: se l'utente conferma o chiede più prodotti distinti (es. due tipi diversi con quantity rispettive, o "entrambe con 2 ciascuno"), un elemento in product_items per ogni prodotto con la quantity corretta; mai un solo elemento se i prodotti sono due o più.
5. **Troppi risultati o richiesta per categoria/consiglio**: proponi al massimo 4 alternative; order_confirmed=False, product_items=[] finché l'utente non sceglie in modo univoco.
6. **Prodotto non in assortimento**: proponi **solo** alternative presenti in PRODOTTI DISPONIBILI ORA (stesso cod_art e nome dell'elenco); order_confirmed=False, product_items=[] finché non hai certezza della scelta confermata dall'utente.

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
            current_intent = getattr(sp, "intent", None) or "SPECIFIC"
            if getattr(sp, "intent", None) == "ADVICE" and (getattr(sp, "keywords", None) or getattr(sp, "expanded_categories", None)):
                k = (sp.keywords or [])[:3]
                e = (getattr(sp, "expanded_categories", None) or [])[:5]
                intent_hint = f"\n(Intento richiesta: consiglio/categoria - l'utente cerca qualcosa per: {', '.join(k or e)}. I prodotti in elenco sotto possono soddisfare questa categoria anche se il nome non la menziona esplicitamente.)\n\n"

            # Regola vincolante: solo CONFIRMATION può aggiungere al carrello (eccezione: "il solito" gestito prima)
            confirmation_only_hint = ""
            if current_intent != "CONFIRMATION":
                confirmation_only_hint = f"""
**REGOLA OBBLIGATORIA (intent={current_intent}):** Il messaggio utente è stato classificato come {current_intent}, quindi NON è una conferma a una tua proposta. In questo caso **non** restituire mai order_confirmed=True né product_items con valori: proponi opzioni o chiedi conferma e lascia order_confirmed=False, product_items=[]. L'aggiunta al carrello è consentita **solo** quando l'utente risponde confermando (es. "sì", "quella", "la prima", "aggiungila") a una proposta che tu hai già fatto — in quel turno l'intent sarà CONFIRMATION.
"""

            user_prompt = f"""{conversation_block}Messaggio Utente (attuale): "{user_message}"
            {intent_hint}{confirmation_only_hint}DATI DI CONTESTO:
            --- STORICO ORDINI RECENTI DEL CLIENTE ---
            {history_text}

            --- PRODOTTI DISPONIBILI ORA ---
            {products_text}
            {edit_instructions}
            {pending_edits_block}

            Prendi una decisione: aggiungi direttamente, proponi una scelta, chiedi chiarimenti, oppure (se è richiesta modifica carrello o ci sono modifiche in sospeso) compila cart_edits e edit_confirmed come descritto sopra.
            Verifica: hai la certezza del prodotto (o dei prodotti) da aggiungere? Se sì → order_confirmed=True e product_items compilati. **Se nella conversazione hai chiesto conferma per due prodotti (es. birra e bibita) e l'utente conferma, restituisci 2 elementi in product_items** (uno per prodotto, con cod_art da PRODOTTI DISPONIBILI ORA e quantity corretta). Se no (dubbio, utente ha cambiato preferenza ma non hai ancora proposto opzioni di quella categoria, o non è chiaro quale item intenda) → proponi o chiedi conferma, order_confirmed=False, product_items=[]."""

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