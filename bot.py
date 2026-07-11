import discord
from discord import app_commands
from discord.ext import tasks
from discord.ui import View, Select, Button
import json
import os
import requests
import asyncio
from datetime import datetime

# ================= CONFIGURACIÓN GLOBAL =================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN no configurado en variables de entorno")

DEFAULT_INTERVAL = 90
DATA_FILE = "estado_anterior.json"
CONFIG_FILE = "config.json"

# Lista global de exploits (puedes ampliarla o reducirla)
GLOBAL_EXPLOITS = [
    "Solara", "Wave", "AWP", "Vega X", "Delta",
    "Hydrogen", "Fluxus", "Electron", "Nihon", "Celestial",
    "Velocity", "Oxygen U", "Comet", "Zypher",
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

# Emojis (usaremos las URLs como imágenes en los embeds)
EMOJI_GREEN_DOT = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
EMOJI_GREEN_ARROW = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"
EMOJI_SUCCESS = "https://cdn.discordapp.com/emojis/1525379448768303207.webp?size=100&animated=true"
EMOJI_LINK = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"  # Reutilizo la flecha

# Colores para embeds
COLOR_ONLINE = 0x00FF00
COLOR_OFFLINE = 0xFF0000
COLOR_PATCHED = 0xFFA500
COLOR_DEFAULT = 0x5865F2

# ================= FUNCIONES DE ARCHIVOS =================
def cargar_json(ruta, por_defecto=None):
    if por_defecto is None:
        por_defecto = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return por_defecto
    return por_defecto

def guardar_json(ruta, datos):
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error guardando {ruta}: {e}")
        return False

# ================= FUNCIONES DE API =================
def obtener_estados():
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
                return []
        except Exception as e:
            print(f"⏰ Intento {intento+1}/{max_intentos} falló: {e}")
            if intento == max_intentos - 1:
                return None
            asyncio.sleep(2)
    return None

def buscar_exploit(nombre, datos):
    nombre = nombre.lower().strip()
    for item in datos:
        if isinstance(item, dict):
            for clave in ["name", "nombre", "title", "exploit"]:
                if clave in item and item[clave]:
                    if str(item[clave]).lower().strip() == nombre:
                        return item
    return None

def extraer_download(item):
    for clave in ["download_url", "download", "link", "url", "download_link", "dl"]:
        if clave in item and item[clave] and isinstance(item[clave], str):
            if item[clave].startswith("http"):
                return item[clave]
    return "Sin enlace"

def obtener_color_estado(estado):
    e = estado.lower() if estado else ""
    if "online" in e or "up" in e:
        return COLOR_ONLINE
    elif "offline" in e or "down" in e:
        return COLOR_OFFLINE
    elif "patched" in e or "fix" in e:
        return COLOR_PATCHED
    return COLOR_DEFAULT

# ================= BOT Y CONFIGURACIÓN =================
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

config_servidores = cargar_json(CONFIG_FILE)
cache_estados = cargar_json(DATA_FILE)

def get_server_config(guild_id):
    guild_id = str(guild_id)
    if guild_id not in config_servidores:
        config_servidores[guild_id] = {
            "canal_id": None,
            "rol_id": None,
            "activo": False,
            "intervalo": DEFAULT_INTERVAL,
            "exploits": GLOBAL_EXPLOITS.copy()
        }
        guardar_json(CONFIG_FILE, config_servidores)
    return config_servidores[guild_id]

def save_server_config(guild_id, config):
    guild_id = str(guild_id)
    config_servidores[guild_id] = config
    guardar_json(CONFIG_FILE, config_servidores)

# ================= VISTA PARA CONFIGURACIÓN (con botones y selector) =================
class ConfigView(View):
    def __init__(self, guild_id, current_config):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.guild_id = guild_id
        self.config = current_config
        self.guild = bot.get_guild(int(guild_id))
        self.add_item(ChannelSelect(self))
        self.add_item(RolSelect(self))
        self.add_item(ToggleButton(self))
        self.add_item(SaveButton(self))

class ChannelSelect(Select):
    def __init__(self, parent):
        self.parent = parent
        # Obtener canales de texto donde el bot tiene permisos
        channels = []
        for ch in parent.guild.text_channels:
            perms = ch.permissions_for(parent.guild.me)
            if perms.send_messages and perms.embed_links:
                label = f"#{ch.name}"
                if ch.id == parent.config.get("canal_id"):
                    label += " ✅"
                channels.append(
                    discord.SelectOption(
                        label=label[:100],
                        value=str(ch.id),
                        default=(ch.id == parent.config.get("canal_id"))
                    )
                )
        if not channels:
            channels.append(discord.SelectOption(label="No hay canales disponibles", value="", default=True))
        super().__init__(placeholder="Selecciona el canal de alertas", options=channels, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected = int(self.values[0])
        self.parent.config["canal_id"] = selected
        await interaction.response.send_message(f"✅ Canal seleccionado: <#{selected}>", ephemeral=True)

class RolSelect(Select):
    def __init__(self, parent):
        self.parent = parent
        roles = []
        for rol in parent.guild.roles:
            if rol.name != "@everyone":
                label = rol.name[:100]
                if rol.id == parent.config.get("rol_id"):
                    label += " ✅"
                roles.append(
                    discord.SelectOption(
                        label=label,
                        value=str(rol.id),
                        default=(rol.id == parent.config.get("rol_id"))
                    )
                )
        # Opción para "Sin rol" (usará @everyone)
        roles.append(discord.SelectOption(label="Sin rol (usar @everyone)", value="0", default=(parent.config.get("rol_id") is None)))
        super().__init__(placeholder="Selecciona el rol a mencionar (opcional)", options=roles, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected = int(self.values[0])
        self.parent.config["rol_id"] = selected if selected != 0 else None
        msg = "Rol seleccionado: <@&{}>".format(selected) if selected != 0 else "Se usará @everyone"
        await interaction.response.send_message(f"✅ {msg}", ephemeral=True)

class ToggleButton(Button):
    def __init__(self, parent):
        self.parent = parent
        activo = parent.config.get("activo", False)
        label = "✅ Desactivar alertas" if activo else "❌ Activar alertas"
        style = discord.ButtonStyle.danger if activo else discord.ButtonStyle.success
        super().__init__(label=label, style=style, custom_id="toggle_alerts")

    async def callback(self, interaction: discord.Interaction):
        self.parent.config["activo"] = not self.parent.config.get("activo", False)
        nuevo_estado = self.parent.config["activo"]
        self.label = "✅ Desactivar alertas" if nuevo_estado else "❌ Activar alertas"
        self.style = discord.ButtonStyle.danger if nuevo_estado else discord.ButtonStyle.success
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Alertas {'activadas' if nuevo_estado else 'desactivadas'}.", ephemeral=True)

class SaveButton(Button):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(label="💾 Guardar configuración", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        # Guardar configuración
        save_server_config(self.parent.guild_id, self.parent.config)
        embed = discord.Embed(
            title="✅ Configuración guardada",
            description="Las alertas se enviarán al canal seleccionado con el rol indicado.",
            color=COLOR_ONLINE
        )
        canal = self.parent.config.get("canal_id")
        rol = self.parent.config.get("rol_id")
        activo = self.parent.config.get("activo", False)
        embed.add_field(name="Canal", value=f"<#{canal}>" if canal else "No configurado", inline=False)
        embed.add_field(name="Rol", value=f"<@&{rol}>" if rol else "@everyone", inline=False)
        embed.add_field(name="Alertas", value="🟢 Activadas" if activo else "🔴 Desactivadas", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        # Cerrar la vista
        self.view.stop()

# ================= COMANDOS SLASH =================

@tree.command(name="executors", description="Muestra el estado de los exploits")
@app_commands.describe(stat="Nombre del exploit (opcional, si no se especifica muestra todos)")
async def slash_executors(interaction: discord.Interaction, stat: str = None):
    await interaction.response.defer(ephemeral=False)  # Respuesta pública (no efímera)
    datos = obtener_estados()
    if datos is None:
        await interaction.followup.send("❌ No se pudo conectar con la API.")
        return

    if stat:
        # Buscar un exploit específico
        info = buscar_exploit(stat, datos)
        if not info:
            await interaction.followup.send(f"❌ No se encontró el exploit '{stat}'.")
            return
        nombre = info.get("name", stat)
        estado = info.get("status", "Desconocido")
        version = info.get("version", "N/A")
        download = extraer_download(info)
        platform = info.get("platform", "N/A")
        last_updated = info.get("last_updated", "Desconocido")
        color = obtener_color_estado(estado)
        embed = discord.Embed(
            title=f"{nombre} - Estado actual",
            color=color,
            timestamp=datetime.now()
        )
        # Usar emojis como imágenes en el thumbnail
        embed.set_thumbnail(url=EMOJI_GREEN_DOT if "online" in estado.lower() else EMOJI_GREEN_ARROW)
        embed.add_field(name="📊 Estado", value=estado, inline=True)
        embed.add_field(name="📦 Versión", value=version, inline=True)
        embed.add_field(name="🖥️ Plataforma", value=platform, inline=True)
        embed.add_field(name="📅 Última actualización", value=last_updated, inline=False)
        if download != "Sin enlace":
            embed.add_field(name=f"[{EMOJI_LINK}]({download}) Descarga", value=f"[Haz clic aquí]({download})", inline=False)
        else:
            embed.add_field(name="🔗 Descarga", value="No disponible", inline=False)
        embed.set_footer(text="Roblox Exploit Tracker")
        await interaction.followup.send(embed=embed)
    else:
        # Mostrar todos los exploits vigilados (para este servidor)
        config = get_server_config(interaction.guild_id)
        exploits_list = config.get("exploits", GLOBAL_EXPLOITS)
        embed = discord.Embed(
            title="📊 Estado de todos los exploits",
            color=COLOR_DEFAULT,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=EMOJI_GREEN_DOT)
        desc = ""
        online_count = 0
        for nombre in exploits_list:
            info = buscar_exploit(nombre, datos)
            if info:
                estado = info.get("status", "Desconocido")
                version = info.get("version", "N/A")
                emoji = "🟢" if "online" in estado.lower() else "🔴" if "offline" in estado.lower() else "🟠"
                desc += f"{emoji} **{nombre}** → {estado} (v{version})\n"
                if "online" in estado.lower():
                    online_count += 1
            else:
                desc += f"❓ **{nombre}** → No encontrado\n"
        if not desc:
            desc = "No se encontraron exploits en la lista."
        embed.description = desc
        embed.add_field(name="📌 Total vigilados", value=len(exploits_list), inline=True)
        embed.add_field(name="🟢 Online", value=online_count, inline=True)
        embed.set_footer(text="Usa /executors stat <nombre> para ver detalles")
        await interaction.followup.send(embed=embed)

@tree.command(name="supported", description="Muestra la lista de exploits vigilados en este servidor")
async def slash_supported(interaction: discord.Interaction):
    config = get_server_config(interaction.guild_id)
    exploits_list = config.get("exploits", GLOBAL_EXPLOITS)
    if not exploits_list:
        await interaction.response.send_message("📭 No hay exploits en la lista de vigilancia.", ephemeral=True)
        return
    # Dividir en varios mensajes si es muy largo
    chunks = [exploits_list[i:i+20] for i in range(0, len(exploits_list), 20)]
    embed = discord.Embed(
        title="📋 Exploits vigilados",
        description="\n".join([f"• {name}" for name in chunks[0]]),
        color=COLOR_DEFAULT
    )
    embed.set_footer(text=f"Total: {len(exploits_list)} exploits")
    await interaction.response.send_message(embed=embed)
    # Si hay más de 20, enviar el resto como mensajes separados
    for i, chunk in enumerate(chunks[1:], start=1):
        embed = discord.Embed(
            title=f"📋 Continuación ({i+1})",
            description="\n".join([f"• {name}" for name in chunk]),
            color=COLOR_DEFAULT
        )
        await interaction.followup.send(embed=embed)

@tree.command(name="set", description="Configura las alertas automáticas de ejecutores")
@app_commands.describe(auto="Abre el panel de configuración para las alertas", executor="(opcional) no usado", update="(opcional) no usado")
async def slash_set(interaction: discord.Interaction, auto: str = None, executor: str = None, update: str = None):
    # El comando se activa con /set auto executor update (aunque los argumentos no importan)
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Necesitas permisos de administrador para usar este comando.", ephemeral=True)
        return

    config = get_server_config(interaction.guild_id)
    view = ConfigView(interaction.guild_id, config)
    embed = discord.Embed(
        title="⚙️ Configuración de alertas automáticas",
        description="Selecciona el canal y el rol (opcional) donde quieres recibir las notificaciones de actualización de los ejecutores.",
        color=COLOR_DEFAULT
    )
    embed.set_thumbnail(url=EMOJI_SUCCESS)
    embed.add_field(name="📌 Instrucciones", value="Usa los menús desplegables para elegir el canal y el rol. Luego pulsa 'Guardar configuración'.", inline=False)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ================= TAREA DE VERIFICACIÓN PERIÓDICA =================

@tasks.loop(seconds=DEFAULT_INTERVAL)
async def verificar_estados():
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Verificando estados...")
    datos_actuales = obtener_estados()
    if datos_actuales is None:
        print("⚠️ No se pudieron obtener datos, reintentando más tarde.")
        return

    cache = cargar_json(DATA_FILE)
    cambios_globales = []

    for nombre_global in GLOBAL_EXPLOITS:
        info = buscar_exploit(nombre_global, datos_actuales)
        if not info:
            continue
        nombre = info.get("name", nombre_global)
        estado = info.get("status", "Desconocido")
        version = info.get("version", "N/A")
        download = extraer_download(info)
        platform = info.get("platform", "N/A")
        last_updated = info.get("last_updated", "Desconocido")

        clave = nombre.lower()
        anterior = cache.get(clave, {})
        cambio = False
        razon = []
        if anterior.get("status") != estado:
            cambio = True
            razon.append(f"Estado: {anterior.get('status', 'N/A')} → {estado}")
        if anterior.get("version") != version:
            cambio = True
            razon.append(f"Versión: {anterior.get('version', 'N/A')} → {version}")
        if cambio:
            cambios_globales.append({
                "nombre": nombre,
                "estado_anterior": anterior.get("status"),
                "estado_nuevo": estado,
                "version_anterior": anterior.get("version"),
                "version_nueva": version,
                "download": download,
                "platform": platform,
                "last_updated": last_updated,
                "razon": " | ".join(razon)
            })
            print(f"📌 Cambio detectado en {nombre}: {razon}")

        cache[clave] = {
            "status": estado,
            "version": version,
            "download": download,
            "platform": platform,
            "last_updated": last_updated
        }

    guardar_json(DATA_FILE, cache)

    if cambios_globales:
        for guild_id_str, config in config_servidores.items():
            if not config.get("activo", False):
                continue
            canal_id = config.get("canal_id")
            if not canal_id:
                continue
            canal = bot.get_channel(canal_id)
            if not canal:
                continue

            exploits_servidor = config.get("exploits", GLOBAL_EXPLOITS)
            cambios_filtrados = [c for c in cambios_globales if c["nombre"] in exploits_servidor]
            if not cambios_filtrados:
                continue

            rol_id = config.get("rol_id")
            mention = f"<@&{rol_id}>" if rol_id else "@everyone"

            for cambio in cambios_filtrados:
                color = obtener_color_estado(cambio["estado_nuevo"])
                embed = discord.Embed(
                    title=f"{EMOJI_SUCCESS} Actualización en {cambio['nombre']}",
                    description=f"**{cambio['nombre']}** ha cambiado su estado o versión.",
                    color=color,
                    timestamp=datetime.now()
                )
                embed.set_thumbnail(url=EMOJI_GREEN_DOT if "online" in cambio["estado_nuevo"].lower() else EMOJI_GREEN_ARROW)
                embed.add_field(name="📊 Cambio", value=cambio["razon"], inline=False)
                embed.add_field(name="Estado anterior", value=cambio["estado_anterior"] or "Desconocido", inline=True)
                embed.add_field(name="Estado actual", value=cambio["estado_nuevo"], inline=True)
                embed.add_field(name="Versión anterior", value=cambio["version_anterior"] or "N/A", inline=True)
                embed.add_field(name="Versión actual", value=cambio["version_nueva"], inline=True)
                if cambio.get("platform") and cambio["platform"] != "N/A":
                    embed.add_field(name="🖥️ Plataforma", value=cambio["platform"], inline=True)
                if cambio.get("last_updated") and cambio["last_updated"] != "Desconocido":
                    embed.add_field(name="📅 Última actualización", value=cambio["last_updated"], inline=True)
                if cambio["download"] and cambio["download"] != "Sin enlace":
                    embed.add_field(name=f"{EMOJI_LINK} Descarga", value=f"[Haz clic aquí]({cambio['download']})", inline=False)
                else:
                    embed.add_field(name="🔗 Descarga", value="No disponible", inline=False)
                embed.set_footer(text="Roblox Exploit Tracker")

                try:
                    await canal.send(content=mention, embed=embed)
                    print(f"📢 Alerta enviada a {canal.guild.name} para {cambio['nombre']}")
                except Exception as e:
                    print(f"❌ Error enviando alerta: {e}")

# ================= EVENTOS =================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    await tree.sync()
    print("📋 Comandos slash sincronizados.")
    print(f"📋 Monitoreando {len(GLOBAL_EXPLOITS)} exploits globales.")
    print("⏳ Iniciando verificación en 10 segundos...")
    await asyncio.sleep(10)
    if not verificar_estados.is_running():
        verificar_estados.start()

@bot.event
async def on_guild_join(guild):
    print(f"🆕 Nuevo servidor: {guild.name} (ID: {guild.id})")
    get_server_config(guild.id)  # Crear configuración por defecto (inactiva)

@bot.event
async def on_guild_remove(guild):
    guild_id = str(guild.id)
    if guild_id in config_servidores:
        del config_servidores[guild_id]
        guardar_json(CONFIG_FILE, config_servidores)
        print(f"🗑️ Configuración eliminada para {guild.name}")

# ================= INICIO =================

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No se encontró DISCORD_TOKEN")
        exit(1)
    print("=" * 50)
    print("🤖 INICIANDO ROBLOX EXPLOIT TRACKER (VERSIÓN CON BOTONES)")
    print("=" * 50)
    bot.run(TOKEN)
