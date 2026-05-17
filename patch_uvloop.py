# patch_uvloop.py
"""Parche para desactivar uvloop cuando sea necesario"""
import asyncio
import sys

def patch_uvloop():
    """Desactiva uvloop para compatibilidad con Playwright"""
    try:
        import uvloop
        # Verificar si uvloop está activo
        if isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy):
            # Cambiar a política por defecto
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            print("✅ uvloop desactivado para compatibilidad con Playwright")
    except ImportError:
        pass

if __name__ == "__main__":
    patch_uvloop()