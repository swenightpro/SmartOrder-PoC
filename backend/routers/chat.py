import re
import logging
from typing import List, Tuple

from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse, SearchContext, BusinessDecisionResponse, ProductItem
from services.ai_service import AIService
from services.db_service import DatabaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

ai_service = AIService()
db_service = DatabaseService()

def _ensure_message_output_coherence(
    assistant_message: str,
    products: list,
    current_items: List[ProductItem],
    current_order_confirmed: bool,
    user_intent_confirmation: bool,
) -> Tuple[List[ProductItem], bool]:
    """
    Se l'output è incoerente (utente aveva confermato ma product_items vuoto, oppure
    messaggio cita più prodotti di quelli restituiti), prova a inferire product_items
    dal testo usando la lista prodotti disponibili. Nessuna lista di frasi: si decide
    solo da contesto (intent conferma) e confronto output vs menzioni nel messaggio.
    """
    if not assistant_message or not products:
        return current_items, current_order_confirmed

    # Cerca nel messaggio riferimenti a prodotti (cod_art o des_art) e quantità; ordine per posizione nel messaggio
    msg_clean = re.sub(r"\*\*", "", assistant_message)
    msg_upper = msg_clean.upper()
    extracted_with_pos: List[Tuple[str, float, int]] = []  # (cod_art, quantity, position)
    seen_cod = set()

    for p in products:
        cod, des = (getattr(p, "cod_art", None) or ""), (getattr(p, "des_art", None) or "")
        if not cod or cod in seen_cod:
            continue
        best_pos = -1
        qty = 1.0
        # Match cod_art come parola
        m = re.search(r"\b" + re.escape(cod) + r"\b", assistant_message, re.IGNORECASE)
        if m:
            best_pos = m.start()
            qty = _parse_quantity_near(assistant_message, cod, des)
        else:
            # Match des_art: tronchi e prime 2-4 parole (per trovare anche secondo prodotto con nome simile)
            words = des.split()
            des_stems = [
                (des[:50] if len(des) > 50 else des).strip(),
                (des[:35] if len(des) > 35 else des).strip(),
                (des[:20] if len(des) > 20 else des).strip(),
            ]
            if len(words) >= 2:
                des_stems.append(" ".join(words[:2]))
            if len(words) >= 3:
                des_stems.append(" ".join(words[:3]))
            if len(words) >= 4:
                des_stems.append(" ".join(words[:4]))
            for des_candidate in des_stems:
                if not des_candidate or len(des_candidate) < 8:
                    continue
                pos = msg_upper.find(des_candidate.upper())
                if pos != -1:
                    best_pos = pos
                    qty = _parse_quantity_near(assistant_message, cod, des_candidate)
                    break
        if best_pos >= 0:
            seen_cod.add(cod)
            extracted_with_pos.append((cod, qty, best_pos))

    # Ordina per posizione nel messaggio (così le quantity vicine a ogni prodotto sono corrette)
    extracted_with_pos.sort(key=lambda x: x[2])
    extracted = [(c, q) for c, q, _ in extracted_with_pos]

    if not extracted:
        return current_items, current_order_confirmed

    current_len = len(current_items)
    # Usa l'estrazione solo per recuperare lista vuota (IA disse conferma ma dimenticò product_items).
    # Non sostituire mai quando l'IA ha già restituito almeno un item: evita di espandere 1→N quando
    # nel messaggio compaiono più varianti/nomi (es. "la prima" → 1 prodotto, ma des_art matcha 2 righe).
    use_extracted = current_len == 0 and user_intent_confirmation
    if use_extracted:
        # Non forzare order_confirmed=True se l'IA ha esplicitamente restituito False (es. sta
        # proponendo opzioni e il messaggio elenca prodotti; estraendo dal testo prenderemmo
        # tutti gli articoli elencati e confermeremmo per sbaglio).
        if not current_order_confirmed:
            return current_items, current_order_confirmed
        items = [ProductItem(cod_art=c, quantity=q) for c, q in extracted]
        logger.info(f"Coerenza output: output incoerente, inferiti product_items={[(it.cod_art, it.quantity) for it in items]}")
        return items, True
    return current_items, current_order_confirmed


