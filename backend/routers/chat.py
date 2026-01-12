from fastapi import APIRouter, HTTPException
import logging

from backend.models.schemas import ChatRequest, ChatResponse, SearchContext
from backend.services.ai_service import AIService
from backend.services.db_service import DatabaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

ai_service = AIService()
db_service = DatabaseService()


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    try:
        logger.info(f"Nuova richiesta chat - Cliente: {request.client_id}, Messaggio: '{request.message}'")
        
        search_params = ai_service.extract_search_params(request.message)
        
        products = db_service.search_products(request.client_id, search_params)
        order_history = db_service.get_order_history(request.client_id, limit=10)
        
        search_context = SearchContext(
            products=products,
            order_history=order_history,
            search_params=search_params
        )
        
        response_message = ai_service.make_business_decision(
            request.message,
            search_context
        )
        
        logger.info(f"Risposta generata: '{response_message}'")
        
        return ChatResponse(message=response_message)
        
    except ValueError as e:
        logger.error(f"Errore validazione: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"Errore endpoint chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Errore interno del server. Riprova tra un momento."
        )
