#!/usr/bin/env python3
"""
Job Monitor WhatsApp v13 - Modo Híbrido con Anti-Detección Avanzada
Versión: Stealth mejorado + Comportamiento humano + Vigilancia visual
"""
import asyncio
import random
import platform
import subprocess
import shutil
import logging
import sys
import math
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any
from ocr_module import OCRProcessor, extract_text_from_all_images_in_chat

# Configurar logging simplificado (menos ruido)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Intentar usar uvloop para mejor rendimiento
#try:
#    import uvloop
#    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
#    logger.info("✅ Usando uvloop para mejor rendimiento")
#except ImportError:
#    pass

from playwright.async_api import async_playwright, Page, BrowserContext

from config import BROWSER_RESTART_HOURS
from storage import Database, save_offer_to_csv
from ai import analizar_oferta_empleo_humano, mensaje_debe_ignorarse, recargar_reglas_ignorar,recargar_prompt_agente, validar_archivo_reglas
from whatsapp import (
    obtener_todos_los_chats_optimizado,
    obtener_mensajes_no_leidos_optimizado,
    abrir_chat_por_nombre,
    cerrar_chat_actual
)
from utils import clean_chat_name
from mouse_simulator import MouseSimulator
from stealth_setup import setup_stealth_browser
from sentinel_mode import SentinelMode
from human_idle_behavior import HumanIdleBehavior
from typing_simulator import HumanTyper
from reading_simulator import ReadingSimulator


# ============================================================
# CONSTANTES OPTIMIZADAS
# ============================================================

class MonitorState(Enum):
    """Estados del monitor híbrido"""
    TRADITIONAL = "tradicional"    # Polling activo
    SENTINEL = "sentinel"          # Vigilancia pasiva visual

class CycleResult(Enum):
    CONTINUE = 0
    RESTART = 1
    FATAL_ERROR = 2

# Configuración de tiempos humanizados - VERSIÓN RÁPIDA
CYCLE_TIMEOUT_SECONDS = 150  # Aumentado de 90 a 150 segundos
MAX_CHATS_PER_CYCLE = 2       # Reducido de 4 a 2 (más seguro)
CHAT_OPEN_TIMEOUT = 10               # Reducido de 15
MESSAGES_TIMEOUT = 12                # Reducido de 20
HEALTH_CHECK_INTERVAL = 300
MAX_CONSECUTIVE_ERRORS = 5

# Pausas humanas - MÁS CORTAS
NORMAL_PAUSE_MIN = 3                 # Reducido de 8
NORMAL_PAUSE_MAX = 8                 # Reducido de 18
HUMAN_BROWSING_PROBABILITY = 0.14    # Reducido de 0.25
HUMAN_SCROLL_PROBABILITY = 0.25      # Reducido de 0.30

STATS_CYCLE_INTERVAL = 10
RELOAD_RULES_INTERVAL = 50

# Configuración centinela
SENTINEL_POST_PROCESS_PAUSE = (3, 6)  # Pausa más humana después de procesar


# ============================================================
# CLASE PRINCIPAL REFACTORIZADA
# ============================================================

