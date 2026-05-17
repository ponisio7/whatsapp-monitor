"""
Módulo que maneja la conexión con WhatsApp Web usando wa-js.
NO más scraping de DOM, NO más polling.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable

from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)

USER_DATA_DIR = "./session_wa_jobs"
WA_JS_CDN = "https://github.com/wppconnect-team/wa-js/releases/latest/download/wppconnect-wa.js"
WA_JS_LOCAL = Path(__file__).parent / "wa_js_bundle.js"
INJECTOR_PATH = Path(__file__).parent / "wa_js_injector.js"


class WhatsAppListener:
    def __init__(self, on_message_callback: Callable[[dict], None]):
        self.on_message = on_message_callback
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._is_running = False
        self._loop = None
    
    async def start(self) -> bool:
        """Inicia el listener y espera que WhatsApp esté listo"""
        self._loop = asyncio.get_running_loop()  # ← Captura correcta
        logger.info("🚀 Iniciando WhatsApp Listener (modo eventos)...")
        
        await self._download_wa_js_if_needed()
        
        self.playwright = await async_playwright().start()
        
        if not await self._setup_browser():
            return False
        
        if not await self._wait_for_whatsapp():
            return False
        
        self._is_running = True
        logger.info("✅ WhatsApp Listener activo - esperando mensajes en tiempo real")
        return True
    
    async def _download_wa_js_if_needed(self):
        if WA_JS_LOCAL.exists():
            return
        
        logger.info("📦 Descargando wa-js...")
        try:
            import httpx
            # ✅ Añadir follow_redirects=True
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(WA_JS_CDN, timeout=30)
                response.raise_for_status()
                WA_JS_LOCAL.write_text(response.text, encoding='utf-8')
            logger.info("✅ wa-js descargado")
        except Exception as e:
            logger.error(f"❌ Error descargando wa-js: {e}")
            raise
    
    async def _setup_browser(self) -> bool:
        """Configura el navegador con persistencia de sesión"""
        try:
            user_data_dir = Path(USER_DATA_DIR)
            user_data_dir.mkdir(exist_ok=True)
            
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                viewport=None,
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            )
            
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            
            # Cargar scripts al inicio (sobreviven reloads)
            wa_js_content = WA_JS_LOCAL.read_text(encoding='utf-8')
            await self.context.add_init_script(wa_js_content)
            
            injector_content = INJECTOR_PATH.read_text(encoding='utf-8')
            await self.context.add_init_script(injector_content)
            
            # Exponer función Python
            await self.page.expose_function("onNewMessagePython", self._handle_message_sync)
            
            # Re-exponer tras cada navegación/reload
            self.page.on("framenavigated", self._on_navigation)
            
            logger.info("✅ Navegador configurado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error configurando navegador: {e}")
            return False
    
    async def _on_navigation(self, frame) -> None:
        """Re-exponer la función si la página recargó."""
        if frame == self.page.main_frame:
            logger.info("🔄 Navegación detectada, re-exponiendo función...")
            try:
                await self.page.expose_function("onNewMessagePython", self._handle_message_sync)
            except Exception as e:
                # Si ya existe, Playwright lanza error - podemos ignorarlo
                logger.debug(f"Expose ya existente: {e}")
    
    def _handle_message_sync(self, payload: dict) -> None:
        """
        Playwright llama esto desde dentro del event loop.
        Solo crea una tarea - no run_coroutine_threadsafe.
        """
        try:
            asyncio.create_task(self.on_message(payload))
            logger.debug(f"📩 Encolado: [{payload.get('chat_name')}] {payload.get('text', '')[:50]}")
        except Exception as e:
            logger.error(f"Error en handler sync: {e}")
    
    async def _wait_for_whatsapp(self, timeout: int = 120) -> bool:
        """Espera a que WhatsApp Web cargue y el QR sea escaneado"""
        logger.info("🌐 Cargando WhatsApp Web...")
        await self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if await self._is_logged_in():
                logger.info("✅ Sesión ya activa")
                return True
            
            qr_element = await self.page.query_selector('canvas[aria-label="Scan me!"]')
            if qr_element:
                logger.info("📱 QR detectado - Escanea con tu teléfono")
                await self.page.wait_for_selector('canvas[aria-label="Scan me!"]', state="detached", timeout=60000)
                logger.info("✅ QR escaneado correctamente")
                await asyncio.sleep(3)
                return True
            
            await asyncio.sleep(2)
        
        logger.error("❌ Timeout esperando WhatsApp")
        return False
    
    async def _is_logged_in(self) -> bool:
        """Verifica sesión sin depender de DOM scraping"""
        try:
            # Método 1: Usar WPP si está disponible
            return await self.page.evaluate("""
                () => {
                    if (window.WPP?.conn?.isRegistered?.()) return true;
                    if (window.WPP?.isReady === true) return true;
                    // Si no hay WPP todavía, asumimos que no estamos logueados
                    return false;
                }
            """)
        except:
            # Fallback ultra básico solo durante carga inicial
            try:
                rows = await self.page.query_selector_all('div[role="row"]')
                return len(rows) > 0
            except:
                return False
    
    async def stop(self):
        """Detiene el listener y cierra el navegador"""
        self._is_running = False
        
        if self.context:
            await self.context.close()
        
        if self.playwright:
            await self.playwright.stop()
        
        logger.info("🛑 WhatsApp Listener detenido")
    
    async def health_check(self) -> bool:
        """Verifica que el listener siga funcionando (con reinjección automática)"""
        if not self._is_running:
            return False
        
        try:
            if not self.page or self.page.is_closed():
                return False
            
            status = await self.page.evaluate("""
                () => {
                    return {
                        wpp_ready: window.WPP?.isReady === true,
                        listener_active: window.__jobMonitorListenerActive === true,
                        msg_count: window.__jobMonitorMsgCount || 0
                    };
                }
            """)
            
            wpp_ready = status.get('wpp_ready', False)
            
            if wpp_ready and not status.get('listener_active', False):
                logger.warning("⚠️ Listener perdido, re-inyectando...")
                injector_content = INJECTOR_PATH.read_text(encoding='utf-8')
                await self.page.evaluate(injector_content)
                await asyncio.sleep(2)
                
                # Verificar que funcionó
                reinyectado = await self.page.evaluate("""
                    () => window.__jobMonitorListenerActive === true
                """)
                if reinyectado:
                    logger.info("✅ Listener reinyectado correctamente")
                    return True
                else:
                    logger.error("❌ Falló la reinyección")
                    return False
            
            # Mostrar estadísticas si hay mensajes
            if status.get('msg_count', 0) > 0:
                logger.debug(f"📊 Mensajes recibidos: {status['msg_count']}")
            
            return wpp_ready
            
        except Exception as e:
            logger.error(f"Health check falló: {e}")
            return False