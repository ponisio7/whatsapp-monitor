# whatsapp.py
"""
Módulo de interacción con WhatsApp Web con simulación humana.
Responsabilidades:
- Obtener chats con mensajes no leídos
- Extraer mensajes del chat actual
- Navegación básica con movimientos humanos
"""
import asyncio
import logging
import re
import random
from typing import List, Dict, Any, Tuple

from playwright.async_api import Page

# Importar utilidades comunes y simuladores humanos
from utils import clean_chat_name, generate_message_hash
from mouse_simulator import MouseSimulator
from reading_simulator import ReadingSimulator

logger = logging.getLogger(__name__)


# ============================================================
# SELECTORES CSS (centralizados para fácil mantenimiento)
# ============================================================

class Selectors:
    """Selectores CSS para elementos de WhatsApp Web"""
    
    # Chats
    CHAT_ROW = 'div[role="row"]'
    CHAT_TITLE = 'span[title], span[dir="auto"]'
    UNREAD_BADGE = 'span[data-testid="icon-unread-count"], div[class*="unread"], span[class*="P2TO5"]'
    UNREAD_SPAN = 'span[aria-label*="no leído"], span[aria-label*="unread"]'
    
    # Panel de conversación
    CONVERSATION_PANEL = '[data-testid="conversation-panel-messages"]'
    MAIN_HEADER = '#main header'
    
    # Mensajes
    MESSAGE_IN = '.message-in, div[class*="message-in"]'
    MESSAGE_AUTHOR = 'span[data-testid="author"], span[class*="author"], span[class*="_author"]'
    COPYABLE_TEXT = '.copyable-text'
    SELECTABLE_TEXT = '.selectable-text span[dir="auto"]'
    MESSAGE_TEXT = 'div[class*="message-text"] span[dir="auto"]'
    TIME_SPAN = 'time, [data-testid="message-time"]'


# ============================================================
# FUNCIONES DE NAVEGACIÓN CON SIMULACIÓN HUMANA
# ============================================================

async def esperar_panel_conversacion(page: Page, timeout: int = 8000) -> bool:
    """Espera a que el panel de conversación esté visible"""
    try:
        await page.wait_for_selector(Selectors.CONVERSATION_PANEL, timeout=timeout)
        # Pausa humana después de detectar
        await asyncio.sleep(random.uniform(0.3, 0.7))
        return True
    except Exception:
        return False


async def cerrar_chat_actual(page: Page) -> None:
    """Cierra el chat actual con Escape (simulación humana)"""
    try:
        # Pausa antes de cerrar (como humano que termina de leer)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await page.keyboard.press("Escape")
        await asyncio.sleep(random.uniform(0.3, 0.6))
    except Exception as e:
        logger.debug(f"Error cerrando chat: {e}")


