from fastapi import APIRouter, HTTPException
import logging

from models.schemas import ChatRequest, ChatResponse, SearchContext, BusinessDecisionResponse
from services.ai_service import AIService
from services.db_service import DatabaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

ai_service = AIService()
db_service = DatabaseService()


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
        
        # Solo prodotti effettivamente passati all'IA (disponibili per il cliente) possono essere restituiti
        allowed_cod_art = {p.cod_art for p in products}
        filtered_codes = [c for c in (decision.product_codes or []) if c in allowed_cod_art]
        if (decision.product_codes or []) and not filtered_codes:
            logger.warning(f"IA ha restituito cod_art non in lista disponibili: {decision.product_codes}, filtrati a []")
        order_confirmed = decision.order_confirmed and len(filtered_codes) > 0
        
        logger.info(f"Risposta generata: message='{decision.message}', product_codes={filtered_codes}, order_confirmed={order_confirmed}")
        
        return ChatResponse(
            message=decision.message,
            product_codes=filtered_codes,
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
