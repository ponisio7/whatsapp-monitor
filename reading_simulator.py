# reading_simulator.py - VERSIÓN ULTRARRÁPIDA
"""
Simulador de lectura optimizado para monitor de ofertas.
No simula lectura real, sino ESCANEO VISUAL RÁPIDO.
Un humano que busca ofertas NO lee todo palabra por palabra.
"""
import random
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ReadingSimulator:
    """Simula ESCANEO visual rápido de mensajes - NO lectura real"""
    
    # Velocidad de escaneo (palabras por segundo, no caracteres)
    # Un humano escanea ofertas a ~20-30 palabras/segundo
    SCAN_SPEED_WPS = 30
    
    @staticmethod
    async def simulate_reading(messages: List[Dict[str, Any]], 
                                base_delay_per_char: float = None) -> None:
        """
        Simula escaneo rápido de mensajes.
        
        Estrategia:
        - NO lee caracter por caracter
        - Calcula tiempo total basado en palabras
        - Pausa única, no múltiples sleeps
        - Máximo 2 segundos por chat
        """
        if not messages:
            return
        
        # Contar palabras totales (mejor métrica que caracteres)
        total_words = 0
        has_offer_keywords = False
        
        offer_keywords = ['trabajo', 'empleo', 'oferta', '$', '€', 'salario', 
                         'contrato', 'empresa', 'remoto', 'programador', 
                         'desarrollador', 'ingeniero', 'sueldo']
        
        for msg in messages:
            text = msg.get('text', '')
            total_words += len(text.split())
            
            # Detectar si hay algo interesante
            if not has_offer_keywords:
                text_lower = text.lower()
                if any(kw in text_lower for kw in offer_keywords):
                    has_offer_keywords = True
        
        # Tiempo base de escaneo: palabras / velocidad
        scan_time = total_words / ReadingSimulator.SCAN_SPEED_WPS
        
        # Si hay ofertas, tiempo extra MUY pequeño (solo para "detenerse" mentalmente)
        if has_offer_keywords:
            scan_time += random.uniform(0.3, 0.8)
        
        # Límite máximo por chat: 2.5 segundos (nunca más)
        scan_time = min(scan_time, 2.5)
        
        # Añadir micro-variación (parece humano, pero es rápido)
        scan_time = scan_time * random.uniform(0.85, 1.15)
        
        # Pequeña pausa inicial (como si el humano posara la vista)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Pausa principal de escaneo (ÚNICA PAUSA - no múltiples)
        if scan_time > 0:
            logger.debug(f"   ⚡ Escaneo rápido: {total_words} palabras en {scan_time:.2f}s")
            await asyncio.sleep(scan_time)
        
        # Micro-pausa final (como procesamiento visual)
        await asyncio.sleep(random.uniform(0.05, 0.1))