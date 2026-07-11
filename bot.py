import discord
from discord.ext import tasks
import json
import os
import requests
import asyncio
from datetime import datetime

# ======================================================
# CONFIGURACIÓN DE EXPLOITS (MÁS DE 60)
# ======================================================
EXPLOITS_A_VIGILAR = [
    # Los más populares
    "Solara", "Wave", "AWP", "Vega X", "Delta",
    "Hydrogen", "Fluxus", "Electron", "Nihon", "Celestial",
    "Velocity", "Oxygen U", "Comet", "Zypher",
    
    # Clásicos y otros conocidos
    "Krnl", "Synapse X", "Script-Ware", "Evon", "JJSploit",
    "Coco", "Zen", "Borealis", "Sirius", "Xeno",
    "Rise", "Valyse", "Elysian", "Novus", "Vynixius",
    "Seliware", "Exoliner", "Neo", "Trigon", "Eclipse",
    "Oblivion", "Fates", "Arceus X", "Mystic", "Aurora",
    "Nexus", "Quantum", "Phantom", "Infinity", "Legendary",
    "Carbon", "X-Code", "Skrypt", "Vortex", "Horizon",
    "Genesis", "Apex", "Nova", "Stellar", "Pandora",
    "Zeus", "Hades", "Ares", "Atlas", "Eden",
    "Frost", "Storm", "Blaze", "Shadow", "Light", "Dark"
]
# ======================================================

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID")) if os.getenv("CHANNEL_ID") else None
DATA_FILE = "estado_anterior.json"

# Colores para los embeds
COLOR_ONLINE = 0x00FF00      # Verde
COLOR_OFFLINE = 0xFF0000     # Rojo
COLOR_PATCHED = 0xFFA500     # Naranja
COLOR_DEFAULT = 0x5865F2     # Azul de Discord

def obtener_estados():
    """Obtiene el estado actual desde la API de WEAO con reintentos"""
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            url = "https://api.weao.xyz/v1/exploits"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, dict) and "exploits" in data:
                return data["exploits"]
            elif isinstance(data, list):
                return data
            else:
                print(f"⚠️ Formato de datos inesperado: {type(data)}")
                return []
                
        except requests.exceptions.Timeout:
            print(f"⏰ Intento {intento+1}/{max_intentos} - Timeout, reintentando...")
        except requests.exceptions.ConnectionError:
            print(f"🔌 Intento {intento+1}/{max_intentos} - Error de conexión, reintentando...")
        except Exception as e:
            print(f"❌ Error al obtener datos: {e}")
            if intento == max_intentos - 1:
                return None
            asyncio.sleep(2)
    
    return None

def cargar_cache():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def guardar_cache(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"❌ Error al guardar cache: {e}")

def buscar_exploit_en_datos(nombre_buscar, datos):
    """Busca un exploit por nombre en la lista devuelta por la API"""
    nombre_buscar = nombre_buscar.lower().strip()
    
    for item in datos:
        if isinstance(item, dict):
            for clave in ["name", "nombre", "title", "exploit"]:
                if clave in item and item[clave]:
                    nombre_actual = str(item[clave]).lower().strip()
                    if nombre_actual == nombre_buscar:
                        return item
    return None

def extraer_download(item):
    for clave in ["download_url", "download", "link", "url", "download_link", "dl"]:
        if clave in item and item[clave] and isinstance(item[clave], str):
            if item[clave].startswith("http"):
                return item[clave]
    return "Sin enlace"

def obtener_color_estado(estado):
    estado_lower = estado.lower() if estado else ""
    if "online" in estado_lower or "up" in estado_lower:
        return COLOR_ONLINE
    elif "offline" in estado_lower or "down" in estado_lower:
        return COLOR_OFFLINE
    elif "patched" in estado_lower or "fix" in estado_lower:
        return COLOR_PATCHED
    else:
        return COLOR_DEFAULT

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    print(f"📋 Monitoreando {len(EXPLOITS_A_VIGILAR)} exploits")
    print("⏳ Iniciando verificación en 10 segundos...")
    await asyncio.sleep(10)
    verificar_estados.start()

