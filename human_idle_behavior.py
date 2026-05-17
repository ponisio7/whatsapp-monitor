# human_idle_behavior.py
"""
Comportamientos humanos durante el tiempo de inactividad (idle).
Movimientos de ratón por aburrimiento, scrolls aleatorios, etc.
"""
import asyncio
import random
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

class HumanIdleBehavior:
    """Simula comportamientos humanos cuando el bot no está activamente procesando"""
    
    @staticmethod
    async def ejecutar_micromovimientos(page: Page, duracion_segundos: float) -> None:
        """
        Ejecuta micromovimientos durante un período de inactividad.
        
        Args:
            page: Página de Playwright
            duracion_segundos: Tiempo total de inactividad (ej: pausa entre ciclos)
        """
        start_time = asyncio.get_event_loop().time()
        elapsed = 0
        
        while elapsed < duracion_segundos:
            # Decidir qué tipo de micromovimiento hacer
            accion = random.choices(
                population=['mouse_sutil', 'scroll_minimo', 'micro_pausa', 'nada'],
                weights=[0.4, 0.3, 0.2, 0.1],
                k=1
            )[0]
            
            if accion == 'mouse_sutil':
                await HumanIdleBehavior._micro_movimiento_raton(page)
                await asyncio.sleep(random.uniform(2.0, 5.0))
                
            elif accion == 'scroll_minimo':
                await HumanIdleBehavior._micro_scroll(page)
                await asyncio.sleep(random.uniform(1.5, 4.0))
                
            elif accion == 'micro_pausa':
                # "Pensar" o distraerse
                await asyncio.sleep(random.uniform(3.0, 8.0))
            
            # Siempre hay un pequeño delay entre acciones
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            elapsed = asyncio.get_event_loop().time() - start_time
    
    @staticmethod
    async def _micro_movimiento_raton(page: Page) -> None:
        """Movimiento de ratón sutil como si el usuario estuviera distraído"""
        try:
            # Obtener posición actual
            current = await page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
            
            # Movimiento muy pequeño y lento (como mover el mouse sin intención)
            delta_x = random.randint(-30, 30)
            delta_y = random.randint(-20, 20)
            
            # Evitar mover demasiado hacia bordes (no queremos salir de la ventana)
            new_x = max(50, min(current.get('x', 500) + delta_x, 1800))
            new_y = max(50, min(current.get('y', 400) + delta_y, 900))
            
            # Movimiento lento y con curva
            steps = random.randint(5, 12)
            for i in range(steps):
                progress = i / steps
                # Curva suave senoidal
                x = current.get('x', 500) + (new_x - current.get('x', 500)) * (0.5 - 0.5 * math.cos(progress * math.pi))
                y = current.get('y', 400) + (new_y - current.get('y', 400)) * (0.5 - 0.5 * math.cos(progress * math.pi))
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.01, 0.03))
            
            # Registrar posición
            await page.evaluate(f"window.mouseX = {new_x}; window.mouseY = {new_y}")
            logger.debug(f"   🖱️ Micromovimiento: ({delta_x:+d}, {delta_y:+d})")
            
        except Exception as e:
            logger.debug(f"Error en micromovimiento: {e}")
    
    @staticmethod
    async def _micro_scroll(page: Page) -> None:
        """Scroll muy pequeño y rápido (como aburrimiento)"""
        try:
            # Scroll aleatorio hacia arriba o abajo
            direccion = random.choice([-1, 1])
            cantidad = random.randint(30, 150) * direccion
            
            await page.evaluate(f"""
                window.scrollBy({{ top: {cantidad}, behavior: 'smooth' }});
            """)
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            # A veces scroll de vuelta (compensación)
            if random.random() < 0.4:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await page.evaluate(f"""
                    window.scrollBy({{ top: {-cantidad // 2}, behavior: 'smooth' }});
                """)
            
            logger.debug(f"   📜 Micro-scroll: {cantidad}px")
            
        except Exception as e:
            logger.debug(f"Error en micro-scroll: {e}")


class GhostInteractions:
    """Interacciones fantasma: abrir chats sin mensajes nuevos por 'ansiedad'"""
    
    @staticmethod
    async def revisar_chat_aleatorio(page: Page, chats_conocidos: list, probability: float = 0.3) -> bool:
        """
        De vez en cuando, abre un chat aleatorio que NO tiene mensajes nuevos
        (como un humano que revisa por costumbre/ansiedad).
        
        Args:
            page: Página de Playwright
            chats_conocidos: Lista de nombres de chats visibles en la lista
            probability: Probabilidad de ejecutar (0-1)
        
        Returns:
            True si se ejecutó una interacción fantasma, False si no
        """
        if not chats_conocidos or random.random() > probability:
            return False
        
        # Filtrar para no interrumpir si ya hay un chat abierto
        already_open = await GhostInteractions._is_any_chat_open(page)
        if already_open:
            return False
        
        # Seleccionar un chat aleatorio (podría ser el primero de la lista)
        chat_objetivo = random.choice(chats_conocidos)
        chat_name = chat_objetivo.get('name', '')
        
        if not chat_name:
            return False
        
        logger.info(f"👻 Interacción fantasma: abriendo '{chat_name}' (sin mensajes nuevos, solo curiosidad)")
        
        # Abrir el chat
        from whatsapp import abrir_chat_por_nombre
        abierto = await abrir_chat_por_nombre(page, chat_name, max_intentos=1)
        
        if abierto:
            # "Leer" rápidamente (como humano que solo ojea)
            await asyncio.sleep(random.uniform(1.0, 2.5))
            
            # Scroll sutil mientras "revisa"
            if random.random() < 0.5:
                await page.evaluate("window.scrollBy({ top: 200, behavior: 'smooth' })")
                await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Cerrar el chat (sin haber procesado nada)
            from whatsapp import cerrar_chat_actual
            await cerrar_chat_actual(page)
            
            logger.info(f"   👻 Chat fantasma cerrado (no se procesaron mensajes)")
            return True
        
        return False
    
    @staticmethod
    async def _is_any_chat_open(page: Page) -> bool:
        """Verifica si hay algún chat abierto actualmente"""
        try:
            return await page.evaluate("""
                () => {
                    const header = document.querySelector('#main header');
                    const panel = document.querySelector('[data-testid="conversation-panel-messages"]');
                    return header !== null && panel !== null;
                }
            """)
        except Exception:
            return False