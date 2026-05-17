# stealth_setup.py - VERSIÓN CORREGIDA
import logging
import random
from playwright.async_api import Page, BrowserContext

logger = logging.getLogger(__name__)

async def setup_stealth_browser(context: BrowserContext, page: Page):
    """Configura protección anti-detección de nivel militar"""
    
    # Configurar Headers HTTP consistentes (Client Hints)
    await context.set_extra_http_headers({
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-platform-version": '"15.0.0"',
        "sec-ch-ua-model": '""',
        "sec-ch-ua-bitness": '"64"',
        "sec-ch-ua-full-version": '"122.0.6261.129"',
    })
    
    # Generar valores estables para la sesión (NO cambian durante la ejecución)
    session_hardware_concurrency = random.choice([4, 6, 8, 10, 12, 16])
    session_device_memory = random.choice([4, 8, 16])
    session_rtt = random.randint(20, 70)
    session_downlink = round(random.uniform(5, 25), 1)
    
    # Determinar effectiveType fuera del f-string
    effective_type = '4g' if session_downlink > 10 else '3g'
    
    # Script de stealth avanzado
    init_script = f"""
        // ============================================
        // 1. CORRECCIÓN DE PROTOTIPOS (PluginArray)
        // ============================================
        
        const createWithProto = (obj, protoConstructor) => {{
            Object.setPrototypeOf(obj, protoConstructor.prototype);
            return obj;
        }};
        
        const isWindows = navigator.userAgent.includes('Windows');
        const pluginsList = isWindows ? [
            {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
            {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'Google Chrome PDF Viewer' }},
            {{ name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }}
        ] : [
            {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
            {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' }},
            {{ name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }}
        ];
        
        const pluginArray = createWithProto(pluginsList, PluginArray);
        pluginArray.refresh = () => {{}};
        pluginArray.item = (index) => pluginsList[index];
        pluginArray.namedItem = (name) => pluginsList.find(p => p.name === name);
        
        Object.defineProperty(navigator, 'plugins', {{
            get: () => pluginArray,
            configurable: false
        }});
        
        // ============================================
        // 2. MIMETYPES COHERENTES CON PLUGINS
        // ============================================
        
        const mimeTypesList = [
            {{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: pluginsList[0] }},
            {{ type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Google Chrome PDF Viewer', enabledPlugin: pluginsList[1] }},
            {{ type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable', enabledPlugin: pluginsList[2] }}
        ];
        
        const mimeTypeArray = createWithProto(mimeTypesList, MimeTypeArray);
        mimeTypeArray.namedItem = (type) => mimeTypesList.find(m => m.type === type);
        mimeTypeArray.item = (index) => mimeTypesList[index];
        
        Object.defineProperty(navigator, 'mimeTypes', {{
            get: () => mimeTypeArray,
            configurable: false
        }});
        
        // ============================================
        // 3. CANVAS FINGERPRINTING CON RUIDO ENTERO Y CONSISTENTE
        // ============================================
        
        const sessionSeed = Date.now() % 10000;
        const pseudoRandom = (i) => {{
            const x = Math.sin(sessionSeed + i) * 10000;
            return x - Math.floor(x);
        }};
        
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
            if (this.width > 100 && this.height > 100) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    const imageData = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 100) {{
                        if (pseudoRandom(i) < 0.3) {{
                            const shift = Math.floor(pseudoRandom(i + 1000) * 3) - 1;
                            imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + shift));
                        }}
                    }}
                    ctx.putImageData(imageData, 0, 0);
                }}
            }}
            return originalToDataURL.call(this, type, quality);
        }};
        
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
            const result = originalGetImageData.call(this, x, y, w, h);
            for (let i = 0; i < result.data.length; i += 200) {{
                if (pseudoRandom(i + 2000) < 0.2) {{
                    const shift = Math.floor(pseudoRandom(i + 3000) * 3) - 1;
                    result.data[i] = Math.max(0, Math.min(255, result.data[i] + shift));
                }}
            }}
            return result;
        }};
        
        // ============================================
        // 4. WEBGL SPOOFING
        // ============================================
        
        const spoofWebGL = (proto) => {{
            if (!proto) return;
            const getParameter = proto.getParameter;
            proto.getParameter = function(parameter) {{
                const spoofed = {{
                    37445: isWindows ? 'Intel Inc.' : 'NVIDIA Corporation',
                    37446: isWindows ? 'Intel Iris Xe Graphics' : 'NVIDIA GeForce RTX 3060',
                    7936: 'WebGL 1.0 (OpenGL ES 2.0 Chromium)',
                    7937: 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)'
                }};
                if (spoofed[parameter]) return spoofed[parameter];
                return getParameter.call(this, parameter);
            }};
            
            const getSupportedExtensions = proto.getSupportedExtensions;
            proto.getSupportedExtensions = function() {{
                const extensions = getSupportedExtensions.call(this);
                return extensions.filter(ext => !ext.includes('debug') && !ext.includes('WEBGL_debug'));
            }};
        }};
        
        if (typeof WebGLRenderingContext !== 'undefined') {{
            spoofWebGL(WebGLRenderingContext.prototype);
        }}
        if (typeof WebGL2RenderingContext !== 'undefined') {{
            spoofWebGL(WebGL2RenderingContext.prototype);
        }}
        
        // ============================================
        // 5. HARDWARE CONCURRENCY Y MEMORY
        // ============================================
        
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => {session_hardware_concurrency},
            configurable: true
        }});
        
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: () => {session_device_memory},
            configurable: true
        }});
        
        // ============================================
        // 6. CONNECTION API
        // ============================================
        
        if (navigator.connection) {{
            Object.defineProperty(navigator.connection, 'rtt', {{
                get: () => {session_rtt},
                configurable: true
            }});
            
            Object.defineProperty(navigator.connection, 'downlink', {{
                get: () => {session_downlink},
                configurable: true
            }});
            
            Object.defineProperty(navigator.connection, 'effectiveType', {{
                get: () => '{effective_type}',
                configurable: true
            }});
        }}
        
        // ============================================
        // 7. PERMISSIONS API
        // ============================================
        
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => {{
            const responses = {{
                'notifications': Notification.permission,
                'camera': 'prompt',
                'microphone': 'prompt',
                'geolocation': 'prompt',
                'clipboard-read': 'prompt',
                'clipboard-write': 'granted'
            }};
            if (responses[parameters.name]) {{
                return Promise.resolve({{
                    state: responses[parameters.name],
                    onchange: null
                }});
            }}
            return originalQuery(parameters);
        }};
        
        // ============================================
        // 8. BLOQUEO DE APIs SOSPECHOSAS
        // ============================================
        
        if (navigator.bluetooth) {{
            Object.defineProperty(navigator, 'bluetooth', {{
                get: () => undefined,
                configurable: true
            }});
        }}
        
        if (navigator.usb) {{
            Object.defineProperty(navigator, 'usb', {{
                get: () => undefined,
                configurable: true
            }});
        }}
        
        // ============================================
        // 9. WEBDRIVER Y PROPIEDADES DE AUTOMATION
        // ============================================
        
        delete navigator.__proto__.webdriver;
        Object.defineProperty(navigator, 'webdriver', {{
            get: () => undefined,
            configurable: true
        }});
        
        if (!window.chrome) window.chrome = {{}};
        window.chrome.app = {{
            isInstalled: false,
            InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
            RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }}
        }};
        
        window.chrome.runtime = {{
            id: '',
            connect: () => {{}},
            sendMessage: () => {{}},
            getManifest: () => ({{ version: '' }})
        }};
        
        // ============================================
        // 10. LANGUAGES Y LOCALE
        // ============================================
        
        Object.defineProperty(navigator, 'languages', {{
            get: () => ['es-ES', 'es', 'en-US', 'en'],
            configurable: true
        }});
        
        Object.defineProperty(navigator, 'language', {{
            get: () => 'es-ES',
            configurable: true
        }});
        
        // ============================================
        // 11. MOUSE POSITION INICIALIZADA
        // ============================================
        
        if (!window.mouseX) window.mouseX = Math.random() * 800 + 200;
        if (!window.mouseY) window.mouseY = Math.random() * 600 + 200;
        
        document.addEventListener('mousemove', (e) => {{
            window.mouseX = e.clientX;
            window.mouseY = e.clientY;
        }});
        
        // ============================================
        // 12. SIMULACIÓN DE EVENTOS DE FOCO/BLUR
        // ============================================
        
        let focusTimeout = null;
        const simulateBlurFocus = () => {{
            if (Math.random() < 0.0005) {{
                window.dispatchEvent(new Event('blur'));
                setTimeout(() => {{
                    window.dispatchEvent(new Event('focus'));
                }}, Math.random() * 500 + 100);
            }}
            focusTimeout = setTimeout(simulateBlurFocus, 10000);
        }};
        simulateBlurFocus();
        
        // ============================================
        // 13. MICRO-MOVIMIENTOS DE RATÓN
        // ============================================
        
        let lastMouseMove = Date.now();
        let idleInterval = null;
        
        const startIdleMouseMoves = () => {{
            if (idleInterval) clearInterval(idleInterval);
            idleInterval = setInterval(() => {{
                const now = Date.now();
                if (now - lastMouseMove > 60000 && window.mouseX) {{
                    const deltaX = (Math.random() - 0.5) * 6;
                    const deltaY = (Math.random() - 0.5) * 6;
                    const newX = Math.max(10, Math.min(window.innerWidth - 10, window.mouseX + deltaX));
                    const newY = Math.max(10, Math.min(window.innerHeight - 100, window.mouseY + deltaY));
                    
                    const event = new MouseEvent('mousemove', {{
                        clientX: newX,
                        clientY: newY,
                        bubbles: true
                    }});
                    document.dispatchEvent(event);
                    window.mouseX = newX;
                    window.mouseY = newY;
                }}
            }}, 30000);
        }};
        
        document.addEventListener('mousemove', () => {{
            lastMouseMove = Date.now();
        }});
        startIdleMouseMoves();
    """
    
    await page.add_init_script(init_script)
    
    logger.info("=" * 50)
    logger.info("🛡️ STEALTH NIVEL MILITAR ACTIVADO")
    logger.info(f"   Hardware Concurrency: {session_hardware_concurrency} cores")
    logger.info(f"   Device Memory: {session_device_memory} GB")
    logger.info(f"   Network RTT: {session_rtt}ms | Downlink: {session_downlink}Mbps")
    logger.info("   ✓ PluginArray + MimeTypes con prototipos correctos")
    logger.info("   ✓ Canvas fingerprinting con ruido entero")
    logger.info("   ✓ WebGL1 + WebGL2 spoofed")
    logger.info("   ✓ Micro-movimientos de ratón durante inactividad")
    logger.info("=" * 50)
    
    return page