async def abrir_chat_por_nombre(page: Page, chat_name: str, max_intentos: int = 2) -> bool:
    """
    Abre un chat específico por nombre con movimientos humanos.
    
    Args:
        page: Página de Playwright
        chat_name: Nombre del chat a abrir
        max_intentos: Número máximo de intentos
    
    Returns:
        True si se abrió correctamente, False en caso contrario
    """
    clean_target = clean_chat_name(chat_name)
    
    # 1. Verificar si ya está abierto
    if await _is_chat_already_open(page, clean_target):
        logger.info(f"   ✅ Chat ya abierto: {chat_name}")
        return True
    
    # 2. Scroll humano en la lista de chats
    await _scroll_chat_list_humano(page)
    
    # 3. Buscar y hacer click con movimiento humano
    for intento in range(max_intentos):
        try:
            rows = await page.query_selector_all(Selectors.CHAT_ROW)
            logger.debug(f"   Buscando '{chat_name}' entre {len(rows)} chats...")
            
            for row in rows:
                title_span = await row.query_selector(Selectors.CHAT_TITLE)
                if not title_span:
                    continue
                
                row_name = await title_span.get_attribute('title')
                if not row_name:
                    row_name = await title_span.inner_text()
                
                if not row_name:
                    continue
                
                if clean_target in clean_chat_name(row_name):
                    logger.info(f"   🎯 Chat encontrado: '{row_name}'")
                    
                    # Scroll humano hacia el elemento
                    await row.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    
                    # Click con movimiento humano
                    if await _click_humano_en_elemento(page, row):
                        # Esperar que se abra con pausa humana
                        if await esperar_panel_conversacion(page, timeout=5000):
                            # Pausa de "satisfacción" después de abrir
                            await asyncio.sleep(random.uniform(0.5, 1.0))
                            logger.info(f"   ✅ Chat abierto: {chat_name}")
                            return True
                    
                    logger.warning(f"   Panel no detectado, reintentando...")
                    await asyncio.sleep(random.uniform(0.8, 1.2))
                    break  # Salir del bucle de rows, reintentar desde fuera
                    
        except Exception as e:
            logger.error(f"   Error en intento {intento + 1}: {e}")
            await asyncio.sleep(random.uniform(0.8, 1.5))
    
    logger.warning(f"   ❌ No se pudo abrir chat: {chat_name}")
    return False


async def _click_humano_en_elemento(page: Page, element) -> bool:
    """Click humano usando el simulador de ratón"""
    try:
        # Mover ratón al elemento con curva natural
        await MouseSimulator.move_to_element(page, element)
        
        # Pausa de "decisión" (como humano que duda antes de hacer click)
        await asyncio.sleep(random.uniform(0.08, 0.25))
        
        # Click real
        await element.click(force=True)
        
        # Registrar actividad
        await page.evaluate("window.lastClickTime = Date.now()")
        
        return True
    except Exception:
        # Fallback: click directo con JavaScript
        try:
            await element.evaluate("el => el.click()")
            return True
        except Exception:
            return False


async def _scroll_chat_list_humano(page: Page) -> None:
    """Simula scroll humano en la lista de chats"""
    try:
        # Scroll suave y aleatorio
        scroll_amount = random.randint(100, 300)
        await page.evaluate(f"""
            const chatList = document.querySelector('[data-testid="chat-list"], div[class*="chat-list"]');
            if (chatList) {{
                chatList.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }});
            }}
        """)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        
        # A veces scroll hacia arriba (humano revisando)
        if random.random() < 0.3:
            await page.evaluate(f"""
                const chatList = document.querySelector('[data-testid="chat-list"], div[class*="chat-list"]');
                if (chatList) {{
                    chatList.scrollBy({{ top: -{scroll_amount // 2}, behavior: 'smooth' }});
                }}
            """)
            await asyncio.sleep(random.uniform(0.2, 0.4))
    except Exception:
        pass


async def _is_chat_already_open(page: Page, clean_target: str) -> bool:
    """Verifica si el chat ya está abierto"""
    try:
        return await page.evaluate(f"""
            () => {{
                const header = document.querySelector('#main header');
                if (!header) return false;
                const title = header.innerText.toLowerCase();
                const target = '{clean_target}';
                return title.includes(target) || target.includes(title.split('\\n')[0].trim().toLowerCase());
            }}
        """)
    except Exception:
        return False


# ============================================================
# OBTENER CHATS CON MENSAJES NO LEÍDOS
# ============================================================

