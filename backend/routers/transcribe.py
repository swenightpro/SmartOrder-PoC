import io
import logging
from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcribe", tags=["transcribe"])
client = OpenAI(api_key=settings.openai_api_key)

# Whisper accetta: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm
MAX_FILE_SIZE_MB = 25


@router.post("")
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    """Riceve un file audio, lo trascrive con OpenAI Whisper, restituisce { \"text\": \"...\" }."""
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail="È richiesto un file audio (es. audio/webm, audio/mp4, audio/mpeg)."
        )
    try:
        data = await file.read()
    except Exception as e:
        logger.error(f"Lettura file audio fallita: {e}")
        raise HTTPException(status_code=400, detail="Impossibile leggere il file audio.")
    if not data or len(data) == 0:
        raise HTTPException(status_code=400, detail="File audio vuoto.")
    if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File troppo grande (max {MAX_FILE_SIZE_MB} MB)."
        )
    try:
        # Whisper accetta file-like; usiamo BytesIO. Nome file utile per tipo (webm/mp4 ecc.)
        name = file.filename or "audio.webm"
        if not "." in name:
            name = "audio.webm"
        file_like = io.BytesIO(data)
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=(name, file_like, file.content_type or "audio/webm"),
        )
        text = (transcription.text or "").strip()
        logger.info(f"Trascrizione completata, lunghezza testo: {len(text)}")
        return {"text": text}
    except Exception as e:
        logger.error(f"Errore Whisper: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Trascrizione non disponibile. Verifica il formato audio (es. webm/mp4) e riprova."
        )