class JobMonitor:
    """Monitor de ofertas de empleo en WhatsApp Web - Modo Híbrido con Anti-Detección"""
    
    def __init__(self):
        self.db: Optional[Database] = None
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # ===== AGREGAR ESTA LÍNEA =====
        self.signals = None  # Para compatibilidad con GUI
        
        # Estado
        self.start_time = datetime.now()
        self.messages_processed_today = 0
        self.spam_filtered_today = 0
        self.restart_count = 0
        self.cycle_count = 0
        self.consecutive_errors = 0
        
        # Health check
        self.last_health_check = datetime.now()
        
        # Modo híbrido
        self.monitor_state: MonitorState = MonitorState.TRADITIONAL
        self.sentinel: Optional[SentinelMode] = None
        self._in_transition = False
        self._last_sentinel_activation = None
        
        # Estadísticas de comportamiento humano
        self.human_actions_today = 0
        self.last_human_action = datetime.now()
        
        # Cache de chats conocidos para interacciones fantasma
        self.known_chats_cache: List[Dict] = []
        self.cache_last_update = None

        # Añadir OCR
        self.ocr_integration: Optional[OCRProcessor] = None
        self.ocr_enabled = True  # Puede desactivarse si da problemas
    
    # ============================================================
    # INICIALIZACIÓN
    # ============================================================
    
    async def init(self) -> None:
        """Inicializa el monitor"""
        self.db = Database()
        await self.db.init()
        
        logger.info("=" * 60)
        logger.info("🚀 Job Monitor WhatsApp v13 - Anti-Detección Avanzada")
        logger.info(f"📅 Iniciado: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("🛡️ Stealth: Emulación profunda de navegador")
        logger.info("👤 Comportamiento: Movimientos y tiempos humanos")
        logger.info("👁️ Vigilancia: Modo centinela visual")
        logger.info("=" * 60)
        
        # Validar reglas
        validation = validar_archivo_reglas()
        if validation.get("valid"):
            stats = validation.get("stats", {})
            logger.info(f"📋 Reglas: {stats.get('frases', 0)} frases, "
                       f"{stats.get('numeros', 0)} números, "
                       f"{stats.get('remitentes', 0)} remitentes")
        else:
            logger.warning(f"⚠️ Problemas con reglas: {validation.get('issues', [])}")

    async def _idle_mouse_while_sentinel(self):
        """
        Ejecuta micro-movimientos nativos durante el modo centinela.
        CRÍTICO: Usa page.mouse.move() -> isTrusted = TRUE
        """
        # No iniciar si no hay centinela activo
        while self.monitor_state == MonitorState.SENTINEL and self.sentinel:
            try:
                # Esperar entre 25-50 segundos (variable, como humano)
                await asyncio.sleep(random.uniform(25, 50))
                
                # Verificar que seguimos en modo centinela
                if self.monitor_state != MonitorState.SENTINEL:
                    break
                
                # Decidir intensidad (mayoría low, ocasional medium, raro high)
                intensity = random.choices(
                    ["low", "medium", "high"],
                    weights=[0.75, 0.20, 0.05]
                )[0]
                
                # Ejecutar micro-movimiento nativo
                new_x, new_y = await MouseSimulator.micro_movimiento_idle(
                    self.page, 
                    intensity=intensity
                )
                
                logger.debug(f"🖱️ Micro-movimiento centinela ({intensity}): ({new_x:.0f}, {new_y:.0f})")
                
                # Ocasionalmente, después del movimiento, pausa extra (como humano que mira)
                if random.random() < 0.3:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
            except asyncio.CancelledError:
                logger.debug("🖱️ Task de micro-movimientos cancelado")
                break
            except Exception as e:
                logger.debug(f"⚠️ Error en micro-movimiento centinela: {e}")
                await asyncio.sleep(random.uniform(10, 20))  # Pausa más larga si hay error
    
    async def close(self) -> None:
        """Limpia recursos"""
        logger.info("\n📊 ESTADÍSTICAS FINALES:")
        logger.info(f"   Mensajes procesados: {self.messages_processed_today}")
        logger.info(f"   Spam filtrado: {self.spam_filtered_today}")
        logger.info(f"   Ciclos completados: {self.cycle_count}")
        logger.info(f"   Reinicios: {self.restart_count}")
        logger.info(f"   Acciones humanas: {self.human_actions_today}")
        
        if self.sentinel:
            stats = self.sentinel.get_stats()
            logger.info(f"   Detecciones centinela: {stats.get('real_detections', 0)}")
        
        if self.db:
            await self.db.close()
        
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        
        if self.playwright:
            await self.playwright.stop()
    
    # ============================================================
    # NAVEGADOR CON STEALTH MEJORADO
    # ============================================================
    
    async def setup_browser(self, playwright) -> Page:
        """Configura el navegador con anti-detección avanzada"""
        logger.info("🌐 Iniciando navegador con stealth mejorado...")
        
        user_data_dir = Path("./session_wa_jobs")
        user_data_dir.mkdir(exist_ok=True)
        
        # Configuración de viewport aleatorio (como humano)
        viewport_width = random.choice([1366, 1440, 1536, 1600, 1920])
        viewport_height = random.choice([768, 900, 864, 1080])
        
        self.context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-infobars",
                f"--window-size={viewport_width},{viewport_height}",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-web-security",  # Necesario para algunas operaciones
                "--disable-features=BlockInsecurePrivateNetworkRequests",
            ],
            viewport={"width": viewport_width, "height": viewport_height},
            user_agent=self._get_random_user_agent(),
            locale="es-ES",
            timezone_id="Europe/Madrid",
            permissions=["notifications", "clipboard-read", "clipboard-write"],
            color_scheme="light" if random.random() < 0.7 else "dark",
        )
        
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # Aplicar stealth avanzado
        await setup_stealth_browser(self.context, self.page)
        
        logger.info(f"✅ Anti-detección avanzada activada (viewport: {viewport_width}x{viewport_height})")
        logger.info("🌐 Cargando WhatsApp Web...")
        
        await self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)

        # Inicializar OCR después de tener page
        if self.ocr_enabled:
            self.ocr_integration = OCRProcessor()  # No necesita page
            ocr_stats = self.ocr_integration.get_stats()
            logger.info(f"🔍 OCR inicializado: Paddle={ocr_stats['paddle_available']}, Tesseract={ocr_stats['tesseract_available']}")

        return self.page
    
    async def _mensaje_tiene_imagen(self, msg: dict) -> bool:
        """Verifica si un mensaje contiene una imagen"""
        # Esto requeriría acceso al DOM del mensaje
        # Por ahora, asumimos que los mensajes sin texto largo pueden tener imagen
        return len(msg.get('text', '')) < 10 and msg.get('remitente') != ''
    
    def _get_random_user_agent(self) -> str:
        """Retorna un User Agent realista y actual"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)
    
    # En main.py, modificar el método esperar_whatsapp_listo
    async def esperar_whatsapp_listo(self) -> bool:
        """Espera a que WhatsApp Web esté cargado con paciencia humana"""
        logger.info("🔄 Esperando WhatsApp Web...")
        
        # Pausa inicial como humano que espera
        await asyncio.sleep(random.uniform(1.5, 3.0))
        
        # Verificar QR - MOSTRAR MENSAJE CLARO EN GUI
        try:
            qr = await self.page.query_selector('canvas[aria-label="Scan me!"], div[data-ref="qrcode"]')
            if qr:
                logger.info("📱 QR detectado - Escanea con tu teléfono")
                # Enviar señal a GUI
                self.signals.log_message.emit("📱 QR DETECTADO - Escanea el código con tu teléfono", "WARNING")
                
                try:
                    await self.page.wait_for_selector(
                        'canvas[aria-label="Scan me!"]',
                        state="detached",
                        timeout=120000
                    )
                    logger.info("✅ QR escaneado correctamente")
                    self.signals.log_message.emit("✅ QR escaneado correctamente", "SUCCESS")
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    logger.error(f"❌ Timeout esperando QR: {e}")
                    return False
        except Exception as e:
            logger.debug(f"Error verificando QR: {e}")
        
        # Esperar selectores de WhatsApp con paciencia
        selectores = [
            'div[role="row"]',
            '[data-testid="chat-list"]',
            'div[contenteditable="true"]',
            '#pane-side',  # Agregar este selector
            'div[class*="chat-list"]'  # Agregar este selector
        ]
        
        for selector in selectores:
            try:
                await self.page.wait_for_selector(selector, timeout=15000)
                logger.info(f"✅ WhatsApp Web listo (selector: {selector})")
                self.signals.log_message.emit("✅ WhatsApp Web listo", "SUCCESS")
                # Pausa humana adicional
                await asyncio.sleep(random.uniform(1.5, 3.0))
                return True
            except Exception as e:
                logger.debug(f"Selector {selector} no encontrado: {e}")
                continue
        
        logger.error("❌ No se detectó WhatsApp Web")
        self.signals.log_message.emit("❌ No se detectó WhatsApp Web - Revisa la ventana del navegador", "ERROR")
        return False
    
    async def restart_browser(self) -> None:
        """Reinicia el navegador con pausa humana"""
        logger.info("🔄 Reiniciando navegador (como humano que refresca)...")
        
        # Pausa antes de cerrar (humano decide reiniciar)
        await asyncio.sleep(random.uniform(2.0, 4.0))
        
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        
        await asyncio.sleep(random.uniform(3.0, 6.0))  # Pausa más larga
        await self.setup_browser(self.playwright)
        
        if not await self.esperar_whatsapp_listo():
            logger.error("❌ No se pudo reiniciar WhatsApp")
        
        self.last_health_check = datetime.now()
        self.consecutive_errors = 0
        self.monitor_state = MonitorState.TRADITIONAL
    
    # ============================================================
    # COMPORTAMIENTO HUMANO
    # ============================================================
    
    async def _perform_human_behavior(self) -> None:
        """Ejecuta comportamientos humanos aleatorios durante inactividad"""
        # Limitar frecuencia de acciones humanas
        if (datetime.now() - self.last_human_action).total_seconds() < 30:
            return
        
        self.last_human_action = datetime.now()
        behavior_type = random.random()
        
        if behavior_type < HUMAN_BROWSING_PROBABILITY:
            await self._human_browsing_behavior()
            self.human_actions_today += 1
        elif behavior_type < HUMAN_BROWSING_PROBABILITY + HUMAN_SCROLL_PROBABILITY:
            await self._human_scroll_behavior()
            self.human_actions_today += 1
    
    async def _human_browsing_behavior(self) -> None:
        """Comportamiento de navegación humana (mirar alrededor)"""
        logger.debug("👤 Comportamiento humano: explorando interfaz")
        
        try:
            # Scroll suave por la lista de chats
            await self.page.evaluate("""
                const chatList = document.querySelector('#pane-side');
                if (chatList) {
                    const scrollAmount = 200 + Math.random() * 300;
                    chatList.scrollBy({ top: scrollAmount, behavior: 'smooth' });
                    setTimeout(() => {
                        chatList.scrollBy({ top: -scrollAmount/2, behavior: 'smooth' });
                    }, 800 + Math.random() * 1000);
                }
            """)
            await asyncio.sleep(random.uniform(1.5, 3.0))
            
            # Mover mouse aleatoriamente
            if random.random() < 0.5:
                x = random.randint(100, 1000)
                y = random.randint(100, 600)
                await self.page.mouse.move(x, y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
        except Exception as e:
            logger.debug(f"Error en comportamiento humano: {e}")
    
    async def _human_scroll_behavior(self) -> None:
        """Scroll aleatorio como humano distraído"""
        logger.debug("👤 Scroll humano aleatorio")
        
        try:
            scroll_amount = random.randint(-300, 500)
            await self.page.evaluate(f"window.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # A veces scroll de vuelta
            if random.random() < 0.4:
                await asyncio.sleep(random.uniform(0.8, 1.5))
                await self.page.evaluate(f"window.scrollBy({{ top: {-scroll_amount // 2}, behavior: 'smooth' }})")
                
        except Exception as e:
            logger.debug(f"Error en scroll humano: {e}")
    
    async def _open_chat_with_human_mouse(self, chat_name: str) -> bool:
        """Abrir chat usando movimientos de ratón humanos"""
        try:
            # Buscar el elemento del chat
            chat_selector = f'div[title="{chat_name}"], span[title="{chat_name}"]'
            elemento = await self.page.query_selector(chat_selector)
            
            if not elemento:
                return await abrir_chat_por_nombre(self.page, chat_name)
            
            # Usar MouseSimulator mejorado
            if hasattr(MouseSimulator, 'click_humano_mejorado'):
                success = await MouseSimulator.click_humano_mejorado(self.page, chat_selector)
            else:
                success = await MouseSimulator.click_humano(self.page, chat_selector)
            
            if success:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                return True
            
            return await abrir_chat_por_nombre(self.page, chat_name)
            
        except Exception as e:
            logger.debug(f"Error en click humano: {e}")
            return await abrir_chat_por_nombre(self.page, chat_name)
    
    async def _anti_freeze_check(self) -> bool:
        """Verifica que la página no esté congelada"""
        try:
            await asyncio.wait_for(
                self.page.evaluate("document.readyState"),
                timeout=2.0
            )
            
            title = await asyncio.wait_for(
                self.page.evaluate("document.title"),
                timeout=1.0
            )
            
            if "WhatsApp" not in title:
                logger.warning("⚠️ Página cargada pero no es WhatsApp")
                return False
                
            return True
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ Posible congelamiento detectado")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Error en anti-freeze check: {e}")
            return False
    
    async def _marcar_como_leido_seguro(self) -> None:
        """Marca mensajes como leídos de forma no bloqueante"""
        try:
            await asyncio.wait_for(self._marcar_como_leido(), timeout=2.0)
        except Exception:
            pass  # Ignorar fallos
    
    async def _marcar_como_leido(self) -> None:
        """Marca mensajes como leídos con timing humano"""
        try:
            # Pausa antes de marcar (como humano que lee)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Scroll suave al último mensaje
            await self.page.evaluate("""
                () => {
                    const lastMsg = document.querySelector('div[class*="message-in"]:last-child');
                    if (lastMsg) {
                        lastMsg.scrollIntoView({behavior: 'smooth', block: 'center'});
                    }
                }
            """)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Click para marcar como leído
            chat_list_selectors = [
                'div[data-testid="chat-list"]',
                'div[role="list"]',
            ]
            
            for selector in chat_list_selectors:
                try:
                    await self.page.click(selector, timeout=1500, force=True, no_wait_after=True)
                    break
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"⚠️ No se pudo marcar como leído: {e}")
    
    # ============================================================
    # PROCESAMIENTO DE MENSAJES
    # ============================================================
    
    async def procesar_mensaje(self, msg: dict, chat_name: str) -> bool:
        """Procesa un mensaje individual con soporte OCR para imágenes"""
        msg_text = msg.get('text', '')
        msg_remitente = msg.get('remitente', '')
        msg_hash = msg.get('hash', '')
        has_image = msg.get('has_image', False)
        
        # Si el mensaje no tiene texto pero tiene imagen, intentar OCR
        if (not msg_text or len(msg_text.strip()) < 5) and (has_image or msg.get('needs_ocr', False)):
            logger.info(f"   🔍 Mensaje sin texto, intentando OCR...")
            
            if hasattr(self, 'ocr_integration') and self.ocr_integration:
                try:
                    # Usar la función extract_text_from_all_images_in_chat
                    ocr_offers = await extract_text_from_all_images_in_chat(self.page, timeout=3.0)
                    
                    for offer in ocr_offers:
                        if offer.get('is_job_offer', False):
                            text = offer.get('text', '')
                            confidence = offer.get('confidence', 0)
                            logger.info(f"   🎯 OCR detectó oferta (confianza: {confidence:.2f}): {text[:100]}")
                            
                            # Guardar como oferta
                            from storage import save_offer_to_csv
                            await save_offer_to_csv(
                                f"📷 OFERTA OCR", 
                                text, 
                                chat_name, 
                                f"OCR detection (conf: {confidence:.2f})", 
                                msg_remitente, 
                                msg.get('contacto_numero', '')
                            )
                            await self.db.increment_stat("offers_found")
                            
                            # Enviar alerta
                            asyncio.create_task(self._enviar_alerta(
                                text, 
                                "📷 OFERTA OCR", 
                                chat_name, 
                                "Detectada por OCR"
                            ))
                            
                            # Marcar mensaje como procesado
                            if msg_hash:
                                await self.db.mark_message_processed(
                                    msg_hash, text, msg_remitente, chat_name, 
                                    msg.get('contacto_numero', ''), False, True
                                )
                            
                            self.messages_processed_today += 1
                            return True
                            
                except Exception as e:
                    logger.error(f"   ❌ Error en OCR: {e}")
            
            # Si no hay texto después de OCR, marcar como procesado sin oferta
            if msg_hash:
                await self.db.mark_message_processed(
                    msg_hash, "", msg_remitente, chat_name, 
                    msg.get('contacto_numero', ''), True, True
                )
            return True
        
        # Si no hay texto válido después de todo, ignorar
        if not msg_text or len(msg_text.strip()) < 2:
            if msg_hash:
                await self.db.mark_message_processed(
                    msg_hash, "", msg_remitente, chat_name, 
                    msg.get('contacto_numero', ''), True, True
                )
            return True
        
        logger.info(f"   📝 {msg_text[:60]}...")
        
        # Pausa antes de decidir (como humano que lee)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Verificar duplicado
        if msg_hash and await self.db.is_message_processed(msg_hash):
            logger.info("   ⏭️ Ya procesado")
            return False
        
        # Filtro spam
        ignorar, motivo = mensaje_debe_ignorarse(msg_text, msg_remitente, msg.get('contacto_numero', ''))
        if ignorar:
            logger.info(f"   🚫 SPAM: {motivo}")
            self.spam_filtered_today += 1
            if msg_hash:
                await self.db.mark_message_processed(
                    msg_hash, msg_text, msg_remitente, chat_name, 
                    msg.get('contacto_numero', ''), True, True
                )
            self.messages_processed_today += 1
            asyncio.create_task(self._marcar_como_leido_seguro())
            return True
        
        # Análisis IA con timeout
        logger.info("   🤖 Analizando...")
        try:
            es_oferta, titulo, motivo = await asyncio.wait_for(
                analizar_oferta_empleo_humano(msg_text, self.db),
                timeout=40.0
            )
        except asyncio.TimeoutError:
            from ai import _analisis_basico_oferta
            es_oferta, titulo, motivo = _analisis_basico_oferta(msg_text)
        
        # Pausa post-análisis (como humano que procesa info)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        if es_oferta:
            logger.info(f"   ✅ OFERTA: {titulo}")
            from storage import save_offer_to_csv
            await save_offer_to_csv(titulo, msg_text, chat_name, motivo, msg_remitente, msg.get('contacto_numero', ''))
            asyncio.create_task(self._enviar_alerta(msg_text, titulo, chat_name, motivo))
            await self.db.increment_stat("offers_found")
        else:
            logger.info(f"   ❌ No oferta: {motivo}")
        
        asyncio.create_task(self._marcar_como_leido_seguro())
        
        if msg_hash:
            await self.db.mark_message_processed(
                msg_hash, msg_text, msg_remitente, chat_name, 
                msg.get('contacto_numero', ''), False, True
            )
        
        self.messages_processed_today += 1
        return True

    async def _enviar_alerta(self, mensaje: str, titulo: str, grupo: str, motivo: str) -> None:
        """Envía alerta visual y sonora"""
        print(f"\n{'🔔' * 35}")
        print(f"🎯 {titulo}")
        print(f"📱 {grupo}")
        print(f"📝 {mensaje[:200]}...")
        print(f"{'🔔' * 35}\n")
        
        if platform.system() == "Linux":
            try:
                if shutil.which("pw-play"):
                    subprocess.run(["pw-play", "/usr/share/sounds/freedesktop/stereo/complete.oga"], check=False)
                elif shutil.which("aplay"):
                    subprocess.run(["aplay", "/usr/share/sounds/alsa/Front_Center.wav"], check=False)
            except Exception:
                pass
    
    # ============================================================
    # MODO TRADICIONAL (CON COMPORTAMIENTO HUMANO)
    # ============================================================
    
    async def run_cycle_traditional(self) -> Tuple[CycleResult, bool]:
        """Ejecuta un ciclo tradicional con timings y comportamiento humano"""
        had_messages = False
        
        # Comportamiento humano ocasional
        await self._perform_human_behavior()
        
        # Pausa humana antes de empezar a revisar
        await asyncio.sleep(random.uniform(0.8, 1.8))
        
        # Verificar congelamiento
        if not await self._anti_freeze_check():
            logger.warning("🔄 Página congelada - forzando reinicio")
            return CycleResult.RESTART, False
        
        # Health check
        if (datetime.now() - self.last_health_check).total_seconds() > HEALTH_CHECK_INTERVAL:
            if not await self._health_check():
                return CycleResult.RESTART, False
        
        # Reinicio programado
        hours_running = (datetime.now() - self.start_time).total_seconds() / 3600
        if hours_running > BROWSER_RESTART_HOURS + random.uniform(-0.5, 0.5):
            logger.info("🔄 Reinicio programado")
            self.restart_count += 1
            self.start_time = datetime.now()
            return CycleResult.RESTART, False
        
        # Demasiados errores
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.error(f"❌ {self.consecutive_errors} errores consecutivos")
            return CycleResult.RESTART, False
        
        await asyncio.sleep(random.uniform(0.5, 1.2))
        
        # Obtener chats con mensajes
        try:
            chats = await asyncio.wait_for(
                obtener_todos_los_chats_optimizado(self.page),
                timeout=25
            )
        except Exception as e:
            logger.error(f"❌ Error obteniendo chats: {e}")
            self.consecutive_errors += 1
            return CycleResult.CONTINUE, False
        
        if not chats:
            logger.debug("📭 Sin mensajes nuevos")
            return CycleResult.CONTINUE, False
        
        # Actualizar cache
        self.known_chats_cache = chats[:10]
        
        logger.info(f"📋 Procesando {len(chats[:MAX_CHATS_PER_CYCLE])} chats")
        
        for idx, chat in enumerate(chats[:MAX_CHATS_PER_CYCLE]):
            chat_name = chat.get("name", "Unknown")
            
            if idx > 0:
                await asyncio.sleep(random.uniform(2.0, 4.0))
            
            try:
                logger.info(f"📂 Abriendo: {chat_name}")
                
                if not await self._open_chat_with_human_mouse(chat_name):
                    logger.warning(f"⚠️ No se pudo abrir chat: {chat_name}")
                    continue
                
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                # Obtener mensajes
                mensajes = await asyncio.wait_for(
                    obtener_mensajes_no_leidos_optimizado(self.page),
                    timeout=MESSAGES_TIMEOUT
                )
                
                if not mensajes:
                    try:
                        await asyncio.wait_for(cerrar_chat_actual(self.page), timeout=2.0)
                    except:
                        pass
                    continue
                
                had_messages = True
                logger.info(f"   📨 {len(mensajes)} mensajes")
                
                # ============================================================
                # OCR OPTIMIZADO - SOLO SI HAY POCOS MENSAJES
                # ============================================================
                if len(mensajes) <= 3:  # Solo OCR si hay pocos mensajes para no demorar
                    try:
                        # Buscar imágenes con timeout corto
                        has_images = await asyncio.wait_for(
                            self.page.query_selector_all('.message-in img, [data-testid="image"] img'),
                            timeout=2.0
                        )
                        
                        if has_images:
                            logger.info(f"   🖼️ Detectadas {len(has_images)} imágenes - OCR rápido")
                            
                            from ocr_module import extract_text_from_all_images_in_chat
                            
                            # OCR con timeout global de 5 segundos
                            ocr_results = await asyncio.wait_for(
                                extract_text_from_all_images_in_chat(self.page),
                                timeout=5.0
                            )
                            
                            for ocr_result in ocr_results:
                                if ocr_result.get('is_job_offer', False):
                                    text = ocr_result.get('text', '')
                                    confidence = ocr_result.get('confidence', 0)
                                    
                                    logger.info(f"   🎯 OFERTA POR OCR: {text[:80]}...")
                                    
                                    from storage import save_offer_to_csv
                                    await save_offer_to_csv(
                                        f"📷 OFERTA OCR", 
                                        text, 
                                        chat_name, 
                                        f"OCR (conf: {confidence:.2f})", 
                                        "OCR_Image", 
                                        ""
                                    )
                                    await self.db.increment_stat("offers_found")
                                    
                                    asyncio.create_task(self._enviar_alerta(
                                        text, "📷 OFERTA OCR", chat_name, f"Confianza: {confidence:.2f}"
                                    ))
                                    
                                    self.messages_processed_today += 1
                                    
                    except asyncio.TimeoutError:
                        logger.debug("   ⏱️ Timeout en OCR, continuando...")
                    except ImportError:
                        logger.debug("   ⚠️ OCR no disponible")
                    except Exception as e:
                        logger.debug(f"   ⚠️ Error OCR: {e}")
                
                # Simular lectura humana
                #await ReadingSimulator.simulate_reading(mensajes)
                
                # Procesar mensajes
                for msg_idx, msg in enumerate(mensajes):
                    try:
                        if msg_idx > 0:
                            await asyncio.sleep(random.uniform(0.3, 0.6))  # Antes era 1.0-2.0
                        
                        try:
                            # Crear la tarea
                            task = asyncio.create_task(self.procesar_mensaje(msg, chat_name))
                            
                            # Esperar con timeout
                            await asyncio.wait_for(asyncio.shield(task), timeout=25.0)
                            
                        except asyncio.TimeoutError:
                            logger.warning(f"⚠️ Timeout procesando mensaje")
                            # Cancelar la tarea si todavía existe
                            if not task.done():
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass
                            continue
                        
                    except asyncio.TimeoutError:
                        logger.warning(f"⚠️ Timeout procesando mensaje")
                        continue
                    except Exception as e:
                        logger.error(f"❌ Error en mensaje: {e}")
                        continue
                
                await asyncio.sleep(random.uniform(1.0, 2.0))
                asyncio.create_task(self._marcar_como_leido_seguro())
                
                try:
                    await asyncio.wait_for(cerrar_chat_actual(self.page), timeout=3.0)
                except:
                    pass
                
                self.consecutive_errors = 0
                
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout en chat {chat_name}")
                try:
                    await asyncio.wait_for(cerrar_chat_actual(self.page), timeout=2.0)
                except:
                    pass
                self.consecutive_errors += 1
                
            except Exception as e:
                logger.error(f"❌ Error en chat {chat_name}: {e}")
                try:
                    await asyncio.wait_for(cerrar_chat_actual(self.page), timeout=2.0)
                except:
                    pass
                self.consecutive_errors += 1
                
                if self.consecutive_errors >= 3:
                    logger.warning(f"⚠️ Demasiados errores ({self.consecutive_errors})")
                    break
        
        return CycleResult.CONTINUE, had_messages

    async def _health_check(self) -> bool:
        """Verifica salud del navegador"""
        try:
            if not self.page or self.page.is_closed():
                return False
            
            title = await self.page.evaluate("document.title")
            if "WhatsApp" not in title:
                return False
            
            self.last_health_check = datetime.now()
            return True
        except Exception:
            return False
    
    # ============================================================
    # MODO CENTINELA (VIGILANCIA VISUAL)
    # ============================================================
    
    async def activar_centinela(self) -> None:
        """Activa el modo centinela con vigilancia visual infinita y micro-movimientos nativos"""
        if self._in_transition:
            logger.debug("⏭️ Ya en transición")
            return
        
        # Inicializar contador de fallos
        if not hasattr(self, '_sentinel_failed_attempts'):
            self._sentinel_failed_attempts = 0
        
        # Limpiar UI antes del centinela
        try:
            await self.page.evaluate("""
                () => {
                    const sidePane = document.querySelector('#pane-side');
                    if (sidePane) sidePane.scrollTop = 0;
                }
            """)
            await asyncio.sleep(0.5)
        except Exception:
            pass

        # Verificar si hay notificaciones reales antes de activar centinela
        force_sentinel = self._sentinel_failed_attempts >= 3
        
        if not force_sentinel:
            try:
                tiene_notificaciones = await self.page.evaluate("""
                    () => {
                        const badges = document.querySelectorAll('[data-testid="icon-unread-count"], ._ak8l');
                        let count = 0;
                        badges.forEach(b => {
                            const val = parseInt(b.textContent);
                            count += isNaN(val) ? 1 : val;
                        });
                        return count > 0;
                    }
                """)
                
                if tiene_notificaciones:
                    self._sentinel_failed_attempts += 1
                    logger.info(f"📬 Notificaciones pendientes (intento {self._sentinel_failed_attempts}/3)")
                    return 
            except Exception as e:
                logger.debug(f"Error en verificación de notificaciones: {e}")

        # Activar modo centinela
        self._sentinel_failed_attempts = 0
        self._in_transition = True
        self._last_sentinel_activation = datetime.now()
        
        logger.info("=" * 60)
        if force_sentinel:
            logger.info("⚠️ MODO CENTINELA FORZADO")
        else:
            logger.info("👁️ ACTIVANDO MODO CENTINELA")
        logger.info("   Vigilancia visual del panel de chats")
        logger.info("   Micro-movimientos nativos cada 25-50s (isTrusted=true)")
        logger.info("=" * 60)

        try:
            # Inicializar centinela
            self.sentinel = SentinelMode(self.page)
            
            # Calibrar centinela (opcional, pero recomendado)
            calibracion = await self.sentinel.calibrar()
            if calibracion.get("error"):
                logger.warning(f"⚠️ Calibración centinela: {calibracion.get('error')}")
            
            # Cambiar estado
            self.monitor_state = MonitorState.SENTINEL
            
            # INICIAR TASK DE MICRO-MOVIMIENTOS NATIVOS
            # Esto es CRÍTICO: reemplaza los eventos sintéticos de stealth_setup.py
            self._idle_mouse_task = asyncio.create_task(self._idle_mouse_while_sentinel())
            logger.info("🖱️ Task de micro-movimientos nativos iniciada")
            
            # Vigilancia infinita (bloqueante)
            logger.info("👁️ Centinela vigilando cambios visuales...")
            detectado = await self.sentinel.vigilancia_infinita()
            
            if detectado:
                logger.info("🎯 ¡Cambio visual detectado! Saliendo del modo centinela")
            else:
                logger.warning("⚠️ Centinela terminó sin detectar cambios")
                
        except asyncio.CancelledError:
            logger.info("👁️ Modo centinela cancelado")
        except Exception as e:
            logger.error(f"❌ Error en modo centinela: {e}")
        finally:
            # LIMPIAR TASK DE MICRO-MOVIMIENTOS
            if hasattr(self, '_idle_mouse_task') and self._idle_mouse_task:
                self._idle_mouse_task.cancel()
                try:
                    await self._idle_mouse_task
                except asyncio.CancelledError:
                    pass
                logger.debug("🖱️ Task de micro-movimientos detenida")
            
            self.monitor_state = MonitorState.TRADITIONAL
            self._in_transition = False
            logger.info("👁️ Modo centinela finalizado, retornando a modo tradicional")

    # ============================================================
    # LOOP PRINCIPAL
    # ============================================================
    
    async def mostrar_estadisticas(self) -> None:
        """Muestra estadísticas del sistema"""
        stats = await self.db.get_stats()
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600
        
        logger.info("=" * 60)
        logger.info(f"📊 ESTADÍSTICAS - Ciclo {self.cycle_count} - Estado: {self.monitor_state.value}")
        logger.info(f"   Mensajes: {self.messages_processed_today} | Spam: {self.spam_filtered_today}")
        logger.info(f"   Ofertas: {stats.get('offers_found', 0)}")
        logger.info(f"   Tiempo: {uptime:.1f}h | Errores: {self.consecutive_errors}")
        logger.info(f"   Acciones humanas: {self.human_actions_today}")
        
        if self.sentinel and self.monitor_state == MonitorState.SENTINEL:
            s_stats = self.sentinel.get_stats()
            logger.info(f"   Centinela: {s_stats.get('mode', '?')} | "
                       f"Capturas: {s_stats.get('screenshots_taken', 0)}")
        
        logger.info("=" * 60)
    
    async def run(self) -> None:
        """Ejecuta el monitor híbrido principal"""
        self.playwright = await async_playwright().start()
        
        try:
            await self.setup_browser(self.playwright)
            
            if not await self.esperar_whatsapp_listo():
                logger.error("❌ No se pudo iniciar WhatsApp")
                return
            
            logger.info("✅ Monitor ONLINE - Anti-Detección Avanzada")
            logger.info("💡 Ctrl+C para detener\n")
            
            while True:
                try:
                    self.cycle_count += 1
                    
                    if self.monitor_state == MonitorState.TRADITIONAL:
                        # Modo Tradicional
                        result, had_messages = await asyncio.wait_for(
                            self.run_cycle_traditional(),
                            timeout=CYCLE_TIMEOUT_SECONDS
                        )
                        
                        if result == CycleResult.RESTART:
                            await self.restart_browser()
                            continue
                        
                        # Estadísticas
                        if self.cycle_count % STATS_CYCLE_INTERVAL == 0:
                            await self.mostrar_estadisticas()
                        
                        # Recargar reglas
                        if self.cycle_count % RELOAD_RULES_INTERVAL == 0:
                            recargar_reglas_ignorar()
                            recargar_prompt_agente()  # ← AÑADIR
                        
                        # Decidir siguiente paso
                        if not had_messages:
                            # Sin actividad: activar centinela
                            pausa = random.uniform(3.0, 6.0)
                            logger.debug(f"⏸️ Pausa pre-centinela: {pausa:.1f}s")
                            await asyncio.sleep(pausa)
                            await self.activar_centinela()
                        else:
                            # Hubo actividad: pausa normal
                            pausa = random.uniform(NORMAL_PAUSE_MIN, NORMAL_PAUSE_MAX)
                            logger.debug(f"⏸️ Pausa tradicional: {pausa:.1f}s")
                            await asyncio.sleep(pausa)
                    
                    else:  # Modo Centinela
                        if self.monitor_state == MonitorState.SENTINEL:
                            self.monitor_state = MonitorState.TRADITIONAL
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                    
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Timeout en ciclo")
                    self.consecutive_errors += 1
                    if self.consecutive_errors >= 3:
                        await self.restart_browser()
                        
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"❌ Error en ciclo: {e}")
                    self.consecutive_errors += 1
                    await asyncio.sleep(5)
                    
        finally:
            await self.playwright.stop()
    


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

async def main() -> None:
    """Función principal"""
    monitor = JobMonitor()
    try:
        await monitor.init()
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("\n👋 Monitor detenido por usuario")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        raise
    finally:
        await monitor.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)