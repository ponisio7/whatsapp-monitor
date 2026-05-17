# sentinel_mode.py
"""
Modo Centinela - Vigilancia pasiva mediante análisis visual
Detecta nuevos mensajes SIN ser afectado por la terminal u otras ventanas.
Versión: v2.0 - Aislamiento total del navegador
"""
import asyncio
import io
import random
import logging
from typing import Tuple, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import hashlib

import numpy as np
from PIL import Image
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class SentinelMode:
    """Vigilancia visual pasiva de WhatsApp Web"""
    
    # Configuración de detección de círculo verde
    GREEN_RGB_MIN = (40, 180, 40)      # Verde característico de WhatsApp
    GREEN_RGB_MAX = (120, 255, 120)    # Rango estricto
    MIN_CIRCLE_PIXELS = 8             # Mínimo píxeles para considerar círculo
    MAX_CIRCLE_PIXELS = 300            # Máximo píxeles de un círculo normal
    
    # Umbrales de cambio
    MIN_DIFF_THRESHOLD = 0.09          # 12% mínimo de cambio (evita ruido)
    SIGNIFICANT_DIFF = 0.15            # 25% cambio muy significativo
    
    # Intervalos de verificación
    NORMAL_INTERVAL = (3, 6)          # Segundos entre verificaciones (normal)
    DEEP_SLEEP_INTERVAL = (15, 25)     # Intervalo cuando inactivo (ahorra CPU)
    
    # Configuración anti-falsos-positivos
    REQUIRED_CONFIRMATIONS = 1          # Confirmaciones necesarias
    CONFIRMATION_WINDOW = 5.0          # Ventana de tiempo para confirmar (segundos)
    
    def __init__(self, page: Page, data_dir: Path = Path("./sentinel_data")):
        """
        Inicializa el modo centinela
        
        Args:
            page: Página de Playwright de WhatsApp Web
            data_dir: Directorio para datos persistentes
        """
        self.page = page
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        
        # Estado interno
        self.captura_base: Optional[bytes] = None
        self.consecutive_empty = 0
        self.screenshots_taken = 0
        self.mode = "normal"  # normal, deep_sleep
        
        # Anti-falsos-positivos
        self._pending_detections: list = []  # [(timestamp, diferencia)]
        self._last_confirmed_detection: Optional[datetime] = None
        
        # Estadísticas
        self.detection_count = 0
        self.false_positives = 0
        self.real_detections = 0
        
        logger.info("👁️ SentinelMode v2.0 inicializado")
        logger.info(f"   Umbral mínimo: {self.MIN_DIFF_THRESHOLD:.0%}")
        logger.info(f"   Confirmaciones necesarias: {self.REQUIRED_CONFIRMATIONS}")

    # sentinel_mode.py - Agregar este método a la clase SentinelMode

    async def _sleep_con_micro_movimientos(self, seconds: float):
        """Sleep con micro-movimientos nativos periódicos (isTrusted=true)"""
        from mouse_simulator import MouseSimulator  # Import aquí para evitar circular
        
        elapsed = 0
        interval = random.uniform(8, 15)  # Intervalo humano entre micro-movimientos
        
        while elapsed < seconds:
            sleep_chunk = min(interval, seconds - elapsed)
            await asyncio.sleep(sleep_chunk)
            elapsed += sleep_chunk
            
            # Probabilidad de micro-movimiento durante inactividad (~70%)
            if random.random() < 0.7 and elapsed < seconds:
                intensity = random.choices(
                    ["low", "medium"], 
                    weights=[0.85, 0.15]  # 85% low, 15% medium (nunca high)
                )[0]
                
                try:
                    await MouseSimulator.micro_movimiento_idle(
                        self.page, 
                        intensity=intensity
                    )
                except Exception as e:
                    logger.debug(f"Micro-movimiento falló: {e}")

    
    # ============================================================
    # MÉTODOS PRINCIPALES
    # ============================================================
    
    async def calibrar(self) -> Dict[str, Any]:
        """
        Calibra el centinela analizando la interfaz actual
        
        Returns:
            Dict con estadísticas de calibración
        """
        logger.info("🔧 Calibrando SentinelMode...")
        
        try:
            # Capturar área de chats
            screenshot = await self._capturar_area_chats()
            
            if not screenshot:
                logger.warning("⚠️ No se pudo capturar área para calibración")
                return {"error": "No se pudo capturar"}
            
            # Analizar estadísticas de color
            img = Image.open(io.BytesIO(screenshot))
            img_array = np.array(img.convert('RGB'))
            
            # Estadísticas de canales
            stats = {
                "mean_red": float(np.mean(img_array[:,:,0])),
                "mean_green": float(np.mean(img_array[:,:,1])),
                "mean_blue": float(np.mean(img_array[:,:,2])),
                "std_green": float(np.std(img_array[:,:,1])),
                "total_pixels": img_array.shape[0] * img_array.shape[1],
                "timestamp": datetime.now().isoformat()
            }
            
            # Detectar si la interfaz está oscura o clara
            brightness = (stats["mean_red"] + stats["mean_green"] + stats["mean_blue"]) / 3
            stats["brightness"] = brightness
            stats["is_dark_mode"] = brightness < 100
            
            # Ajustar umbrales según modo oscuro/claro
            if stats["is_dark_mode"]:
                logger.info("   🌙 Modo oscuro detectado - ajustando umbrales")
                # En modo oscuro, el verde resalta más
                self.MIN_DIFF_THRESHOLD = 0.10
                self.GREEN_RGB_MIN = (30, 200, 30)
            else:
                logger.info("   ☀️ Modo claro detectado")
                self.MIN_DIFF_THRESHOLD = 0.12
                self.GREEN_RGB_MIN = (40, 180, 40)
            
            logger.info(f"   ✅ Calibración completada")
            logger.info(f"   Brillo promedio: {brightness:.1f}")
            logger.info(f"   Modo oscuro: {stats['is_dark_mode']}")
            
            # Guardar calibración
            self.captura_base = screenshot
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error en calibración: {e}")
            return {"error": str(e)}
    
    async def vigilancia_infinita(self, callback_on_detection=None) -> bool:
        """
        Vigilancia INFINITA hasta detectar actividad real.
        
        Args:
            callback_on_detection: Función a ejecutar cuando se detecta actividad
        
        Returns:
            bool: True si se detectó actividad, False si hubo error fatal
        """
        logger.info("=" * 50)
        logger.info("👁️ INICIANDO VIGILANCIA VISUAL INFINITA")
        logger.info("   ✅ Capturas limitadas AL panel de chats")
        logger.info("   🎯 Detectando: Círculo verde | Reordenamiento")
        logger.info("   🔇 Terminal y logs IGNORADOS")
        logger.info("=" * 50)
        
        # Asegurar que tenemos una captura base
        if not self.captura_base:
            self.captura_base = await self._capturar_area_chats()
            if not self.captura_base:
                logger.error("❌ No se pudo establecer captura base")
                return False
        
        ultimo_log_estado = datetime.now()
        modo_sueno_activado = False
        
        while True:
            try:
                # Determinar intervalo de verificación según modo
                if self.mode == "deep_sleep":
                    wait_time = random.uniform(*self.DEEP_SLEEP_INTERVAL)
                else:
                    wait_time = random.uniform(*self.NORMAL_INTERVAL)
                
                # En vigilancia_infinita(), cambiar esto:
                # await asyncio.sleep(wait_time)  # ❌ viejo

                # Por esto:
                await self._sleep_con_micro_movimientos(wait_time)  # ✅ nuevo
                
                # Detectar cambios (SOLO en el área de chats)
                tiene_cambios, detalles = await self._detectar_cambios_con_confirmacion()
                
                # Log periódico del estado (cada ~2 minutos)
                if (datetime.now() - ultimo_log_estado).total_seconds() > 120:
                    logger.info(f"💤 Centinela activo - Modo: {self.mode} | "
                               f"Verificaciones: {self.screenshots_taken} | "
                               f"Sueño: {self.consecutive_empty} ciclos")
                    ultimo_log_estado = datetime.now()
                
                # Si se confirma actividad real
                if tiene_cambios:
                    logger.info("=" * 50)
                    logger.info(f"🎯 ¡ACTIVIDAD REAL CONFIRMADA!")
                    logger.info(f"   Tipo: {detalles.get('tipo', 'desconocido')}")
                    logger.info(f"   Confianza: {detalles.get('confianza', 0):.0%}")
                    logger.info("=" * 50)
                    
                    self.real_detections += 1
                    
                    # Actualizar captura base para próxima ronda
                    self.captura_base = await self._capturar_area_chats()
                    
                    # Ejecutar callback si existe
                    if callback_on_detection:
                        await callback_on_detection()
                    
                    return True
                
                # Gestionar modo sueño profundo
                if self.consecutive_empty > 20 and not modo_sueno_activado:
                    self.mode = "deep_sleep"
                    modo_sueno_activado = True
                    logger.info("💤 Modo sueño profundo activado (verificaciones más espaciadas)")
                elif self.consecutive_empty < 10 and modo_sueno_activado:
                    self.mode = "normal"
                    modo_sueno_activado = False
                    logger.info("⚡ Volviendo a modo normal")
                
            except Exception as e:
                logger.error(f"❌ Error en vigilancia: {e}")
                await asyncio.sleep(5)
                
                # Si la página se cerró, retornar error
                if "closed" in str(e).lower():
                    return False
    
    # ============================================================
    # MÉTODOS DE CAPTURA (AISLADOS)
    # ============================================================
    
    async def _capturar_area_chats(self) -> Optional[bytes]:
        """
        Captura EXCLUSIVAMENTE el área de la lista de chats.
        IGNORA completamente la terminal, escritorio y otras ventanas.
        
        Returns:
            bytes de la imagen PNG o None si error
        """
        try:
            # Estrategia 1: Capturar el panel lateral específico de WhatsApp
            selectores = [
                '#pane-side',                           # Selector oficial
                'div[data-testid="chat-list"]',         # Test ID
                'div[class*="chat-list"]',              # Clase genérica
                'div[role="region"]:first-child',       # Primera región
            ]
            
            for selector in selectores:
                try:
                    elemento = await self.page.query_selector(selector)
                    if elemento:
                        screenshot = await elemento.screenshot(type='png')
                        if screenshot and len(screenshot) > 1000:  # Mínimo 1KB
                            self.screenshots_taken += 1
                            logger.debug(f"📸 Captura vía {selector[:30]}")
                            return screenshot
                except Exception:
                    continue
            
            # Estrategia 2: Capturar viewport completo pero recortar inteligentemente
            screenshot_completo = await self.page.screenshot(type='png')
            
            if not screenshot_completo:
                logger.warning("⚠️ No se pudo capturar la página")
                return None
            
            # Recortar para quedarnos SOLO con el área de chats
            img = Image.open(io.BytesIO(screenshot_completo))
            ancho, alto = img.size
            
            # El panel de chats está en la parte izquierda (primer 35-40%)
            # y excluyendo headers y footers
            img_recortada = img.crop((
                0,                      # izquierda
                70,                     # superior (saltar header de WhatsApp)
                int(ancho * 0.45),      # derecha (~45% del ancho)
                alto - 60               # inferior (saltar input)
            ))
            
            # Guardar en bytes
            output = io.BytesIO()
            img_recortada.save(output, format='PNG')
            screenshot = output.getvalue()
            
            self.screenshots_taken += 1
            logger.debug(f"📸 Captura recortada: {img_recortada.size}")
            return screenshot
            
        except Exception as e:
            logger.error(f"❌ Error capturando área de chats: {e}")
            return None
    
    # ============================================================
    # MÉTODOS DE DETECCIÓN
    # ============================================================
    
    async def _detectar_cambios_con_confirmacion(self) -> Tuple[bool, Dict]:
        """
        Detecta cambios con sistema de confirmación para evitar falsos positivos
        
        Returns:
            Tuple[bool, Dict]: (confirmado, detalles)
        """
        try:
            # Capturar estado actual
            screenshot_actual = await self._capturar_area_chats()
            
            if not screenshot_actual:
                return False, {"error": "No se pudo capturar"}
            
            if self.captura_base is None:
                self.captura_base = screenshot_actual
                return False, {"tipo": "inicializacion"}
            
            # 1. Detección específica de círculo verde (más confiable)
            tiene_circulo_verde = await self._detectar_circulo_verde(screenshot_actual)
            
            if tiene_circulo_verde:
                # Círculo verde es DETECCIÓN INMEDIATA (alta confianza)
                self._pending_detections = []
                self._last_confirmed_detection = datetime.now()
                self.consecutive_empty = 0  # Reset contador inactivo
                logger.info("🟢 ¡CÍRCULO VERDE detectado! Activando inmediatamente")
                return True, {
                    "tipo": "circulo_verde",
                    "confianza": 0.98,
                    "timestamp": datetime.now().isoformat()
                }
            
            # 2. Detectar cambios estructurales (reordenamiento de chats)
            diferencia = self._calcular_diferencia(screenshot_actual, self.captura_base)
            
            # 🔥 LOG DE DEPURACIÓN: Mostrar diferencia detectada
            if diferencia > 0.01:  # Solo log si hay cambio mínimo
                logger.debug(f"📊 Diferencia detectada: {diferencia:.1%} (umbral: {self.MIN_DIFF_THRESHOLD:.1%})")
            
            # 🔥 CAMBIO CRÍTICO: Si hay diferencia significativa, detectar inmediatamente
            if diferencia > self.MIN_DIFF_THRESHOLD:
                timestamp_actual = datetime.now()
                
                # Limpiar detecciones viejas (fuera de la ventana)
                self._pending_detections = [
                    (ts, diff) for ts, diff in self._pending_detections
                    if (timestamp_actual - ts).total_seconds() < self.CONFIRMATION_WINDOW
                ]
                
                # Agregar esta detección
                self._pending_detections.append((timestamp_actual, diferencia))
                
                # 🔥 CON REQUIRED_CONFIRMATIONS=1, esto es TRUE inmediatamente
                if len(self._pending_detections) >= self.REQUIRED_CONFIRMATIONS:
                    logger.info(f"🎯 CAMBIO CONFIRMADO: diferencia={diferencia:.1%}, "
                            f"confirmaciones={len(self._pending_detections)}/{self.REQUIRED_CONFIRMATIONS}")
                    
                    # Guardar estadísticas
                    self.real_detections += 1
                    self.consecutive_empty = 0
                    
                    # Limpiar detecciones pendientes
                    self._pending_detections = []
                    self._last_confirmed_detection = timestamp_actual
                    
                    # Actualizar captura base para próxima ronda
                    self.captura_base = screenshot_actual
                    
                    # Determinar tipo de cambio según magnitud
                    tipo = "reordenamiento_mayor" if diferencia > self.SIGNIFICANT_DIFF else "reordenamiento_menor"
                    
                    return True, {
                        "tipo": tipo,
                        "diferencia": diferencia,
                        "confianza": min(0.95, diferencia * 3),
                        "confirmaciones": len(self._pending_detections),
                        "timestamp": timestamp_actual.isoformat()
                    }
                else:
                    # Todavía no hay suficientes confirmaciones
                    logger.debug(f"⏳ Detección pendiente: {len(self._pending_detections)}/{self.REQUIRED_CONFIRMATIONS}, "
                            f"diferencia={diferencia:.1%}")
                    
                    # Actualizar base para siguiente comparación (adaptación gradual)
                    self.captura_base = screenshot_actual
                    
                    return False, {
                        "tipo": "deteccion_pendiente",
                        "diferencia": diferencia,
                        "pendientes": len(self._pending_detections),
                        "necesarias": self.REQUIRED_CONFIRMATIONS
                    }
            
            elif diferencia > self.MIN_DIFF_THRESHOLD * 0.5:
                # Cambio muy pequeño, posible ruido visual (sombras, animaciones)
                # No activar, pero adaptar base lentamente
                if random.random() < 0.1:  # Solo 10% de adaptación
                    self.captura_base = screenshot_actual
                    logger.debug(f"🔄 Adaptación gradual por ruido: {diferencia:.1%}")
                
                return False, {
                    "tipo": "cambio_menor",
                    "diferencia": diferencia,
                    "ignorado": True
                }
            
            # Sin cambios significativos
            self.consecutive_empty += 1
            
            # Log periódico cada 30 ciclos sin cambios
            if self.consecutive_empty % 30 == 0 and self.consecutive_empty > 0:
                logger.debug(f"💤 Sin cambios - {self.consecutive_empty} ciclos consecutivos")
            
            return False, {
                "tipo": "sin_cambios",
                "consecutive_empty": self.consecutive_empty,
                "diferencia": diferencia
            }
            
        except Exception as e:
            logger.error(f"Error en detección: {e}")
            return False, {"error": str(e)}
    
    async def _detectar_circulo_verde(self, screenshot_bytes: bytes) -> bool:
        """
        Detecta específicamente el círculo verde de notificación no leída.
        Esta es la señal MÁS CONFIABLE de nuevo mensaje.
        
        Args:
            screenshot_bytes: Bytes de la imagen PNG
            
        Returns:
            bool: True si se detecta círculo verde
        """
        try:
            # Cargar imagen
            img = Image.open(io.BytesIO(screenshot_bytes))
            
            # Redimensionar para análisis más rápido (manteniendo proporción)
            img.thumbnail((400, 600))
            img_array = np.array(img.convert('RGB'))
            
            # Detectar píxeles verdes dentro del rango de WhatsApp
            verde_mask = (
                (img_array[:,:,0] >= self.GREEN_RGB_MIN[0]) & (img_array[:,:,0] <= self.GREEN_RGB_MAX[0]) &
                (img_array[:,:,1] >= self.GREEN_RGB_MIN[1]) & (img_array[:,:,1] <= self.GREEN_RGB_MAX[1]) &
                (img_array[:,:,2] >= self.GREEN_RGB_MIN[2]) & (img_array[:,:,2] <= self.GREEN_RGB_MAX[2])
            )
            
            # Encontrar componentes conectadas (clusters)
            from scipy import ndimage
            labeled, num_features = ndimage.label(verde_mask)
            
            for i in range(1, num_features + 1):
                cluster_size = np.sum(labeled == i)
                
                # Un círculo típico tiene entre 15 y 300 píxeles
                if self.MIN_CIRCLE_PIXELS <= cluster_size <= self.MAX_CIRCLE_PIXELS:
                    # Verificar circularidad
                    coords = np.where(labeled == i)
                    if len(coords[0]) > 0:
                        alto_cluster = coords[0].max() - coords[0].min()
                        ancho_cluster = coords[1].max() - coords[1].min()
                        
                        # Evitar división por cero
                        if min(alto_cluster, ancho_cluster) > 0:
                            ratio = max(alto_cluster, ancho_cluster) / min(alto_cluster, ancho_cluster)
                            
                            # Si es aproximadamente circular (ratio < 1.5)
                            if ratio < 1.5:
                                logger.debug(f"🟢 Círculo verde detectado: {cluster_size}px, ratio={ratio:.2f}")
                                self.detection_count += 1
                                return True
            
            return False
            
        except ImportError:
            # Fallback si scipy no está disponible
            logger.debug("scipy no disponible, usando detección básica")
            verde_count = np.sum(
                (img_array[:,:,1] > 180) &  # Verde alto
                (img_array[:,:,0] < 100) &   # Rojo bajo
                (img_array[:,:,2] < 100)     # Azul bajo
            )
            return verde_count > 30
            
        except Exception as e:
            logger.debug(f"Error en detección círculo verde: {e}")
            return False
    
    def _calcular_diferencia(self, img1_bytes: bytes, img2_bytes: bytes) -> float:
        """
        Calcula el porcentaje de diferencia entre dos imágenes
        
        Args:
            img1_bytes: Primera imagen en bytes
            img2_bytes: Segunda imagen en bytes
            
        Returns:
            float: Porcentaje de diferencia (0.0 a 1.0)
        """
        try:
            # Cargar imágenes
            img1 = Image.open(io.BytesIO(img1_bytes)).convert('RGB')
            img2 = Image.open(io.BytesIO(img2_bytes)).convert('RGB')
            
            # Redimensionar al mismo tamaño si es necesario
            if img1.size != img2.size:
                target_size = (min(img1.width, img2.width), min(img1.height, img2.height))
                img1 = img1.resize(target_size, Image.Resampling.LANCZOS)
                img2 = img2.resize(target_size, Image.Resampling.LANCZOS)
            
            # Convertir a arrays numpy
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            
            # Calcular diferencia por canal (con umbral para ignorar ruido)
            umbral_ruido = 25
            diff = np.abs(arr1.astype(np.int16) - arr2.astype(np.int16)) > umbral_ruido
            
            # Píxeles diferentes en cualquier canal
            pixeles_diferentes = np.sum(np.any(diff, axis=2))
            
            total_pixeles = arr1.shape[0] * arr1.shape[1]
            porcentaje = pixeles_diferentes / total_pixeles
            
            return float(porcentaje)
            
        except Exception as e:
            logger.error(f"Error calculando diferencia: {e}")
            return 0.0
    
    # ============================================================
    # MÉTODOS DE UTILIDAD
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas del centinela
        
        Returns:
            Dict con estadísticas
        """
        return {
            "mode": self.mode,
            "screenshots_taken": self.screenshots_taken,
            "consecutive_empty": self.consecutive_empty,
            "detection_count": self.detection_count,
            "real_detections": self.real_detections,
            "false_positives": self.false_positives,
            "has_base_capture": self.captura_base is not None,
            "thresholds": {
                "min_diff": self.MIN_DIFF_THRESHOLD,
                "significant_diff": self.SIGNIFICANT_DIFF,
                "required_confirmations": self.REQUIRED_CONFIRMATIONS,
                "green_range": [self.GREEN_RGB_MIN, self.GREEN_RGB_MAX]
            }
        }
    
    async def reset(self) -> None:
        """Resetea el estado del centinela"""
        self.captura_base = None
        self.consecutive_empty = 0
        self._pending_detections = []
        self._last_confirmed_detection = None
        self.mode = "normal"
        logger.info("🔄 SentinelMode reseteado")
    
    async def take_debug_screenshot(self, filename: str = None) -> Optional[Path]:
        """
        Toma una captura de depuración del área de chats
        
        Args:
            filename: Nombre del archivo (opcional)
            
        Returns:
            Path del archivo guardado o None
        """
        try:
            screenshot = await self._capturar_area_chats()
            if screenshot:
                if not filename:
                    filename = f"debug_chat_area_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                
                filepath = self.data_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(screenshot)
                
                logger.info(f"📸 Debug screenshot guardado: {filepath}")
                return filepath
        except Exception as e:
            logger.error(f"Error guardando debug screenshot: {e}")
        
        return None