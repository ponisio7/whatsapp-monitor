# typing_simulator.py
import random
import asyncio
from typing import Optional

class HumanTyper:
    """Simula escritura humana con errores y correcciones opcionales"""
    
    # Tiempos entre teclas según distribución real
    LETTER_DELAY = (0.05, 0.15)  # Entre letras
    WORD_PAUSE = (0.15, 0.35)     # Pausa entre palabras
    PUNCTUATION_PAUSE = (0.2, 0.4) # Después de puntuación
    BACKSPACE_DELAY = (0.08, 0.2)  # Velocidad de borrado
    
    @staticmethod
    async def type_human(page, selector: str, text: str, 
                         error_rate: float = 0.02,  # 2% de error
                         backspace_on_error: bool = True,
                         min_wpm: int = 40, max_wpm: int = 80):
        """Escribe texto como un humano, con errores y correcciones"""
        
        # Calcular velocidad base
        avg_wpm = (min_wpm + max_wpm) / 2
        avg_delay_per_char = 60 / (avg_wpm * 5)  # 5 caracteres por palabra promedio
        
        # Enfocar campo
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        for i, char in enumerate(text):
            # ¿Cometer error?
            if random.random() < error_rate and backspace_on_error:
                # Escribir caracter incorrecto
                wrong_char = HumanTyper._get_wrong_char(char)
                await page.keyboard.type(wrong_char, delay=HumanTyper._get_char_delay(avg_delay_per_char))
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # "Oh, error, borrar"
                for _ in range(random.randint(1, 2)):
                    await asyncio.sleep(random.uniform(*HumanTyper.BACKSPACE_DELAY))
                    await page.keyboard.press('Backspace')
                
                await asyncio.sleep(random.uniform(0.1, 0.25))
            
            # Escribir caracter correcto
            await page.keyboard.type(char, delay=HumanTyper._get_char_delay(avg_delay_per_char))
            
            # Pausas especiales
            if char in '.!?':
                await asyncio.sleep(random.uniform(*HumanTyper.PUNCTUATION_PAUSE))
            elif char == ' ':
                await asyncio.sleep(random.uniform(*HumanTyper.WORD_PAUSE))
            elif char == ',':
                await asyncio.sleep(random.uniform(0.1, 0.25))
            
            # Pequeña pausa al llegar al final de una palabra larga
            if i > 0 and text[i-1].isalpha() and char == ' ' and (i - text.rfind(' ', 0, i-1) > 8):
                await asyncio.sleep(random.uniform(0.05, 0.15))
    
    @staticmethod
    def _get_char_delay(base_delay: float) -> float:
        """Genera delay realista con variación"""
        # Algunas letras son más lentas (mayúsculas, símbolos raros)
        variation = random.gauss(1.0, 0.3)
        return max(0.02, base_delay * variation)
    
    @staticmethod
    def _get_wrong_char(correct_char: str) -> str:
        """Genera un error típico humano (teclas cercanas en QWERTY)"""
        # Distribución de errores comunes en QWERTY
        nearby_keys = {
            'a': 'sqw', 'b': 'vghn', 'c': 'xdfv', 'd': 'sfecx', 'e': 'wrd',
            'f': 'dgrv', 'g': 'fhtb', 'h': 'gjny', 'i': 'uok', 'j': 'hkim',
            'k': 'jil', 'l': 'kop', 'm': 'njk', 'n': 'bmh', 'o': 'ipl',
            'p': 'o', 'q': 'wa', 'r': 'etf', 's': 'awd', 't': 'ryg',
            'u': 'yih', 'v': 'cfb', 'w': 'qes', 'x': 'zsc', 'y': 'tuh',
            'z': 'asx'
        }
        
        if correct_char.lower() in nearby_keys:
            possible = list(nearby_keys[correct_char.lower()])
            if correct_char.isupper():
                return random.choice(possible).upper()
            return random.choice(possible)
        
        # Error genérico: caracter cercano en ASCII
        offset = random.choice([-1, 1])
        return chr(ord(correct_char) + offset) if random.random() < 0.7 else correct_char