async def obtener_chats_no_leidos(page: Page) -> List[Dict[str, str]]:
    """
    Obtiene lista de chats que tienen mensajes no leídos.
    Con función de limpieza inline y pausas humanas.
    
    Returns:
        Lista de dicts con {id, name}
    """
    # Pausa antes de verificar (humano que mira la pantalla)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    
    try:
        chats = await page.evaluate(f"""
            () => {{
                function cleanName(name) {{
                    if (!name) return '';
                    return name.toLowerCase()
                        .replace(/["'.,!?¿¡]/g, '')
                        .replace(/\\s+/g, ' ')
                        .trim();
                }}
                
                const rows = Array.from(document.querySelectorAll('{Selectors.CHAT_ROW}'));
                const unreadChats = [];
                
                for (const row of rows) {{
                    let hasUnread = false;
                    
                    const badge = row.querySelector('{Selectors.UNREAD_BADGE}');
                    if (badge && badge.isConnected && badge.offsetParent !== null) {{
                        hasUnread = true;
                    }}
                    
                    if (!hasUnread) {{
                        const unreadSpans = row.querySelectorAll('{Selectors.UNREAD_SPAN}');
                        for (const span of unreadSpans) {{
                            if (span.isConnected && span.offsetParent !== null) {{
                                hasUnread = true;
                                break;
                            }}
                        }}
                    }}
                    
                    if (!hasUnread) {{
                        const messagePreview = row.querySelector('[class*="message"], [class*="preview"]');
                        if (messagePreview) {{
                            const styles = window.getComputedStyle(messagePreview);
                            if (styles.fontWeight === '700' || styles.fontWeight === 'bold') {{
                                hasUnread = true;
                            }}
                        }}
                    }}
                    
                    if (hasUnread) {{
                        const nameElement = row.querySelector('{Selectors.CHAT_TITLE}');
                        let name = 'Unknown';
                        if (nameElement) {{
                            name = nameElement.getAttribute('title') || nameElement.innerText;
                            name = cleanName(name);
                        }}
                        
                        const dataId = row.getAttribute('data-id');
                        const id = dataId || btoa(unescape(encodeURIComponent(name.substring(0, 50))));
                        
                        unreadChats.push({{ id, name }});
                    }}
                }}
                
                unreadChats.sort((a, b) => a.name.localeCompare(b.name));
                return unreadChats;
            }}
        """)
        
        if chats:
            logger.info(f"   🔵 {len(chats)} chats con no leídos")
            for chat in chats[:3]:
                logger.debug(f"      - {chat['name']}")
        
        return chats
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo chats: {e}")
        return []


# ============================================================
# OBTENER INFORMACIÓN DEL CONTACTO ACTUAL
# ============================================================

async def obtener_contacto_actual(page: Page) -> Dict[str, str]:
    """Obtiene nombre y número del contacto del chat actual"""
    try:
        return await page.evaluate(f"""
            () => {{
                const header = document.querySelector('{Selectors.MAIN_HEADER}');
                if (!header) return {{ nombre: 'Unknown', numero: '' }};
                
                const titleSpan = header.querySelector('{Selectors.CHAT_TITLE}');
                const nombre = titleSpan ? (titleSpan.getAttribute('title') || titleSpan.innerText) : 'Unknown';
                
                let numero = '';
                const allSpans = header.querySelectorAll('span');
                for (const span of allSpans) {{
                    const text = span.innerText;
                    if (text && /^[+\\d\\s()-]{{8,}}$/.test(text.replace(/\\s/g, ''))) {{
                        numero = text;
                        break;
                    }}
                }}
                
                return {{ nombre: nombre.trim(), numero: numero }};
            }}
        """)
    except Exception as e:
        logger.error(f"Error obteniendo contacto actual: {e}")
        return {"nombre": "Unknown", "numero": ""}


# ============================================================
# EXTRAER MENSAJES CON LECTURA SIMULADA
# ============================================================

