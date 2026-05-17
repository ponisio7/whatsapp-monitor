# main_window.py - VERSIÓN COMPLETA CON VISOR DE OFERTAS
"""
WhatsApp Monitor - GUI Minimalista
Consola de log, contador de ofertas y configuración de API Key
"""
import asyncio
import sys
import threading
import logging
import os
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QFrame, QDialog, QLineEdit,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import uvloop
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except ImportError:
    pass


class APIConfigDialog(QDialog):
    """Diálogo para configurar la API Key de DeepSeek"""
    
    def __init__(self, current_key, parent=None):
        super().__init__(parent)
        self.current_key = current_key
        self.new_key = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("WhatsApp Monitor")
        self.setMinimumSize(250, 900)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
            QPushButton:disabled {
                background-color: #1E1E1E;
                color: #666666;
            }
            QPushButton#config_btn {
                background-color: #2196F3;
            }
            QPushButton#config_btn:hover {
                background-color: #42A5F5;
            }
            
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Contador
        counter_frame = QFrame()
        counter_frame.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        counter_layout = QVBoxLayout()
        
        counter_label = QLabel("🎯 OFERTAS ENCONTRADAS")
        counter_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #AAAAAA; cursor: pointer;")
        counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        counter_label.mousePressEvent = self.on_counter_clicked
        
        self.offer_display = QLabel("0")
        self.offer_display.setStyleSheet("font-size: 48px; font-weight: bold; color: #4CAF50; cursor: pointer;")
        self.offer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offer_display.mousePressEvent = self.on_counter_clicked
        
        counter_layout.addWidget(counter_label)
        counter_layout.addWidget(self.offer_display)
        counter_frame.setLayout(counter_layout)
        
        # ============================================================
        # BOTONES - SECCIÓN MODIFICADA CON BOTÓN DE ACTUALIZACIÓN
        # ============================================================
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.start_btn = QPushButton("▶ INICIAR")
        self.start_btn.clicked.connect(self.start_monitor)
        
       
        self.config_btn = QPushButton("🔑 CONFIGURAR API")
        self.config_btn.setObjectName("config_btn")
        self.config_btn.clicked.connect(self.configure_api)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.config_btn)
        buttons_layout.addStretch()
        # ============================================================
        
        # Log
        self.log_widget = LogWidget()
        
        main_layout.addWidget(counter_frame)
        main_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.log_widget, 1)
        
        central_widget.setLayout(main_layout)

    def mask_api_key(self, key):
        """Enmascarar la API Key para mostrar solo primeros y últimos caracteres"""
        if not key or len(key) < 10:
            return "*** No configurada ***"
        return f"{key[:8]}...{key[-4:]}"
    
    def toggle_visibility(self):
        """Alternar visibilidad de la nueva API Key"""
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def save_key(self):
        """Guardar la nueva API Key"""
        new_key = self.key_input.text().strip()
        
        if not new_key:
            QMessageBox.warning(self, "Advertencia", "Por favor ingresa una API Key válida")
            return
        
        if not new_key.startswith("sk-"):
            reply = QMessageBox.question(
                self, 
                "Confirmar",
                "La API Key no parece tener el formato correcto (debe empezar con 'sk-').\n"
                "¿Deseas continuar de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        self.new_key = new_key
        self.accept()


class OffersViewerDialog(QDialog):
    """Diálogo para mostrar las ofertas detectadas"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Ofertas Detectadas")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        self.load_offers()
    
    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QTableWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: none;
                gridline-color: #3D3D3D;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #3D3D3D;
                color: #FFFFFF;
                padding: 5px;
                border: 1px solid #4D4D4D;
            }
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                border-radius: 5px;
                font-family: monospace;
            }
            QPushButton {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4D4D4D;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Título y contador
        title_layout = QHBoxLayout()
        self.count_label = QLabel("Cargando ofertas...")
        self.count_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
        title_layout.addWidget(self.count_label)
        title_layout.addStretch()
        
        # Botón de refrescar
        refresh_btn = QPushButton("🔄 Refrescar")
        refresh_btn.clicked.connect(self.load_offers)
        title_layout.addWidget(refresh_btn)
        
        layout.addLayout(title_layout)
        
        # Crear tabs para diferentes vistas
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3D3D3D;
                background-color: #2D2D2D;
            }
            QTabBar::tab {
                background-color: #3D3D3D;
                color: #FFFFFF;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
            }
        """)
        
        # Tabla de ofertas
        self.table_widget = QTableWidget()
        self.table_widget.setSortingEnabled(True)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.itemDoubleClicked.connect(self.show_offer_details)
        
        # Tabla de texto plano (alternativa)
        self.text_widget = QTextEdit()
        self.text_widget.setFont(QFont("Monospace", 10))
        self.text_widget.setReadOnly(True)
        
        self.tab_widget.addTab(self.table_widget, "📋 Vista Tabla")
        self.tab_widget.addTab(self.text_widget, "📄 Vista Texto")
        
        layout.addWidget(self.tab_widget)
        
        # Botón de cerrar
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_offers(self):
        """Cargar ofertas desde el archivo CSV"""
        csv_path = Path("ofertas_detectadas.csv")
        
        if not csv_path.exists():
            self.count_label.setText("📭 No hay ofertas registradas aún")
            self.text_widget.setText("No se ha encontrado el archivo 'ofertas_detectadas.csv'\n\nLas ofertas aparecerán aquí cuando se detecten.")
            
            # Limpiar tabla
            self.table_widget.setRowCount(0)
            self.table_widget.setColumnCount(0)
            return
        
        try:
            # Intentar con pandas primero (si está instalado)
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                self.display_with_pandas(df)
            except ImportError:
                # Fallback a csv nativo
                self.display_with_csv(csv_path)
                
        except Exception as e:
            self.text_widget.setText(f"❌ Error al cargar ofertas: {str(e)}")
            self.count_label.setText("❌ Error al cargar")
    
    def display_with_pandas(self, df):
        """Mostrar usando pandas (más bonito)"""
        if df.empty:
            self.count_label.setText("📭 No hay ofertas registradas aún")
            self.text_widget.setText("No se han detectado ofertas todavía.\n\nLas ofertas aparecerán aquí cuando se detecten.")
            self.table_widget.setRowCount(0)
            return
        
        # Actualizar contador
        self.count_label.setText(f"🎯 Total de ofertas: {len(df)}")
        
        # Mostrar en texto plano
        text_content = []
        text_content.append("=" * 80)
        text_content.append(f"{'OFERTAS DETECTADAS':^80}")
        text_content.append("=" * 80)
        text_content.append("")
        
        for idx, row in df.iterrows():
            text_content.append(f"📌 OFERTA #{idx + 1}")
            for col in df.columns:
                text_content.append(f"   {col}: {row[col]}")
            text_content.append("-" * 80)
        
        self.text_widget.setText("\n".join(text_content))
        
        # Configurar tabla
        self.table_widget.setColumnCount(len(df.columns))
        self.table_widget.setHorizontalHeaderLabels(df.columns)
        
        self.table_widget.setRowCount(len(df))
        
        for i, row in df.iterrows():
            for j, col in enumerate(df.columns):
                item = QTableWidgetItem(str(row[col]))
                item.setToolTip(str(row[col]))
                self.table_widget.setItem(i, j, item)
        
        # Ajustar columnas
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        
        # Ordenar por fecha descendente si existe columna de fecha
        if 'fecha' in df.columns or 'timestamp' in df.columns:
            date_col = 'fecha' if 'fecha' in df.columns else 'timestamp'
            if date_col in df.columns:
                self.table_widget.sortItems(df.columns.get_loc(date_col), Qt.SortOrder.DescendingOrder)
    
    def display_with_csv(self, csv_path):
        """Mostrar usando csv nativo (sin pandas)"""
        offers = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for row in reader:
                offers.append(row)
        
        if not offers:
            self.count_label.setText("📭 No hay ofertas registradas aún")
            self.text_widget.setText("No se han detectado ofertas todavía.")
            return
        
        # Actualizar contador
        self.count_label.setText(f"🎯 Total de ofertas: {len(offers)}")
        
        # Mostrar en texto plano
        text_content = []
        text_content.append("=" * 80)
        text_content.append(f"{'OFERTAS DETECTADAS':^80}")
        text_content.append("=" * 80)
        text_content.append("")
        
        for idx, offer in enumerate(offers):
            text_content.append(f"📌 OFERTA #{idx + 1}")
            for key, value in offer.items():
                text_content.append(f"   {key}: {value}")
            text_content.append("-" * 80)
        
        self.text_widget.setText("\n".join(text_content))
        
        # Configurar tabla
        if headers:
            self.table_widget.setColumnCount(len(headers))
            self.table_widget.setHorizontalHeaderLabels(headers)
            
            self.table_widget.setRowCount(len(offers))
            
            for i, offer in enumerate(offers):
                for j, header in enumerate(headers):
                    item = QTableWidgetItem(offer.get(header, ""))
                    item.setToolTip(offer.get(header, ""))
                    self.table_widget.setItem(i, j, item)
            
            # Ajustar columnas
            self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.table_widget.horizontalHeader().setStretchLastSection(True)
    
    def show_offer_details(self, item):
        """Mostrar detalles completos de una oferta al hacer doble clic"""
        row = item.row()
        
        details_dialog = QDialog(self)
        details_dialog.setWindowTitle("Detalles de la Oferta")
        details_dialog.setModal(True)
        details_dialog.setMinimumSize(500, 400)
        details_dialog.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                border-radius: 5px;
                font-family: monospace;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Obtener datos de la fila
        details_text = []
        for col in range(self.table_widget.columnCount()):
            header = self.table_widget.horizontalHeaderItem(col).text()
            value = self.table_widget.item(row, col).text()
            details_text.append(f"<b>{header}:</b><br>{value}<br><br>")
        
        text_edit = QTextEdit()
        text_edit.setHtml("<br>".join(details_text))
        text_edit.setReadOnly(True)
        
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(details_dialog.accept)
        close_btn.setFixedWidth(100)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        details_dialog.setLayout(layout)
        details_dialog.exec()


