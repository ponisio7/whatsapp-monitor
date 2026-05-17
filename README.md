# 📱 WhatsApp Monitor

Monitor automático de ofertas de empleo u otras aplicaciones adaptables en WhatsApp Web con inteligencia artificial.

## 📖 ¿Qué hace esto?

Este programa monitoriza WhatsApp Web automáticamente y detecta mensajes que contienen ofertas de empleo. Usa IA (DeepSeek) para analizar los mensajes y evitar falsos positivos.

## ⚙️ Leer

- [manual.html](manual.html)

## 📄 Licencia

MIT - Código abierto

📦 Comandos para descargar y configurar el proyecto
Opción 1: Clonar con HTTPS (recomendado para usuarios sin SSH)
bash

# 1. Clonar el repositorio
git clone https://github.com/ponisio7/whatsapp-monitor.git

# 2. Entrar al directorio del proyecto
cd whatsapp-monitor

# 3. Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Crear archivos de configuración (cada usuario debe crear el suyo)
cp config.example.py config.py  # Si tienes un archivo de ejemplo
# O crear manualmente config.py con sus propias credenciales

# 6. Ejecutar el proyecto
python main.py

Opción 2: Clonar con SSH (para usuarios con clave SSH configurada)
bash

git clone git@github.com:ponisio7/whatsapp-monitor.git
cd whatsapp-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

Opción 3: Descargar como ZIP (sin Git)
bash

# Alternativa para usuarios que no quieren usar Git
# 1. Ir a: https://github.com/ponisio7/whatsapp-monitor
# 2. Hacer clic en "Code" -> "Download ZIP"
# 3. Descomprimir el archivo
# 4. Seguir los pasos de configuración desde el paso 3 de la Opción 1
