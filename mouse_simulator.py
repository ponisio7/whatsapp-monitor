# mouse_simulator.py
import random
import math
import asyncio
from typing import Tuple, List, Optional

class MouseSimulator:
    """Simula movimientos de ratón humanos usando curvas Bézier"""
    
    @staticmethod
    async def move_to_element(page, element, duration: float = None):
        """Mueve el ratón a un elemento siguiendo una curva natural"""
        # Obtener posición actual y objetivo
        current_pos = await page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
        box = await element.bounding_box()
        
        if not box:
            return await element.click()
        
        target_x = box['x'] + box['width'] / 2 + random.uniform(-5, 5)
        target_y = box['y'] + box['height'] / 2 + random.uniform(-5, 5)
        
        # Duración basada en distancia (más humano)
        if duration is None:
            distance = math.hypot(target_x - current_pos.get('x', 0), target_y - current_pos.get('y', 0))
            duration = random.uniform(0.3, 0.8) * (distance / 500) + random.uniform(0.1, 0.3)
        
        # Generar puntos de la curva Bézier cúbica
        points = MouseSimulator._generate_bezier_curve(
            (current_pos.get('x', random.randint(100, 500)), current_pos.get('y', random.randint(100, 500))),
            (target_x, target_y),
            num_points=max(20, int(duration * 60))
        )
        
        # Ejecutar movimiento con pequeños overshoots
        for i, (x, y) in enumerate(points):
            await page.mouse.move(x, y)
            # Delay variable según la fase del movimiento
            if i < len(points) * 0.2:  # Aceleración inicial
                await asyncio.sleep(duration / len(points) * random.uniform(0.8, 1.2))
            elif i > len(points) * 0.8:  # Desaceleración final
                await asyncio.sleep(duration / len(points) * random.uniform(1.0, 1.5))
            else:
                await asyncio.sleep(duration / len(points) * random.uniform(0.9, 1.1))
        
        # Pequeño overshoot y corrección (muy humano)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.move(target_x + random.uniform(-3, 3), target_y + random.uniform(-3, 3))
        await asyncio.sleep(random.uniform(0.02, 0.05))
        await page.mouse.move(target_x, target_y)
        
        # Registrar posición actual
        await page.evaluate(f"window.mouseX = {target_x}; window.mouseY = {target_y}")
        
        return target_x, target_y
    
    @staticmethod
    def _generate_bezier_curve(start: Tuple[float, float], end: Tuple[float, float], num_points: int) -> List[Tuple[float, float]]:
        """Genera curva Bézier cúbica con puntos de control aleatorios"""
        # Puntos de control con desviación humana
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        
        # Curvatura aleatoria (nunca línea recta perfecta)
        control1 = (
            start[0] + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
            start[1] + dy * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        )
        control2 = (
            start[0] + dx * random.uniform(0.6, 0.8) + random.uniform(-50, 50),
            start[1] + dy * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
        )
        
        points = []
        for t in range(num_points + 1):
            t_norm = t / num_points
            # Fórmula de Bézier cúbica
            x = (1-t_norm)**3 * start[0] + 3*(1-t_norm)**2*t_norm * control1[0] + 3*(1-t_norm)*t_norm**2 * control2[0] + t_norm**3 * end[0]
            y = (1-t_norm)**3 * start[1] + 3*(1-t_norm)**2*t_norm * control1[1] + 3*(1-t_norm)*t_norm**2 * control2[1] + t_norm**3 * end[1]
            points.append((x, y))
        
        return points
    
    @staticmethod
    async def click_humano(page, selector: str, delay_before_click: float = None):
        """Click humano completo: hover sutil -> espera -> click"""
        elemento = await page.query_selector(selector)
        if not elemento:
            return False
        
        # Hover sutil primero (como humano que busca)
        await MouseSimulator.move_to_element(page, elemento)
        
        # Pausa de "decisión" (¿realmente quiero hacer click?)
        await asyncio.sleep(random.uniform(0.1, 0.4))
        
        # Pequeño micro-movimiento antes del click
        await page.mouse.move(
            random.uniform(-2, 2),
            random.uniform(-2, 2)
        )
        await asyncio.sleep(random.uniform(0.02, 0.08))
        
        # Click
        await page.mouse.click()
        
        return True
    
    # Añadir a la clase MouseSimulator:

    @staticmethod
    async def click_humano_mejorado(page, selector: str, offset_x: int = 0, offset_y: int = 0):
        """Click humano mejorado con micro-movimientos y timing variable"""
        elemento = await page.query_selector(selector)
        if not elemento:
            return False
        
        # Obtener bounding box
        box = await elemento.bounding_box()
        if not box:
            return await elemento.click()
        
        # Coordenada objetivo con desviación humana
        target_x = box['x'] + box['width'] / 2 + random.randint(-8, 8) + offset_x
        target_y = box['y'] + box['height'] / 2 + random.randint(-8, 8) + offset_y
        
        # Obtener posición actual del ratón
        current = await page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
        
        # Decidir si hacer un movimiento en curva o directo
        use_bezier = random.random() < 0.7
        
        if use_bezier:
            await MouseSimulator.move_to_element_with_bezier(page, elemento, target_x, target_y)
        else:
            # Movimiento con ruido
            steps = random.randint(8, 15)
            for i in range(steps):
                progress = i / steps
                x = current.get('x', 0) + (target_x - current.get('x', 0)) * progress + random.randint(-3, 3)
                y = current.get('y', 0) + (target_y - current.get('y', 0)) * progress + random.randint(-3, 3)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.005, 0.02))
        
        # Pequeña pausa antes del click (humano duda)
        await asyncio.sleep(random.uniform(0.08, 0.25))
        
        # Micro-movimiento justo antes del click
        await page.mouse.move(target_x + random.randint(-2, 2), target_y + random.randint(-2, 2))
        await asyncio.sleep(random.uniform(0.01, 0.04))
        await page.mouse.move(target_x, target_y)
        await asyncio.sleep(random.uniform(0.02, 0.08))
        
        # Click con presión variable
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.15))  # Tiempo presionando
        await page.mouse.up()
        
        # Registrar posición
        await page.evaluate(f"window.mouseX = {target_x}; window.mouseY = {target_y}")
        
        return True

    @staticmethod
    async def move_to_element_with_bezier(page, element, target_x: float, target_y: float):
        """Movimiento con curva Bézier (más humano)"""
        current = await page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
        
        # Calcular distancia
        distance = math.hypot(target_x - current.get('x', 0), target_y - current.get('y', 0))
        duration = min(1.5, max(0.3, distance / 800)) * random.uniform(0.8, 1.5)
        
        # Generar puntos de control aleatorios (curva natural)
        cp1_x = current.get('x', 0) + (target_x - current.get('x', 0)) * random.uniform(0.2, 0.4) + random.randint(-50, 50)
        cp1_y = current.get('y', 0) + (target_y - current.get('y', 0)) * random.uniform(0.2, 0.4) + random.randint(-50, 50)
        cp2_x = current.get('x', 0) + (target_x - current.get('x', 0)) * random.uniform(0.6, 0.8) + random.randint(-50, 50)
        cp2_y = current.get('y', 0) + (target_y - current.get('y', 0)) * random.uniform(0.6, 0.8) + random.randint(-50, 50)
        
        steps = max(30, int(duration * 60))
        
        for i in range(steps + 1):
            t = i / steps
            
            # Curva Bézier cúbica
            x = (1-t)**3 * current.get('x', 0) + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * target_x
            y = (1-t)**3 * current.get('y', 0) + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * target_y
            
            await page.mouse.move(x, y)
            
            # Delay variable (aceleración/desaceleración)
            if t < 0.2:
                await asyncio.sleep(duration / steps * random.uniform(0.8, 1.0))
            elif t > 0.8:
                await asyncio.sleep(duration / steps * random.uniform(1.0, 1.3))
            else:
                await asyncio.sleep(duration / steps * random.uniform(0.9, 1.1))

    @staticmethod
    async def micro_movimiento_idle(page, intensity: str = "low"):
        """
        Micro-movimiento nativo para periodos de inactividad.
        isTrusted = TRUE porque usa page.mouse.move()
        
        intensity: "low" (1-2px), "medium" (3-5px), "high" (6-10px)
        """
        # Obtener posición actual
        current = await page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
        
        if not current.get('x') or current.get('x') == 0:
            # Sin posición registrada, usar centro de pantalla
            viewport = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
            current = {'x': viewport['w'] // 2, 'y': viewport['h'] // 2}
        
        # Definir rango de movimiento
        ranges = {
            "low": (1, 3),
            "medium": (3, 6),
            "high": (6, 11)
        }
        min_delta, max_delta = ranges.get(intensity, (2, 5))
        
        delta_x = random.uniform(min_delta, max_delta) * random.choice([-1, 1])
        delta_y = random.uniform(min_delta, max_delta) * random.choice([-1, 1])
        
        # Limitar dentro de viewport
        viewport = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
        new_x = max(50, min(viewport['w'] - 50, current['x'] + delta_x))
        new_y = max(50, min(viewport['h'] - 100, current['y'] + delta_y))
        
        # Movimiento suave (con steps para que sea incremental, no teletransporte)
        steps = random.randint(2, 4)
        for i in range(1, steps + 1):
            progress = i / steps
            step_x = current['x'] + (new_x - current['x']) * progress
            step_y = current['y'] + (new_y - current['y']) * progress
            await page.mouse.move(step_x, step_y)
            await asyncio.sleep(random.uniform(0.008, 0.025))
        
        # Actualizar posición en JS
        await page.evaluate(f"window.mouseX = {new_x}; window.mouseY = {new_y}")
        
        return new_x, new_y