async def obtener_mensajes_no_leidos(page: Page, max_mensajes: int = 7) -> List[Dict[str, Any]]:
    """
    Extrae mensajes del chat actual con simulación de lectura humana.
    """
    # Esperar que el panel de mensajes esté listo
    if not await esperar_panel_conversacion(page, timeout=5000):
        logger.warning("   ⚠️ Panel de mensajes no detectado")
        return []
    
    # Pausa humana antes de leer
    await asyncio.sleep(random.uniform(0.5, 1.2))
    
    # Scroll suave para ver todos los mensajes
    try:
        await page.evaluate("""
            const container = document.querySelector('[data-testid="conversation-panel-messages"]');
            if (container) {
                container.scrollTo({ top: 0, behavior: 'smooth' });
            }
        """)
        await asyncio.sleep(random.uniform(0.4, 0.8))
    except Exception:
        pass
    
    try:
        # Obtener información del contacto actual
        contacto = await obtener_contacto_actual(page)
        
        # Extraer mensajes
        mensajes = await page.evaluate(f"""
            () => {{
                const messages = [];
                const seenIds = new Set();
                const seenTexts = new Set();
                
                const messageElements = document.querySelectorAll('{Selectors.MESSAGE_IN}');
                
                if (messageElements.length === 0) {{
                    return [];
                }}
                
                for (const msg of messageElements) {{
                    if (msg.classList.contains('message-out') || msg.className.includes('message-out')) {{
                        continue;
                    }}
                    
                    let msgId = msg.getAttribute('data-id');
                    if (!msgId) {{
                        const timeSpan = msg.querySelector('{Selectors.TIME_SPAN}');
                        const timeText = timeSpan ? timeSpan.innerText : '';
                        msgId = btoa(unescape(encodeURIComponent(msg.innerText.substring(0, 100) + timeText)));
                    }}
                    
                    if (seenIds.has(msgId)) continue;
                    seenIds.add(msgId);
                    
                    let remitente = '';
                    const authorSpan = msg.querySelector('{Selectors.MESSAGE_AUTHOR}');
                    if (authorSpan) {{
                        remitente = authorSpan.innerText.trim();
                    }}
                    
                    let text = '';
                    
                    const messageTextDiv = msg.querySelector('div[class*="message-text"]');
                    if (messageTextDiv) {{
                        const spans = messageTextDiv.querySelectorAll('span[dir="auto"]');
                        for (const span of spans) {{
                            const spanText = span.innerText.trim();
                            const isTimestamp = /^\\d{{1,2}}:\\d{{2}}\\s*(a\\.?\\s*m\\.?|p\\.?\\s*m\\.?|AM|PM)?$/i.test(spanText);
                            if (spanText && !isTimestamp && spanText.length > 1) {{
                                text = spanText;
                                break;
                            }}
                        }}
                    }}
                    
                    if (!text) {{
                        const copyable = msg.querySelector('.copyable-text');
                        if (copyable) {{
                            const spans = copyable.querySelectorAll('span[dir="auto"]');
                            for (const span of spans) {{
                                const spanText = span.innerText.trim();
                                if (span.closest('[data-testid="author"], [class*="author"]')) continue;
                                const isTimestamp = /^\\d{{1,2}}:\\d{{2}}/.test(spanText);
                                if (spanText && !isTimestamp && spanText.length > 2) {{
                                    text = spanText;
                                    break;
                                }}
                            }}
                        }}
                    }}
                    
                    if (!text) {{
                        const selectable = msg.querySelector('{Selectors.SELECTABLE_TEXT}');
                        if (selectable) {{
                            const candidate = selectable.innerText.trim();
                            const isTimestamp = /^\\d{{1,2}}:\\d{{2}}/.test(candidate);
                            if (candidate && !isTimestamp && candidate.length > 2) {{
                                text = candidate;
                            }}
                        }}
                    }}
                    
                    if (!text) {{
                        let raw = msg.innerText.trim();
                        raw = raw.replace(/\\d{{1,2}}:\\d{{2}}\\s*(a\\.?\\s*m\\.?|p\\.?\\s*m\\.?|AM|PM)?/gi, '');
                        raw = raw.replace(/[✔✓]{{1,2}}/g, '');
                        if (remitente && raw.startsWith(remitente)) {{
                            raw = raw.slice(remitente.length);
                        }}
                        text = raw.trim();
                    }}
                    
                    if (!text || text.length < 2) continue;
                    if (remitente && text === remitente) continue;
                    
                    const textKey = text.substring(0, 200);
                    if (seenTexts.has(textKey)) continue;
                    seenTexts.add(textKey);
                    
                    const timeSpan = msg.querySelector('{Selectors.TIME_SPAN}');
                    let timestamp = Date.now();
                    if (timeSpan && timeSpan.getAttribute('datetime')) {{
                        const parsed = new Date(timeSpan.getAttribute('datetime'));
                        if (!isNaN(parsed.getTime())) {{
                            timestamp = parsed.getTime();
                        }}
                    }}
                    
                    messages.push({{
                        id: msgId,
                        text: text,
                        remitente: remitente,
                        timestamp: timestamp,
                        raw_timestamp: timeSpan ? timeSpan.innerText : ''
                    }});
                }}
                
                messages.reverse();
                return messages.slice(0, {max_mensajes});
            }}
        """)
        
        # Enriquecer con información del contacto
        for msg in mensajes:
            msg['contacto_nombre'] = contacto.get('nombre', 'Unknown')
            msg['contacto_numero'] = contacto.get('numero', '')
            msg['hash'] = generate_message_hash(
                msg_id=msg.get('id', ''),
                text=msg.get('text', ''),
                remitente=msg.get('remitente', ''),
                timestamp=msg.get('timestamp', 0)
            )
        
        if mensajes:
            logger.info(f"   📨 Extraídos {len(mensajes)} mensajes")
            
            # SIMULACIÓN DE LECTURA HUMANA
            logger.info(f"   👁️ Simulando lectura humana...")
            await ReadingSimulator.simulate_reading(mensajes)
            
            for i, msg in enumerate(mensajes[:5]):
                remitente_info = f"[{msg['remitente']}] " if msg.get('remitente') else ""
                logger.debug(f"      {i+1}: {remitente_info}{msg['text'][:60]}...")
        
        return mensajes
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo mensajes: {e}")
        return []


