# ocr_module.py - VERSIÓN CORREGIDA

import asyncio
import logging
import re
import hashlib
import base64
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from io import BytesIO
from datetime import datetime
import random

import cv2
import numpy as np
from PIL import Image
from playwright.async_api import Page, ElementHandle

logger = logging.getLogger(__name__)

# Intentar importar OCR engines
TESSERACT_AVAILABLE = False
PADDLE_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
    logger.debug("✅ Tesseract OCR disponible")
except ImportError:
    logger.debug("⚠️ pytesseract no instalado")

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    logger.debug("✅ PaddleOCR disponible")
except ImportError:
    logger.debug("⚠️ PaddleOCR no instalado")


class OCRProcessor:
    """Procesador OCR para imágenes de WhatsApp"""
    
    # Palabras clave para ofertas de empleo (español)
    JOB_KEYWORDS = [
        'oferta', 'empleo', 'trabajo', 'vacante', 'contrato', 'salario',
        'empresa', 'buscamos', 'contratamos', 'seleccionamos', 'candidatos',
        'incorporación', 'jornada', 'remoto', 'presencial', 'horario',
        'experiencia', 'requisitos', 'funciones', 'beneficios',
        'ingeniero', 'técnico', 'operario', 'conductor', 'repartidor',
        'limpieza', 'mantenimiento', 'seguridad', 'logística', 'almacén',
        'carpintero', 'electricista', 'fontanero', 'construcción', 'obra',
        'atención al cliente', 'ventas', 'administrativo', 'recepcionista'
    ]
    
    # Palabras clave de spam
    SPAM_KEYWORDS = [
        'premio', 'ganaste', 'sorteo', 'haz clic', 'registrate',
        'deposita', 'envía dinero', 'inversión segura', 'invierta',
        'gana dinero desde casa', 'multinivel', 'esquema'
    ]
    
    def __init__(self, cache_dir: Path = Path("./ocr_cache")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        
        self._paddle_ocr = None
        self._cache: Dict[str, Dict] = {}
        self._stats = {
            "images_processed": 0,
            "texts_extracted": 0,
            "cache_hits": 0,
            "offers_detected": 0
        }
        
        # Inicializar OCR engines (manejo de errores mejorado)
        self._init_ocr_engines()
    
    def _init_ocr_engines(self):
        """Inicializa motores OCR disponibles con manejo de errores"""
        # DESHABILITAR PaddleOCR temporalmente (da error)
        # if PADDLE_AVAILABLE and not self._paddle_ocr:
        #     try:
        #         ... código de PaddleOCR ...
        
        # Solo usar Tesseract (más estable)
        if TESSERACT_AVAILABLE:
            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"✅ Tesseract OCR disponible (v{version})")
                logger.info("   Nota: PaddleOCR deshabilitado (problemas de API)")
            except Exception as e:
                logger.warning(f"⚠️ Tesseract no disponible: {e}")

    def _get_image_hash(self, image_data: bytes) -> str:
        """Genera hash de la imagen para caché"""
        return hashlib.md5(image_data).hexdigest()
    
    async def extract_text_from_image(
        self, 
        image_data: bytes, 
        force_refresh: bool = False,
        timeout: float = 5.0
    ) -> Optional[str]:
        """
        Extrae texto de una imagen usando OCR con timeout.
        
        Args:
            image_data: Bytes de la imagen
            force_refresh: Si True, ignora caché
            timeout: Timeout máximo para OCR (segundos)
        
        Returns:
            Texto extraído o None si falla
        """
        img_hash = self._get_image_hash(image_data)
        
        # Verificar caché
        if not force_refresh and img_hash in self._cache:
            self._stats["cache_hits"] += 1
            logger.debug(f"📦 OCR caché hit: {img_hash[:8]}")
            return self._cache[img_hash].get("text")
        
        try:
            # Ejecutar OCR con timeout
            text = await asyncio.wait_for(
                self._do_ocr(image_data),
                timeout=timeout
            )
            
            if text:
                self._stats["texts_extracted"] += 1
                logger.debug(f"🔍 OCR extrajo: {text[:100]}...")
                
                # Guardar en caché
                self._cache[img_hash] = {
                    "text": text,
                    "timestamp": datetime.now().isoformat()
                }
                
                return text
            
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout en OCR ({timeout}s)")
            return None
        except Exception as e:
            logger.error(f"❌ Error en OCR: {e}")
            return None
    
    async def _do_ocr(self, image_data: bytes) -> Optional[str]:
        """Ejecuta OCR en un thread separado"""
        # Convertir bytes a imagen OpenCV
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.warning("❌ No se pudo decodificar la imagen")
            return None
        
        # Preprocesar imagen para mejor OCR
        processed_img = self._preprocess_image(img)
        
        # Intentar OCR con diferentes engines
        text = None
        
        # Priorizar Tesseract (más estable)
        if TESSERACT_AVAILABLE:
            text = await self._ocr_with_tesseract(processed_img)
        
        # Si Tesseract falla o da poco texto, intentar con Paddle
        if (not text or len(text) < 20) and self._paddle_ocr:
            paddle_text = await self._ocr_with_paddle(processed_img)
            if paddle_text and len(paddle_text) > len(text or ""):
                text = paddle_text
        
        return text
    
    def _preprocess_image(self, img: np.ndarray) -> np.ndarray:
        """Preprocesa imagen para mejorar OCR (rápido y eficiente)"""
        # Convertir a grises
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Redimensionar solo si es muy pequeña (OCR rápido)
        height, width = gray.shape
        if width < 300:
            scale = 500 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Aplicar CLAHE para mejorar contraste
        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
        except Exception:
            enhanced = gray
        
        # Binarización simple (más rápida que adaptativa)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    async def _ocr_with_paddle(self, img: np.ndarray) -> Optional[str]:
        """OCR con PaddleOCR (rápido)"""
        try:
            # Ejecutar en thread pool
            result = await asyncio.to_thread(self._paddle_ocr.ocr, img, cls=True)
            
            if not result or not result[0]:
                return None
            
            texts = []
            for line in result[0]:
                if line and len(line) >= 2:
                    if isinstance(line[1], tuple) and len(line[1]) >= 1:
                        text = line[1][0]
                        confidence = line[1][1] if len(line[1]) > 1 else 0
                        if confidence > 0.5 and text.strip():
                            texts.append(text.strip())
                    elif isinstance(line[1], str):
                        texts.append(line[1].strip())
            
            return " ".join(texts) if texts else None
            
        except Exception as e:
            logger.debug(f"PaddleOCR error: {e}")
            return None
    
    async def _ocr_with_tesseract(self, img: np.ndarray) -> Optional[str]:
        """OCR con Tesseract"""
        try:
            # Configuración para español (rápida)
            custom_config = r'--oem 3 --psm 6 -l spa'
            
            text = await asyncio.to_thread(
                pytesseract.image_to_string,
                img,
                config=custom_config
            )
            
            return text.strip() if text else None
            
        except Exception as e:
            logger.debug(f"Tesseract error: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza texto extraído"""
        if not text:
            return ""
        
        # Eliminar caracteres especiales repetidos
        text = re.sub(r'\s+', ' ', text)
        
        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def analyze_text_for_job(self, text: str) -> Tuple[bool, float, List[str]]:
        """
        Analiza si el texto extraído corresponde a una oferta de empleo.
        """
        if not text:
            return False, 0.0, []
        
        text_lower = text.lower()
        
        # Verificar spam primero
        spam_matches = [kw for kw in self.SPAM_KEYWORDS if kw in text_lower]
        if spam_matches:
            return False, 0.0, spam_matches
        
        # Buscar palabras clave de empleo
        job_matches = [kw for kw in self.JOB_KEYWORDS if kw in text_lower]
        
        # Calcular confianza
        confidence = min(len(job_matches) / 3, 1.0)
        
        # Patrones comunes en ofertas
        job_patterns = [
            r'se busca', r'se necesita', r'se solicita', r'contratamos',
            r'buscamos', r'ofrecemos', r'vacante', r'puesto de',
            r'salario', r'beneficios', r'horario', r'incorporar'
        ]
        
        pattern_matches = 0
        for pattern in job_patterns:
            if re.search(pattern, text_lower):
                pattern_matches += 1
        
        # Ajustar confianza
        confidence += pattern_matches * 0.15
        confidence = min(confidence, 1.0)
        
        # Una oferta necesita al menos 1 palabra clave o patrón
        is_job = (len(job_matches) >= 1) or (pattern_matches >= 1)
        
        return is_job, confidence, job_matches
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del OCR"""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "paddle_available": PADDLE_AVAILABLE and self._paddle_ocr is not None,
            "tesseract_available": TESSERACT_AVAILABLE
        }


async def extract_text_from_all_images_in_chat(page: Page, timeout: float = 3.0) -> List[Dict]:
    """
    Extrae texto de todas las imágenes en el chat actual con timeout.
    """
    ocr = OCRProcessor()
    results = []
    
    try:
        # Buscar imágenes con timeout
        image_messages = await asyncio.wait_for(
            page.query_selector_all('.message-in img, [data-testid="image"] img, img[src*="blob"]'),
            timeout=timeout
        )
        
        if not image_messages:
            logger.debug("📭 No se encontraron imágenes en el chat")
            return []
        
        logger.info(f"🔍 Encontradas {len(image_messages)} imágenes en el chat")
        
        for idx, img in enumerate(image_messages):
            try:
                # Verificar visibilidad rápido
                is_visible = await asyncio.wait_for(img.is_visible(), timeout=1.0)
                if not is_visible:
                    continue
                
                # Obtener src
                src = await img.get_attribute("src")
                if not src:
                    continue
                
                # Decodificar imagen
                if src.startswith('data:image'):
                    base64_data = src.split(',')[1] if ',' in src else src
                    image_data = base64.b64decode(base64_data)
                    
                    # OCR con timeout
                    text = await ocr.extract_text_from_image(image_data, timeout=2.0)
                    
                    if text:
                        is_job, confidence, keywords = ocr.analyze_text_for_job(text)
                        
                        if is_job:
                            results.append({
                                "text": text,
                                "is_job_offer": is_job,
                                "confidence": confidence,
                                "keywords": keywords,
                                "image_index": idx
                            })
                            logger.info(f"🎯 OCR detectó oferta en imagen {idx + 1} (conf: {confidence:.2f})")
                        else:
                            logger.debug(f"📷 Imagen {idx + 1}: no es oferta - '{text[:50]}...'")
                
                # Pausa pequeña entre imágenes
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
            except asyncio.TimeoutError:
                logger.debug(f"⏱️ Timeout procesando imagen {idx}")
                continue
            except Exception as e:
                logger.debug(f"Error procesando imagen {idx}: {e}")
                continue
        
        return results
        
    except asyncio.TimeoutError:
        logger.warning("⏱️ Timeout buscando imágenes en el chat")
        return []
    except Exception as e:
        logger.error(f"Error extrayendo imágenes: {e}")
        return []