def _parse_quantity_near(message: str, cod_art: str, des_art: str) -> float:
    """Cerca un numero vicino al riferimento al prodotto (es. '2 ACQUA BRACCA' -> 2, '2 ciascuno' -> 2)."""
    msg_upper = message.upper()
    # "2 ciascuno" / "entrambe 2 ciascuno" → quantity 2 per tutti
    ciascuno = re.search(r"(\d+)\s*ciascuno|ciascuno\s*(?:con)?\s*(\d+)", message, re.IGNORECASE)
    if ciascuno:
        n = int(ciascuno.group(1) or ciascuno.group(2) or 1)
        if n >= 1:
            return float(n)
    for needle in [cod_art, (des_art[:30] if des_art else ""), des_art]:
        if not needle:
            continue
        pos = msg_upper.find(needle.upper())
        if pos == -1:
            continue
        # Cifre nei ~30 caratteri prima della menzione
        segment = message[max(0, pos - 30) : pos]
        m = re.search(r"(\d+)\s*(?:bottiglie?|unità|pezzi|fusti|lattine?|×|x)?\s*$", segment, re.IGNORECASE)
        if m:
            return max(0.001, float(int(m.group(1))))
    return 1.0


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    try:
        logger.info(f"Nuova richiesta chat - Cliente: {request.client_id}, Messaggio: '{request.message}'")
        
        message_lower = request.message.lower().strip()
        usual_phrases = [
            "il solito", "come sempre", "quello di prima", "lo stesso", "come al solito",
            "come l'altra volta", "l'ultimo", "ultimo ordinato", "l'ultima volta"
        ]
        is_usual_request = any(phrase in message_lower for phrase in usual_phrases)
        
        if is_usual_request:
            order_history = db_service.get_order_history(request.client_id, limit=10)
            available_cod_art = set(db_service.get_available_cod_art_for_client(request.client_id))
            # Ultimo ordinato che sia ancora disponibile (in assortimento per il cliente)
            for item in order_history:
                if item.cod_art in available_cod_art:
                    logger.info(f"Richiesta 'il solito' - uso ultimo disponibile: {item.cod_art}")
                    return ChatResponse(
                        message=f"Come sempre, ho aggiunto {item.des_art or item.cod_art} al tuo ordine.",
                        product_codes=[item.cod_art],
                        product_items=[ProductItem(cod_art=item.cod_art, quantity=1)],
                        order_confirmed=True
                    )
            if order_history:
                logger.info("Richiesta 'il solito' ma nessun prodotto dello storico è disponibile ora")
                return ChatResponse(
                    message="Al momento non ho disponibile il prodotto che ordini di solito. Vuoi che ti proponga altre opzioni?",
                    product_codes=[],
                    order_confirmed=False
                )
            else:
                logger.info("Richiesta 'il solito' ma nessuno storico disponibile")
                return ChatResponse(
                    message="Non ho trovato ordini precedenti. Puoi specificare quale prodotto vuoi?",
                    product_codes=[],
                    order_confirmed=False
                )
        
        search_params = ai_service.extract_search_params(request.message)
        
        products = db_service.search_products(request.client_id, search_params)
        
        # Se l'utente conferma ("sì", "la prima", "prendo il secondo") la lista prodotti
        # è spesso vuota/keyword-less (CONFIRMATION) e restituisce i primi N per ordine alfabetico.
        # I prodotti proposti nel turno prima potrebbero non esserci → il backend li filtrava e
        # l'utente vedeva "Aggiungo X" ma product_items vuoto. Includiamo anche i prodotti
        # della ricerca fatta sull'ultimo messaggio utente (es. "vorrei un aperitivo").
        if search_params.intent == "CONFIRMATION" and request.history:
            last_user_content = None
            for m in reversed(request.history):
                if (getattr(m, "role", "") or "").lower() == "user":
                    last_user_content = getattr(m, "content", "") or ""
                    break
            if last_user_content and last_user_content.strip():
                params_prev = ai_service.extract_search_params(last_user_content.strip())
                products_prev = db_service.search_products(request.client_id, params_prev)
                seen = set(p.cod_art for p in products)
                for p in products_prev:
                    if p.cod_art not in seen:
                        seen.add(p.cod_art)
                        products.append(p)
                if products_prev:
                    logger.info(f"Conferma: inclusi {len(products_prev)} prodotti dalla ricerca sul messaggio precedente")
        
        order_history = db_service.get_order_history(request.client_id, limit=10)
        
        search_context = SearchContext(
            products=products,
            order_history=order_history,
            search_params=search_params
        )
        
        # Memoria: ultimi 10 messaggi per contesto (max 5 turni)
        history = None
        if request.history:
            history = [{"role": m.role, "content": m.content} for m in request.history[:10]]
        
        decision = ai_service.make_business_decision(
            request.message,
            search_context,
            history=history
        )
        
        intent = getattr(search_params, "intent", None)
        # Override: se l'utente ha chiesto una categoria/consiglio (ADVICE) o una scelta tra molti prodotti,
        # non aggiungere al carrello finché non conferma. Il modello spesso restituisce comunque product_items;
        # forziamo proposta per coerenza con i criteri.
        if intent == "ADVICE":
            if decision.product_items or decision.product_codes or decision.order_confirmed:
                logger.info("Intent ADVICE: forzati order_confirmed=False e product_items=[] (solo proposta)")
            raw_items = []
            order_confirmed = False
        else:
            raw_items = list(decision.product_items or [])
            if not raw_items and (decision.product_codes or []):
                raw_items = [ProductItem(cod_art=c, quantity=1) for c in decision.product_codes]
            order_confirmed = decision.order_confirmed

        # Coerenza messaggio ↔ output: se l'output è vuoto dopo una conferma utente o
        # il messaggio cita più prodotti di quelli restituiti, prova a inferire dal testo
        raw_items, order_confirmed = _ensure_message_output_coherence(
            decision.message or "",
            products,
            raw_items,
            order_confirmed,
            user_intent_confirmation=(getattr(search_params, "intent", None) == "CONFIRMATION"),
        )

        # Solo prodotti effettivamente passati all'IA (disponibili per il cliente) possono essere restituiti
        allowed_cod_art = {p.cod_art for p in products}
        filtered_items = [it for it in raw_items if it.cod_art in allowed_cod_art]
        if raw_items and not filtered_items:
            logger.warning(f"IA ha restituito cod_art non in lista disponibili, filtrati a []")
        order_confirmed = order_confirmed and len(filtered_items) > 0
        product_codes = [it.cod_art for it in filtered_items]

        logger.info(f"Risposta generata: message='{decision.message}', product_items={[(it.cod_art, it.quantity) for it in filtered_items]}, order_confirmed={order_confirmed}")

        return ChatResponse(
            message=decision.message,
            product_codes=product_codes,
            product_items=filtered_items,
            order_confirmed=order_confirmed
        )
        
    except ValueError as e:
        logger.error(f"Errore validazione: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"Errore endpoint chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Errore interno del server. Riprova tra un momento."
        )
