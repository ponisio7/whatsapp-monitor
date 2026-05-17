# ai.py
"""
Módulo de análisis de mensajes con IA (DeepSeek).
Responsabilidades:
- Cargar prompt del agente desde AGENT.md
- Cargar reglas de ignorado desde JSON
- Analizar si un mensaje es oferta de empleo
- Rate limiting para API calls
- Cache de resultados
"""
import asyncio
import json
import logging
import random
import re
from pathlib import Path
from collections import deque
import time
from typing import Tuple, Optional, Dict, Any

from openai import OpenAI
from config import DEEPSEEK_KEY, MODELO, AGENT_PROMPT_FILE


logger = logging.getLogger(__name__)


# ============================================================
# RATE LIMITING PARA OPENAI
# ============================================================

class RateLimiter:
    """Rate limiter simple para llamadas a API"""
    
    def __init__(self, calls_per_minute: int = 25):
        self.calls_per_minute = calls_per_minute
        self.calls = deque()
    
    async def acquire(self) -> None:
        """Espera si es necesario respetar el rate limit"""
        now = time.time()
        
        # Limpiar llamadas anteriores al último minuto
        while self.calls and self.calls[0] < now - 60:
            self.calls.popleft()
        
        if len(self.calls) >= self.calls_per_minute:
            wait_time = 60 - (now - self.calls[0])
            if wait_time > 0:
                logger.info(f"⏳ Rate limit OpenAI: esperando {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        
        self.calls.append(time.time())


_rate_limiter = RateLimiter(calls_per_minute=25)


# ============================================================
# CARGA DE PROMPT (DESDE AGENT.md)
# ============================================================

def cargar_prompt_agente() -> str:
    """Carga el prompt del agente desde AGENT.md"""
    try:
        with open(AGENT_PROMPT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        if content:
            logger.info(f"✅ Prompt del agente cargado desde {AGENT_PROMPT_FILE}")
            return content
            
    except FileNotFoundError:
        logger.warning(f"⚠️ No se encontró {AGENT_PROMPT_FILE}, usando prompt por defecto")
    
    # Prompt por defecto (solo si el archivo no existe)
    return """
    Eres un humano buscando trabajo. Analiza si este mensaje es una oferta de empleo.
    Responde SOLO en formato JSON: {"es_oferta": true/false, "titulo": "corto", "motivo": "explicacion"}
    """


# ============================================================
# CARGA DE REGLAS DE IGNORADO (DESDE JSON)
# ============================================================

_IGNORE_RULES_CACHE = None
_IGNORE_RULES_FILE = Path("ignore_rules.json")


def _get_default_rules() -> dict:
    """Devuelve reglas por defecto si no existe el archivo JSON"""
    return {
        "frases": [],
        "numeros": [],
        "remitentes": []    }


def cargar_reglas_ignorar() -> dict:
    """
    Carga reglas de exclusión desde ignore_rules.json
    
    Retorna dict con:
        - frases: list[str] - frases exactas a ignorar
        - numeros: list[str] - números de teléfono a ignorar
        - remitentes: list[str] - nombres de remitentes a ignorar
        
    """
    global _IGNORE_RULES_CACHE
    
    if _IGNORE_RULES_CACHE is not None:
        return _IGNORE_RULES_CACHE
    
    if not _IGNORE_RULES_FILE.exists():
        logger.warning(f"⚠️ No existe {_IGNORE_RULES_FILE}, creando archivo por defecto")
        _crear_archivo_reglas_por_defecto()
        return _get_default_rules()
    
    try:
        with open(_IGNORE_RULES_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
        
        # Validar estructura básica
        for key in ["frases", "numeros", "remitentes"]:
            if key not in rules:
                rules[key] = []
        
        # ✅ Correcto
        logger.info(f"📋 Reglas de ignorado cargadas: {len(rules['frases'])} frases, "
                    f"{len(rules['numeros'])} números, {len(rules['remitentes'])} remitentes")
                   
        
        _IGNORE_RULES_CACHE = rules
        return rules
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing {_IGNORE_RULES_FILE}: {e}")
        return _get_default_rules()
    except Exception as e:
        logger.error(f"❌ Error cargando reglas de ignorar: {e}")
        return _get_default_rules()


def _crear_archivo_reglas_por_defecto() -> None:
    """Crea un archivo ignore_rules.json por defecto"""
    default_rules = {
        "frases": [
            "empleo24h",
            "trabajo garantizado",
            "gana dinero desde casa",
            "inversión segura",
            "haz clic aquí"
        ],
        "numeros": [
            "644841253",
            "34644841253"
        ],
        "remitentes": [
            "empleo24h",
            "ofertas rapidas"
        ]
    }
    
    try:
        with open(_IGNORE_RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_rules, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Creado {_IGNORE_RULES_FILE} con reglas por defecto")
    except Exception as e:
        logger.error(f"❌ Error creando {_IGNORE_RULES_FILE}: {e}")


def mensaje_debe_ignorarse(texto: str, remitente: str = "", contacto_numero: str = "") -> Tuple[bool, str]:
    """
    Verifica si un mensaje debe ser ignorado según las reglas.
    
    Args:
        texto: Contenido del mensaje
        remitente: Nombre del remitente (si está disponible)
        contacto_numero: Número de teléfono del contacto
    
    Returns:
        (debe_ignorarse: bool, motivo: str)
    """
    rules = cargar_reglas_ignorar()
    texto_lower = texto.lower()
    remitente_lower = remitente.lower()
    numero_limpio = re.sub(r'\D', '', contacto_numero)
    
    # 1. Verificar remitentes bloqueados
    for rem in rules.get("remitentes", []):
        if rem.lower() in remitente_lower:
            return True, f"Remitente bloqueado: {rem}"
    
    # 2. Verificar números de teléfono
    for num in rules.get("numeros", []):
        # Limpiar el número de la regla también
        num_limpio = re.sub(r'\D', '', num)
        if num_limpio and (num_limpio in numero_limpio or num_limpio in texto_lower):
            return True, f"Número bloqueado: {num}"
    
    # 3. Verificar frases exactas en el texto
    for frase in rules.get("frases", []):
        if len(frase) >= 3 and frase.lower() in texto_lower:
            return True, f"Frase prohibida: {frase}"
    
    
    
    return False, ""


def recargar_reglas_ignorar() -> dict:
    """Forzar recarga de reglas desde el archivo JSON"""
    global _IGNORE_RULES_CACHE
    _IGNORE_RULES_CACHE = None
    return cargar_reglas_ignorar()


# ============================================================
# CLIENTE OPENAI (DEEPSEEK)
# ============================================================

AGENT_PROMPT = cargar_prompt_agente()
def get_ai_client():
    """Crea un cliente OpenAI con la API Key actual"""
    from config import DEEPSEEK_KEY
    return OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")

# Cache del cliente para evitar crear uno nuevo cada vez
_AI_CLIENT_CACHE = None

def _get_cached_ai_client():
    """Obtiene el cliente AI (con caché, pero verifica si la key cambió)"""
    global _AI_CLIENT_CACHE
    from config import DEEPSEEK_KEY
    
    # Si no hay cache o la key cambió, recrear cliente
    if _AI_CLIENT_CACHE is None:
        _AI_CLIENT_CACHE = get_ai_client()
    else:
        # Verificar si la key actual es diferente a la del cliente cacheado
        # Como no podemos acceder fácilmente a la key del cliente, recreamos periódicamente
        # o simplemente recreamos cada vez (es barato)
        pass
    
    return _AI_CLIENT_CACHE


# ============================================================
# ANÁLISIS PRINCIPAL
# ============================================================

async def analizar_oferta_empleo_humano(texto_mensaje: str, db) -> Tuple[bool, str, str]:
    """
    Analiza si un mensaje es una oferta de empleo relevante.
    
    Args:
        texto_mensaje: El texto del mensaje a analizar
        db: Instancia de Database para cache
    
    Returns:
        (es_oferta: bool, titulo: str, motivo: str)
    """
    # PRIMERO: Verificar si el mensaje debe ser ignorado
    ignorar, motivo_ignorar = mensaje_debe_ignorarse(texto_mensaje)
    if ignorar:
        logger.info(f"   🚫 Mensaje marcado para ignorar: {motivo_ignorar}")
        return (False, "", motivo_ignorar)
    
    # SEGUNDO: Verificar caché
    cached = await db.get_cached_analysis(texto_mensaje)
    if cached:
        is_offer, title, reason = cached
        logger.info(f"   💾 Usando análisis cacheado: {title if is_offer else 'no oferta'}")
        # Simular tiempo de lectura humano (sin errores artificiales)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        return is_offer, title, reason
    
    # TERCERO: Simular tiempo de lectura humano realista
    tiempo_lectura = random.uniform(0.5, 1.0)  # Reducido de 1.5-3.5 a 0.5-1.0
    logger.info(f"   🤔 Analizando mensaje ({tiempo_lectura:.1f}s)...")
    await asyncio.sleep(tiempo_lectura)
    
    try:
        # Rate limiting antes de llamar a OpenAI
        await _rate_limiter.acquire()
        
        # Obtener cliente actualizado
        client = get_ai_client()  # O usa _get_cached_ai_client() si prefieres

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODELO,
            messages=[
                {"role": "system", "content": AGENT_PROMPT},
                {"role": "user", "content": f"¿Esto es oferta de trabajo?\n\n{texto_mensaje[:1500]}"} #Subir truncado de 800 a 1500 caracteres en ai.py línea 295
            ],
            temperature=0.2,
            timeout=30
        )
        
        resultado_texto = response.choices[0].message.content.strip()
        logger.debug(f"   Respuesta IA (primeros 200 chars): {resultado_texto[:200]}")
        
        # Si la respuesta está vacía, usar fallback
        if not resultado_texto:
            logger.warning("   ⚠️ Respuesta vacía de la API")
            return _analisis_basico_oferta(texto_mensaje)
        
        # Extraer JSON (puede estar envuelto en markdown)
        json_str = _extraer_json_de_respuesta(resultado_texto)
        
        # Intentar parsear JSON
        try:
            resultado = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"   ⚠️ Error parseando JSON: {e}")
            logger.error(f"   String problemático: {json_str[:200]}")
            return _analisis_basico_oferta(texto_mensaje)
        
        # Validar y extraer campos
        es_oferta = resultado.get('es_oferta', False)
        titulo = resultado.get('titulo', 'Oferta')
        motivo = resultado.get('motivo', '')
        
        # Validar tipos
        if not isinstance(es_oferta, bool):
            es_oferta = False
        if not isinstance(titulo, str):
            titulo = str(titulo) if titulo else "Oferta"
        if not isinstance(motivo, str):
            motivo = str(motivo) if motivo else ""
        
        # Limitar longitud del título
        if len(titulo) > 60:
            titulo = titulo[:57] + "..."
        
        # Guardar en caché
        await db.cache_analysis(texto_mensaje, es_oferta, titulo, motivo)
        
        return (es_oferta, titulo, motivo)
        
    except asyncio.TimeoutError:
        logger.error("   ⚠️ Timeout en llamada a OpenAI")
        return _analisis_basico_oferta(texto_mensaje)
    except Exception as e:
        logger.error(f"   ⚠️ Error en análisis IA: {e}")
        return _analisis_basico_oferta(texto_mensaje)


def _extraer_json_de_respuesta(respuesta: str) -> str:
    """Extrae un objeto JSON de una respuesta que puede incluir markdown o texto adicional"""
    # Limpiar markdown
    if '```json' in respuesta:
        respuesta = respuesta.split('```json')[1].split('```')[0].strip()
    elif '```' in respuesta:
        respuesta = respuesta.split('```')[1].split('```')[0].strip()
    
    # Buscar el primer { y último } para extraer JSON válido
    start_idx = respuesta.find('{')
    end_idx = respuesta.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return respuesta[start_idx:end_idx + 1]
    
    return respuesta


# ============================================================
# ANÁLISIS FALLBACK (BASADO EN KEYWORDS)
# ============================================================

def _analisis_basico_oferta(texto: str) -> Tuple[bool, str, str]:
    """
    Análisis básico basado en keywords (fallback cuando la API falla).
    SIN errores artificiales.
    """
    if not texto:
        return (False, "", "Texto vacío")
    
    texto_lower = texto.lower()
    
    # Palabras clave positivas (sectores relevantes para Christian)
    palabras_clave = [
        'oferta', 'empleo', 'trabajo', 'vacante', 'remoto', 'salario',
        'contrato', 'jornada', 'empresa', 'incorporación', 'contratamos',
        'buscamos', 'seleccionamos', 'candidatos', 'ingeniero', 'petróleo',
        'logística', 'inventario', 'seguridad', 'datos', 'python', 'sql',
        'mantenimiento', 'limpieza', 'cuidador', 'atención al cliente'
    ]
    
    # Palabras clave negativas (spam)
    palabras_spam = [
        'premio', 'ganaste', 'sorteo', 'haz clic', 'registrate',
        'deposita', 'envía dinero', 'inversión segura', 'trabajo desde casa sin experiencia',
        'gana miles', 'ingresos extra', 'multinivel', 'esquema'
    ]
    
    encontradas_pos = [p for p in palabras_clave if p in texto_lower]
    encontradas_spam = [p for p in palabras_spam if p in texto_lower]
    
    # Si tiene palabras de spam, no es oferta
    if encontradas_spam:
        return (False, "", f"Spam detectado: {', '.join(encontradas_spam[:3])}")
    
    # Si tiene al menos 2 palabras clave de empleo, podría ser oferta
    if len(encontradas_pos) >= 2:
        return (True, "📢 Posible Oferta", f"Palabras detectadas: {', '.join(encontradas_pos[:3])}")
    
    # Si solo tiene 1 palabra clave, es dudoso
    if len(encontradas_pos) == 1:
        return (False, "", f"Solo una palabra clave: {encontradas_pos[0]}")
    
    return (False, "", "No se detectaron palabras clave relevantes")


# ============================================================
# FUNCIÓN DE UTILIDAD PARA VALIDAR REGLAS
# ============================================================

def validar_archivo_reglas() -> Dict[str, Any]:
    """
    Valida el archivo ignore_rules.json y reporta problemas.
    Útil para debugging.
    """
    if not _IGNORE_RULES_FILE.exists():
        return {"error": f"No existe {_IGNORE_RULES_FILE}"}
    
    try:
        with open(_IGNORE_RULES_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
        
        issues = []
        
        # Validar estructura
        if not isinstance(rules, dict):
            return {"error": "El archivo no contiene un objeto JSON válido"}
        
        # Validar cada sección
        for key in ["frases", "numeros", "remitentes"]:
            if key not in rules:
                issues.append(f"Falta la clave '{key}'")
            elif not isinstance(rules[key], list):
                issues.append(f"La clave '{key}' debe ser una lista")
        
                
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": {
                "frases": len(rules.get("frases", [])),
                "numeros": len(rules.get("numeros", [])),
                "remitentes": len(rules.get("remitentes", []))
            }
        }
        
    except json.JSONDecodeError as e:
        return {"error": f"JSON inválido: {e}"}
    except Exception as e:
        return {"error": str(e)}
    
# En ai.py, agregar:
def recargar_prompt_agente():
    global AGENT_PROMPT  # ← OBLIGATORIO
    AGENT_PROMPT = cargar_prompt_agente()
    logger.info("🔄 Prompt del agente recargado")