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
        usual_phrases = ["il solito", "come sempre", "quello di prima", "lo stesso", "come al solito"]
        is_usual_request = any(phrase in message_lower for phrase in usual_phrases)
        
        if is_usual_request:
            order_history = db_service.get_order_history(request.client_id, limit=1)
            if order_history:
                most_recent = order_history[0]
                logger.info(f"Richiesta 'il solito' - uso prodotto più recente: {most_recent.cod_art}")
                return ChatResponse(
                    message=f"Come sempre, ho aggiunto {most_recent.des_art or most_recent.cod_art} al tuo ordine.",
                    product_codes=[most_recent.cod_art],
                    order_confirmed=True
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
        
        logger.info(f"Risposta generata: message='{decision.message}', product_codes={decision.product_codes}, order_confirmed={decision.order_confirmed}")
        
        return ChatResponse(
            message=decision.message,
            product_codes=decision.product_codes,
            order_confirmed=decision.order_confirmed
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
