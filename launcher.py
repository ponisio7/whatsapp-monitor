# launcher.py - versión corregida
#!/usr/bin/env python3
"""Lanzador para WhatsApp Job Monitor con GUI"""
import sys
import subprocess
import importlib.util
import asyncio
from pathlib import Path

def check_and_install_dependencies():
    """Verificar e instalar dependencias faltantes"""
    required = [
        "playwright", "openai", "python-dotenv",
        "PyQt6", "numpy", "pillow"
    ]
    
    missing = []
    for package in required:
        if importlib.util.find_spec(package) is None:
            missing.append(package)
    
    if missing:
        print(f"📦 Instalando dependencias faltantes: {', '.join(missing)}")
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
        print("✅ Dependencias instaladas")
        
        # Instalar playwright browsers
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    
    return True

def disable_uvloop():
    """Desactivar uvloop para compatibilidad con Playwright"""
    try:
        import uvloop
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        print("✅ uvloop desactivado (compatibilidad con Playwright)")
    except ImportError:
        pass

if __name__ == "__main__":
    print("=" * 50)
    print("📱 WhatsApp Job Monitor - Dashboard GUI")
    print("=" * 50)
    
    # Desactivar uvloop ANTES de importar main_window
    disable_uvloop()
    
    # Verificar dependencias
    check_and_install_dependencies()
    
    # Lanzar GUI
    from main_window import main
    main()