# config_ocr.py
"""Configuración del módulo OCR"""

import os
from pathlib import Path

# Directorios
OCR_CACHE_DIR = Path("./ocr_cache")
OCR_SCREENSHOT_DIR = Path("./screenshots")

# Configuración OCR
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_USE_PADDLE = os.getenv("OCR_USE_PADDLE", "true").lower() == "true"
OCR_USE_TESSERACT = os.getenv("OCR_USE_TESSERACT", "true").lower() == "true"

# Intervalos
OCR_SCREENSHOT_INTERVAL = float(os.getenv("OCR_SCREENSHOT_INTERVAL", "10.0"))
OCR_CACHE_TTL_HOURS = int(os.getenv("OCR_CACHE_TTL_HOURS", "24"))

# Umbrales
OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.6"))

# Crear directorios
OCR_CACHE_DIR.mkdir(exist_ok=True)
OCR_SCREENSHOT_DIR.mkdir(exist_ok=True)