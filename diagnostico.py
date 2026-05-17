import asyncio
from playwright.async_api import async_playwright

async def diagnosticar():
    async with async_playwright() as p:
        print("🔍 Diagnóstico de WhatsApp Web")
        print("="*50)
        
        # Lanzar navegador
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./session_wa_jobs",
            headless=False,
            args=["--start-maximized"]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("🌐 Cargando WhatsApp Web...")
        await page.goto("https://web.whatsapp.com")
        
        input("\n📱 Escanea el QR si es necesario, luego presiona ENTER...")
        
        # Verificar elementos
        print("\n📊 Verificando elementos de la interfaz:")
        
        # Lista de selectores a probar
        selectores = [
            ('Caja de texto principal', 'div[contenteditable="true"]'),
            ('Footer con caja', 'footer div[contenteditable="true"]'),
            ('Role textbox', 'div[role="textbox"]'),
            ('Compose box testid', '[data-testid="conversation-compose-box"]'),
            ('Input message', 'div[data-tab="10"]'),
            ('Mensaje aria-label', 'div[aria-label="Mensaje"]'),
            ('Lexical editor', 'div[data-lexical-editor="true"]'),
            ('Panel de chat', '#main'),
        ]
        
        for nombre, selector in selectores:
            try:
                elemento = await page.query_selector(selector)
                if elemento:
                    visible = await elemento.is_visible()
                    print(f"   ✅ {nombre}: {selector} - VISIBLE" if visible else f"   ⚠️ {nombre}: {selector} - EXISTE pero NO visible")
                else:
                    print(f"   ❌ {nombre}: {selector} - NO ENCONTRADO")
            except Exception as e:
                print(f"   ❌ {nombre}: Error - {e}")
        
        # Verificar URL actual
        print(f"\n🔗 URL actual: {page.url}")
        
        # Tomar screenshot
        await page.screenshot(path="diagnostico_whatsapp.png")
        print("📸 Screenshot guardado: diagnostico_whatsapp.png")
        
        input("\nPresiona ENTER para cerrar...")
        await context.close()

asyncio.run(diagnosticar())