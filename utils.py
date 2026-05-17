# utils.py
import re
import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def clean_chat_name(name: str) -> str:
    """Limpia caracteres problemáticos del nombre del chat (versión única y consistente)"""
    if not name:
        return ""
    cleaned = re.sub(r'["\'.,!?¿¡]', '', name)
    cleaned = ' '.join(cleaned.split())
    return cleaned.strip().lower()


def get_clean_chat_name_js() -> str:
    """Devuelve la función JS equivalente para limpiar nombres (consistente con Python)"""
    return """
    function cleanChatName(name) {
        if (!name) return '';
        return name.toLowerCase()
            .replace(/["'.,!?¿¡]/g, '')
            .replace(/\\s+/g, ' ')
            .trim();
    }
    """


def generate_message_hash(msg_id: str, text: str, remitente: str, timestamp: int) -> str:
    """
    Genera un hash único y robusto para un mensaje.
    Prioriza el ID real de WhatsApp si existe.
    """
    if msg_id and len(msg_id) > 5:
        # Si tenemos ID real de WhatsApp, lo usamos como base
        content = f"{msg_id}_{remitente}"
    else:
        # Fallback: combinación de texto completo + remitente + timestamp
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
        content = f"{text_hash}_{remitente}_{timestamp}"
    
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:32]