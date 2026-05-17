# config.py
import os
from dotenv import load_dotenv

load_dotenv()

def get_deepseek_key():
    """
    Obtiene la API Key de DeepSeek dinámicamente.
    Prioriza variable de entorno en memoria, luego recarga .env.
    """
    # Primero intentar desde variable de entorno en memoria
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and key.strip():
        return key.strip()
    
    # Si no está en memoria, recargar .env
    load_dotenv(override=True)
    key = os.getenv("DEEPSEEK_API_KEY")
    
    if not key or not key.strip():
        raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
    
    return key.strip()

# Para compatibilidad con código existente que espera DEEPSEEK_KEY como string
# Usamos una propiedad que se evalúa cada vez que se accede
class _ConfigModule:
    @property
    def DEEPSEEK_KEY(self):
        return get_deepseek_key()
    
    @property
    def MODELO(self):
        return "deepseek-v4-flash"
    
    @property
    def PROCESSED_DB(self):
        return "processed.db"
    
    @property
    def OFFERS_CSV(self):
        return "ofertas_empleo.csv"
    
    @property
    def AGENT_PROMPT_FILE(self):
        return "AGENT.md"
    
    @property
    def MAX_CHATS_PER_CYCLE(self):
        return 4
    
    @property
    def CACHE_SIZE(self):
        return 1000
    
    @property
    def BROWSER_RESTART_HOURS(self):
        return 6
    
    @property
    def HUMAN_TYPING_SPEED(self):
        return (0.02, 0.08)
    
    @property
    def HUMAN_READING_SPEED(self):
        return 40
    
    @property
    def HUMAN_IDLE_MOUSEMOVE(self):
        return False
    
    @property
    def HUMAN_IDLE_SCROLL(self):
        return True
    
    @property
    def GHOST_CHAT_PROBABILITY(self):
        return 0.05
    
    @property
    def HUMAN_MISTAKE_CLICK_PROBABILITY(self):
        return 0.01

# Reemplazar el módulo con la instancia dinámica
import sys
sys.modules[__name__] = _ConfigModule()