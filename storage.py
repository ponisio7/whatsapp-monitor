import sqlite3
import asyncio
import csv
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

# ============================================================
# CLASE PRINCIPAL DE BASE DE DATOS
# ============================================================

class Database:
    def __init__(self, db_path: str = "whatsapp_monitor.db"):
        self.db_path = db_path
        self.conn = None
        self.lock = asyncio.Lock()
    
    async def init(self):
        """Inicializa la base de datos y crea tablas si no existen"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Crear tablas
        await self._create_tables()
        
        # Verificar y migrar esquema si es necesario
        await self._migrate_schema()
        
        logger.info("✅ Base de datos inicializada")
    
    async def _create_tables(self):
        """Crea todas las tablas necesarias"""
        cursor = self.conn.cursor()
        
        # Tabla de mensajes procesados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                msg_id TEXT PRIMARY KEY,
                message_text TEXT,
                remitente TEXT,
                chat_name TEXT,
                contacto_numero TEXT,
                is_spam BOOLEAN DEFAULT 0,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analyzed BOOLEAN DEFAULT 1
            )
        """)
        
        # Tabla de caché de análisis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                message_hash TEXT PRIMARY KEY,
                is_offer BOOLEAN,
                title TEXT,
                reason TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de estadísticas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de ofertas guardadas (para búsqueda rápida)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                mensaje TEXT,
                grupo TEXT,
                motivo TEXT,
                remitente TEXT,
                contacto_numero TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                csv_exported BOOLEAN DEFAULT 0
            )
        """)
        
        # Tabla de spam detectado (para estadísticas detalladas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id TEXT,
                motivo TEXT,
                remitente TEXT,
                chat_name TEXT,
                contacto_numero TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para mejorar rendimiento
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_messages(processed_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_spam ON processed_messages(is_spam)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_hash ON analysis_cache(message_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_offers_date ON saved_offers(saved_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_spam_date ON spam_log(detected_at)")
        
        self.conn.commit()
        
        # Inicializar estadísticas por defecto
        await self._init_default_stats()
    
    async def _migrate_schema(self):
        """Migra el esquema existente si es necesario (backward compatibility)"""
        cursor = self.conn.cursor()
        
        # Verificar si la columna is_spam existe en processed_messages
        cursor.execute("PRAGMA table_info(processed_messages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_spam' not in columns:
            logger.info("🔄 Migrando esquema: añadiendo columna is_spam")
            cursor.execute("ALTER TABLE processed_messages ADD COLUMN is_spam BOOLEAN DEFAULT 0")
            self.conn.commit()
        
        if 'analyzed' not in columns:
            logger.info("🔄 Migrando esquema: añadiendo columna analyzed")
            cursor.execute("ALTER TABLE processed_messages ADD COLUMN analyzed BOOLEAN DEFAULT 1")
            self.conn.commit()
    
    async def _init_default_stats(self):
        """Inicializa las estadísticas por defecto"""
        cursor = self.conn.cursor()
        
        default_stats = [
            ('offers_found', 0),
            ('messages_processed', 0),
            ('spam_filtered', 0),
            ('analysis_cache_hits', 0),
            ('api_calls', 0)
        ]
        
        for key, value in default_stats:
            cursor.execute(
                "INSERT OR IGNORE INTO stats (key, value) VALUES (?, ?)",
                (key, value)
            )
        
        self.conn.commit()
    
    # ============================================================
    # MÉTODOS PARA MENSAJES PROCESADOS
    # ============================================================
    
    async def is_message_processed(self, msg_id: str) -> bool:
        """Verifica si un mensaje ya fue procesado"""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_messages WHERE msg_id = ?",
                (msg_id,)
            )
            return cursor.fetchone() is not None
    
    async def mark_message_processed(
        self, 
        msg_id: str, 
        message_text: str = "", 
        remitente: str = "", 
        chat_name: str = "",
        contacto_numero: str = "", 
        is_spam: bool = False,
        analyzed: bool = True
    ):
        """Marca un mensaje como procesado con todos sus metadatos"""
        async with self.lock:
            cursor = self.conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO processed_messages 
                    (msg_id, message_text, remitente, chat_name, contacto_numero, is_spam, analyzed, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (msg_id, message_text[:1000], remitente, chat_name, contacto_numero, 
                      1 if is_spam else 0, 1 if analyzed else 0))
                
                # Actualizar estadísticas
                await self.increment_stat("messages_processed")
                
                if is_spam:
                    await self.increment_stat("spam_filtered")
                    
                    # Guardar en log de spam
                    cursor.execute("""
                        INSERT INTO spam_log (msg_id, remitente, chat_name, contacto_numero, motivo)
                        VALUES (?, ?, ?, ?, ?)
                    """, (msg_id, remitente, chat_name, contacto_numero, "Filtrado por reglas AGENT.md"))
                
                self.conn.commit()
                
            except Exception as e:
                logger.error(f"Error guardando mensaje procesado: {e}")
                self.conn.rollback()
    
    # ============================================================
    # MÉTODOS PARA CACHÉ DE ANÁLISIS
    # ============================================================
    
    async def get_cached_analysis(self, message_text: str) -> Optional[Tuple[bool, str, str]]:
        """Obtiene análisis cacheado de un mensaje"""
        message_hash = self._hash_message(message_text)
        
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT is_offer, title, reason FROM analysis_cache WHERE message_hash = ?",
                (message_hash,)
            )
            row = cursor.fetchone()
            
            if row:
                await self.increment_stat("analysis_cache_hits")
                return (bool(row['is_offer']), row['title'], row['reason'])
            
            return None
    
    async def cache_analysis(self, message_text: str, is_offer: bool, title: str, reason: str):
        """Guarda análisis en caché"""
        message_hash = self._hash_message(message_text)
        
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO analysis_cache 
                (message_hash, is_offer, title, reason, analyzed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (message_hash, 1 if is_offer else 0, title[:200], reason[:200]))
            
            self.conn.commit()
    
    # ============================================================
    # MÉTODOS PARA ESTADÍSTICAS
    # ============================================================
    
    async def increment_stat(self, key: str, increment: int = 1):
        """Incrementa una estadística"""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO stats (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET 
                    value = value + ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, increment, increment))
            self.conn.commit()
    
    async def get_stat(self, key: str) -> int:
        """Obtiene el valor de una estadística"""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM stats WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else 0
    
    async def get_stats(self) -> Dict[str, int]:
        """Obtiene todas las estadísticas"""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT key, value FROM stats")
            rows = cursor.fetchall()
            return {row['key']: row['value'] for row in rows}
    
    # ============================================================
    # MÉTODOS PARA OFERTAS
    # ============================================================
    
    async def save_offer(self, titulo: str, mensaje: str, grupo: str, motivo: str,
                        remitente: str = "", contacto_numero: str = ""):
        """Guarda una oferta en la base de datos"""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO saved_offers 
                (titulo, mensaje, grupo, motivo, remitente, contacto_numero, saved_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (titulo[:200], mensaje[:2000], grupo[:100], motivo[:200], 
                  remitente[:100], contacto_numero[:50]))
            self.conn.commit()
            return cursor.lastrowid
    
    async def get_today_offers(self) -> List[Dict]:
        """Obtiene las ofertas de hoy"""
        async with self.lock:
            cursor = self.conn.cursor()
            today = date.today().isoformat()
            cursor.execute("""
                SELECT * FROM saved_offers 
                WHERE DATE(saved_at) = ?
                ORDER BY saved_at DESC
            """, (today,))
            return [dict(row) for row in cursor.fetchall()]
    
    async def get_spam_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas detalladas de spam"""
        async with self.lock:
            cursor = self.conn.cursor()
            
            # Spam por día
            cursor.execute("""
                SELECT DATE(detected_at) as fecha, COUNT(*) as total
                FROM spam_log
                GROUP BY DATE(detected_at)
                ORDER BY fecha DESC
                LIMIT 7
            """)
            daily_spam = {row['fecha']: row['total'] for row in cursor.fetchall()}
            
            # Top chats con spam
            cursor.execute("""
                SELECT chat_name, COUNT(*) as total
                FROM spam_log
                GROUP BY chat_name
                ORDER BY total DESC
                LIMIT 10
            """)
            top_chats = [dict(row) for row in cursor.fetchall()]
            
            # Top remitentes spam
            cursor.execute("""
                SELECT remitente, COUNT(*) as total
                FROM spam_log
                WHERE remitente != ''
                GROUP BY remitente
                ORDER BY total DESC
                LIMIT 10
            """)
            top_remitentes = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_spam': await self.get_stat('spam_filtered'),
                'daily_spam': daily_spam,
                'top_spam_chats': top_chats,
                'top_spam_senders': top_remitentes
            }
    
    # ============================================================
    # MÉTODOS DE UTILIDAD
    # ============================================================
    
    async def clear_old_data(self, days: int = 30):
        """Limpia datos antiguos para mantener la DB liviana"""
        async with self.lock:
            cursor = self.conn.cursor()
            
            # Limpiar caché viejo
            cursor.execute("""
                DELETE FROM analysis_cache 
                WHERE analyzed_at < datetime('now', ?)
            """, (f'-{days} days',))
            
            # Limpiar logs de spam antiguos
            cursor.execute("""
                DELETE FROM spam_log 
                WHERE detected_at < datetime('now', ?)
            """, (f'-{days} days',))
            
            deleted_cache = cursor.rowcount
            deleted_spam = cursor.rowcount
            
            self.conn.commit()
            logger.info(f"🧹 Limpieza automática: {deleted_cache} cachés, {deleted_spam} logs eliminados")
    
    @staticmethod
    def _hash_message(message: str) -> str:
        """Genera un hash del mensaje para caché"""
        import hashlib
        # Limitar longitud para hash consistente
        normalized = ' '.join(message.lower().split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    async def close(self):
        """Cierra la conexión a la base de datos"""
        if self.conn:
            self.conn.close()
            logger.info("✅ Base de datos cerrada")


# ============================================================
# FUNCIONES PARA GUARDAR EN CSV
# ============================================================

async def save_offer_to_csv(titulo: str, mensaje: str, grupo: str, motivo: str,
                           remitente: str = "", contacto_numero: str = ""):
    """Guarda una oferta en archivo CSV"""
    csv_file = Path("ofertas_detectadas.csv")
    
    # Crear archivo con headers si no existe
    file_exists = csv_file.exists()
    
    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            if not file_exists:
                writer.writerow([
                    'fecha', 'titulo', 'mensaje', 'grupo', 'motivo', 
                    'remitente', 'contacto_numero', 'fuente'
                ])
            
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                titulo,
                mensaje.replace('\n', ' ').replace(',', ';'),  # Limpiar para CSV
                grupo,
                motivo,
                remitente,
                contacto_numero,
                'whatsapp'
            ])
        
        logger.info(f"   💾 Oferta guardada en CSV: {titulo[:50]}...")
        
    except Exception as e:
        logger.error(f"❌ Error guardando en CSV: {e}")


# ============================================================
# FUNCIÓN PARA EXPORTAR ESTADÍSTICAS
# ============================================================

async def export_stats_to_csv(db: Database):
    """Exporta estadísticas completas a CSV para análisis"""
    stats_file = Path("estadisticas_diarias.csv")
    file_exists = stats_file.exists()
    
    stats = await db.get_stats()
    spam_stats = await db.get_spam_stats()
    
    try:
        with open(stats_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            if not file_exists:
                writer.writerow([
                    'fecha', 'mensajes_procesados', 'ofertas_encontradas', 
                    'spam_filtrado', 'cache_hits', 'api_calls'
                ])
            
            writer.writerow([
                date.today().isoformat(),
                stats.get('messages_processed', 0),
                stats.get('offers_found', 0),
                stats.get('spam_filtered', 0),
                stats.get('analysis_cache_hits', 0),
                stats.get('api_calls', 0)
            ])
        
        logger.info(f"📊 Estadísticas exportadas a {stats_file}")
        
    except Exception as e:
        logger.error(f"❌ Error exportando estadísticas: {e}")