# ============================================================
# FUNCIONES ALIAS PARA COMPATIBILIDAD CON main.py
# ============================================================

async def obtener_todos_los_chats_optimizado(page: Page) -> List[Dict[str, str]]:
    """Alias para obtener_chats_no_leidos"""
    return await obtener_chats_no_leidos(page)


async def obtener_mensajes_no_leidos_optimizado(page: Page) -> List[Dict[str, Any]]:
    """Alias para obtener_mensajes_no_leidos"""
    return await obtener_mensajes_no_leidos(page)

# Añadir al final del archivo

async def obtener_mensajes_con_imagenes(page: Page, max_mensajes: int = 10) -> List[Dict[str, Any]]:
    """
    Obtiene mensajes que contienen imágenes para procesar con OCR.
    """
    try:
        mensajes = await page.evaluate(f"""
            () => {{
                const messages = [];
                const messageElements = document.querySelectorAll('.message-in');
                
                for (const msg of messageElements) {{
                    const hasImage = msg.querySelector('img[src*="blob"], [data-testid="image"]') !== null;
                    
                    if (hasImage) {{
                        let remitente = '';
                        const authorSpan = msg.querySelector('span[data-testid="author"], span[class*="author"]');
                        if (authorSpan) {{
                            remitente = authorSpan.innerText.trim();
                        }}
                        
                        const timeSpan = msg.querySelector('time');
                        
                        messages.push({{
                            id: msg.getAttribute('data-id') || Date.now().toString(),
                            remitente: remitente,
                            has_image: true,
                            timestamp: timeSpan ? timeSpan.getAttribute('datetime') : Date.now()
                        }});
                    }}
                }}
                
                return messages.slice(-{max_mensajes});
            }}
        """)
        
        return mensajes
        
    except Exception as e:
        logger.error(f"Error obteniendo mensajes con imágenes: {e}")
        return []