@tasks.loop(seconds=90)
async def verificar_estados():
    if not CHANNEL_ID:
        print("❌ CHANNEL_ID no configurado")
        return
        
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"❌ No se encontró el canal con ID {CHANNEL_ID}")
        return

    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Verificando estados...")
    
    datos_actuales = obtener_estados()
    if datos_actuales is None:
        print("⚠️ No se pudieron obtener datos, reintentando en el siguiente ciclo...")
        return
    
    if not datos_actuales:
        print("⚠️ La API devolvió una lista vacía")
        return

    cache_anterior = cargar_cache()
    cambios_detectados = []
    exploits_encontrados = 0

    for exploit_name in EXPLOITS_A_VIGILAR:
        info_actual = buscar_exploit_en_datos(exploit_name, datos_actuales)
        
        if not info_actual:
            continue
        
        exploits_encontrados += 1
        
        nombre = info_actual.get("name", info_actual.get("nombre", exploit_name))
        estado = info_actual.get("status", info_actual.get("estado", "Desconocido"))
        version = info_actual.get("version", info_actual.get("ver", info_actual.get("versión", "N/A")))
        download = extraer_download(info_actual)
        last_updated = info_actual.get("last_updated", info_actual.get("updated_at", "Desconocido"))
        platform = info_actual.get("platform", info_actual.get("tipo", "N/A"))

        clave_cache = nombre.lower()
        estado_anterior = cache_anterior.get(clave_cache, {})

        if estado_anterior:
            cambio_detectado = False
            razon_cambio = []
            
            if estado_anterior.get("status") != estado:
                cambio_detectado = True
                razon_cambio.append(f"Estado: {estado_anterior.get('status')} → {estado}")
            
            if estado_anterior.get("version") != version:
                cambio_detectado = True
                razon_cambio.append(f"Versión: {estado_anterior.get('version')} → {version}")
            
            if cambio_detectado:
                cambios_detectados.append({
                    "nombre": nombre,
                    "estado_anterior": estado_anterior.get("status"),
                    "estado_nuevo": estado,
                    "version_anterior": estado_anterior.get("version"),
                    "version_nueva": version,
                    "download": download,
                    "razon": " | ".join(razon_cambio),
                    "platform": platform,
                    "last_updated": last_updated
                })
                print(f"📌 Cambio detectado en {nombre}: {razon_cambio}")

        cache_anterior[clave_cache] = {
            "status": estado,
            "version": version,
            "download": download,
            "platform": platform,
            "last_updated": last_updated
        }

    guardar_cache(cache_anterior)
    print(f"📊 {exploits_encontrados}/{len(EXPLOITS_A_VIGILAR)} exploits encontrados en la API")

    for cambio in cambios_detectados:
        try:
            color = obtener_color_estado(cambio["estado_nuevo"])
            
            embed = discord.Embed(
                title=f"🔄 Actualización en {cambio['nombre']}",
                description=f"**{cambio['nombre']}** ha tenido un cambio importante.",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📊 Cambio detectado", value=cambio["razon"], inline=False)
            embed.add_field(name="Estado anterior", value=cambio["estado_anterior"] or "Desconocido", inline=True)
            embed.add_field(name="Estado actual", value=cambio["estado_nuevo"], inline=True)
            embed.add_field(name="Versión anterior", value=cambio["version_anterior"] or "N/A", inline=True)
            embed.add_field(name="Versión actual", value=cambio["version_nueva"], inline=True)
            
            if cambio["platform"] and cambio["platform"] != "N/A":
                embed.add_field(name="🖥️ Plataforma", value=cambio["platform"], inline=True)
            if cambio["last_updated"] and cambio["last_updated"] != "Desconocido":
                embed.add_field(name="📅 Última actualización", value=cambio["last_updated"], inline=True)
            
            if cambio["download"] and cambio["download"] != "Sin enlace":
                embed.add_field(name="🔗 Descarga", value=f"[Haz clic aquí para descargar]({cambio['download']})", inline=False)
            else:
                embed.add_field(name="🔗 Descarga", value="No disponible oficialmente", inline=False)

            embed.set_footer(text="Roblox Exploit Tracker | Powered by WEAO")
            
            await channel.send(content="@everyone 🚨 ¡Nueva actualización disponible!", embed=embed)
            print(f"📢 Alerta enviada para {cambio['nombre']}")
            
        except Exception as e:
            print(f"❌ Error al enviar embed para {cambio['nombre']}: {e}")

@verificar_estados.before_loop
async def before_verificar():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR CRÍTICO: DISCORD_TOKEN no configurado")
        exit(1)
    if not CHANNEL_ID:
        print("❌ ERROR CRÍTICO: CHANNEL_ID no configurado")
        exit(1)
    
    print("=" * 50)
    print("🤖 INICIANDO ROBLOX EXPLOIT TRACKER")
    print(f"📋 Monitoreando {len(EXPLOITS_A_VIGILAR)} exploits")
    print(f"📢 Canal objetivo: {CHANNEL_ID}")
    print("=" * 50)
    bot.run(TOKEN)