class MonitorSignals(QObject):
    log_message = pyqtSignal(str, str)
    offer_count = pyqtSignal(int)
    status_changed = pyqtSignal(bool)


class LogWidget(QTextEdit):
    MAX_BLOCKS = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Monospace", 8))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: none;
            }
        """)
        
        self.colors = {
            "INFO": QColor("#4CAF50"),
            "WARNING": QColor("#FF9800"),
            "ERROR": QColor("#F44336"),
            "SUCCESS": QColor("#2196F3"),
            "OFFER": QColor("#FF5722")
        }
    
    def append_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.colors.get(level, QColor("#FFFFFF"))
        
        formatted = f'<span style="color: #888888;">[{timestamp}]</span> '
        formatted += f'<span style="color: {color.name()};">[{level}]</span> '
        formatted += f'<span style="color: #CCCCCC;">{message}</span>'
        
        self.append(formatted)
        
        doc = self.document()
        while doc.blockCount() > self.MAX_BLOCKS:
            cursor = QTextCursor(doc.begin())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.movePosition(QTextCursor.MoveOperation.NextBlock,
                                QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.monitor_thread = None
        self.is_running = False
        self.signals = MonitorSignals()
        self.offer_count_value = 0
        
        self.init_ui()
        self.connect_signals()
        self.load_current_api_key()
    
    def load_current_api_key(self):
        """Cargar la API Key actual del archivo .env"""
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
            current_key = os.getenv("DEEPSEEK_API_KEY", "")
            if current_key:
                self.signals.log_message.emit("API Key de DeepSeek cargada correctamente", "SUCCESS")
            else:
                self.signals.log_message.emit("⚠️ No se encontró API Key de DeepSeek", "WARNING")
        else:
            self.signals.log_message.emit("⚠️ Archivo .env no encontrado", "WARNING")
    
    def update_api_key(self, new_key):
        """Actualizar la API Key en el archivo .env y en memoria"""
        try:
            env_path = Path(".env")
            
            # Cargar variables existentes
            if env_path.exists():
                load_dotenv(env_path)
            
            # Actualizar o crear el archivo .env
            set_key(str(env_path), "DEEPSEEK_API_KEY", new_key)
            
            # Actualizar en memoria
            os.environ["DEEPSEEK_API_KEY"] = new_key
            
            # Recargar dotenv para asegurar consistencia
            load_dotenv(env_path, override=True)
            
            # Forzar recarga del módulo config para que tome el nuevo valor
            import config
            import importlib
            importlib.reload(config)
            
            self.signals.log_message.emit("✅ API Key actualizada correctamente", "SUCCESS")
            
            # Mostrar mensaje de éxito con key enmascarada
            masked = f"{new_key[:8]}...{new_key[-4:]}" if len(new_key) > 12 else "***"
            self.signals.log_message.emit(f"Nueva API Key configurada: {masked}", "INFO")
            
            return True
            
        except Exception as e:
            self.signals.log_message.emit(f"❌ Error al guardar API Key: {e}", "ERROR")
            return False

    def init_ui(self):
        self.setWindowTitle("WhatsApp Monitor")
        self.setMinimumSize(250, 900)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
            QPushButton:disabled {
                background-color: #1E1E1E;
                color: #666666;
            }
            QPushButton#config_btn {
                background-color: #2196F3;
            }
            QPushButton#config_btn:hover {
                background-color: #42A5F5;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Contador
        counter_frame = QFrame()
        counter_frame.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        counter_layout = QVBoxLayout()
        
        counter_label = QLabel("🎯 OFERTAS ENCONTRADAS")
        counter_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #AAAAAA; cursor: pointer;")
        counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Hacer clickeable el label
        counter_label.mousePressEvent = self.on_counter_clicked
        
        self.offer_display = QLabel("0")
        self.offer_display.setStyleSheet("font-size: 48px; font-weight: bold; color: #4CAF50; cursor: pointer;")
        self.offer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Hacer clickeable el número
        self.offer_display.mousePressEvent = self.on_counter_clicked
        
        counter_layout.addWidget(counter_label)
        counter_layout.addWidget(self.offer_display)
        counter_frame.setLayout(counter_layout)
        
        # Botones
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.start_btn = QPushButton("▶ INICIAR")
        self.start_btn.clicked.connect(self.start_monitor)

        
                
        self.config_btn = QPushButton("🔑 CONFIGURAR API")
        self.config_btn.setObjectName("config_btn")
        self.config_btn.clicked.connect(self.configure_api)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.start_btn)

        buttons_layout.addWidget(self.config_btn)
        buttons_layout.addStretch()
        
        # Log
        self.log_widget = LogWidget()
        
        main_layout.addWidget(counter_frame)
        main_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.log_widget, 1)
        
        central_widget.setLayout(main_layout)
    
    def on_counter_clicked(self, event):
        """Mostrar el diálogo de ofertas cuando se hace clic en el contador"""
        dialog = OffersViewerDialog(self)
        dialog.exec()
    
    def configure_api(self):
        """Abrir diálogo de configuración de API Key"""
        current_key = os.getenv("DEEPSEEK_API_KEY", "")
        
        dialog = APIConfigDialog(current_key, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.new_key:
            if self.update_api_key(dialog.new_key):
                QMessageBox.information(
                    self,
                    "Configuración Guardada",
                    "La API Key se ha guardado correctamente.\n"
                    "Reinicia el monitor para aplicar los cambios."
                )
    
    def connect_signals(self):
        self.signals.log_message.connect(self.log_widget.append_log)
        self.signals.offer_count.connect(self.update_offer_count)
        self.signals.status_changed.connect(self.update_buttons)
    
    def update_offer_count(self, count: int):
        self.offer_count_value = count
        self.offer_display.setText(str(count))
    
    def update_buttons(self, running: bool):
        self.start_btn.setEnabled(not running)
        
    
    def clear_log(self):
        self.log_widget.clear()
        self.log_widget.append_log("Log limpiado", "INFO")
    
    def start_monitor(self):
        if self.is_running:
            return
        
        # Verificar que existe API Key antes de iniciar
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            reply = QMessageBox.question(
                self,
                "API Key no configurada",
                "No se encontró una API Key de DeepSeek configurada.\n"
                "¿Deseas configurarla ahora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.configure_api()
                # Verificar nuevamente después de configurar
                api_key = os.getenv("DEEPSEEK_API_KEY", "")
                if not api_key:
                    self.signals.log_message.emit("❌ No se puede iniciar sin API Key", "ERROR")
                    return
            else:
                self.signals.log_message.emit("❌ No se puede iniciar sin API Key", "ERROR")
                return
        
        self.is_running = True
        self.signals.status_changed.emit(True)
        self.signals.log_message.emit("=" * 50, "INFO")
        self.signals.log_message.emit("Iniciando monitor de WhatsApp...", "INFO")
        self.signals.log_message.emit("Modo Anti-Detección Avanzada activado", "SUCCESS")
        self.signals.log_message.emit("=" * 50, "INFO")
        
        self.monitor_thread = threading.Thread(target=self.run_monitor, daemon=True)
        self.monitor_thread.start()
    
    def run_monitor(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._run_monitor_async())
        except Exception as e:
            self.signals.log_message.emit(f"Error en monitor: {e}", "ERROR")
            logger.exception("Error en monitor thread")
        finally:
            loop.close()
            self.is_running = False
            self.signals.status_changed.emit(False)
    
    async def _run_monitor_async(self):
        from main import JobMonitor
        
        class GUIJobMonitor(JobMonitor):
            def __init__(self, signals):
                super().__init__()
                self.signals = signals
                self.offer_count = 0
            
            async def _enviar_alerta(self, mensaje: str, titulo: str, grupo: str, motivo: str):
                self.signals.log_message.emit(f"🎯 OFERTA: {titulo}", "OFFER")
                self.signals.log_message.emit(f"   📱 {grupo}", "INFO")
                self.signals.log_message.emit(f"   📝 {mensaje[:100]}...", "INFO")
                self.offer_count += 1
                self.signals.offer_count.emit(self.offer_count)
                await super()._enviar_alerta(mensaje, titulo, grupo, motivo)
        
        monitor = GUIJobMonitor(self.signals)
        
        # Redirigir logs
        class GUILogHandler(logging.Handler):
            def __init__(self, signals):
                super().__init__()
                self.signals = signals
                self.setFormatter(logging.Formatter('%(message)s'))
            
            def emit(self, record):
                msg = self.format(record)
                level = record.levelname
                self.signals.log_message.emit(msg, level)
        
        handler = GUILogHandler(self.signals)
        logging.getLogger().addHandler(handler)
        
        try:
            await monitor.init()
            self.signals.log_message.emit("Monitor inicializado correctamente", "SUCCESS")
            await monitor.run()
        except asyncio.CancelledError:
            self.signals.log_message.emit("Monitor detenido", "INFO")
        except Exception as e:
            self.signals.log_message.emit(f"Error fatal: {e}", "ERROR")
            logger.exception("Error en monitor")
        finally:
            logging.getLogger().removeHandler(handler)
            await monitor.close()
    
    def stop_monitor(self):
        if self.is_running:
            self.is_running = False
            self.signals.log_message.emit("Deteniendo monitor...", "WARNING")
            self.signals.status_changed.emit(False)

    # En main_window.py, dentro de la clase MainWindow

    def check_for_updates(self):
        """Verifica y aplica actualizaciones"""
        try:
            # Importar aquí para evitar dependencia circular
            from updater import UpdateDialog
            
            self.signals.log_message.emit("🔄 Abriendo actualizador...", "INFO")
            
            dialog = UpdateDialog(self)
            dialog.exec()
            
        except ImportError as e:
            QMessageBox.warning(
                self,
                "Actualizador no disponible",
                f"El módulo de actualización no está instalado correctamente.\n\n"
                f"Error: {e}\n\n"
                f"Asegúrate de que el archivo 'updater.py' existe en la misma carpeta."
            )
            self.signals.log_message.emit("❌ Actualizador no disponible - archivo updater.py faltante", "ERROR")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo abrir el actualizador: {e}"
            )
            self.signals.log_message.emit(f"❌ Error al abrir actualizador: {e}", "ERROR")

    def closeEvent(self, event):
        self.stop_monitor()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()