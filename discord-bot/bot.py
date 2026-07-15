import os
import re
import json
import time
import asyncio
import logging
import threading
import random
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
import requests
from dotenv import load_dotenv

load_dotenv()

# ── LOGGING ──────────────────────────────────────────────────────
LOG_FILE = "bot_logs.txt"
logger = logging.getLogger("FMD_BOT")
logger.setLevel(logging.INFO)
_file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# ── CONFIGURACIÓN ──────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525629900038475969")

VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"

# ── EMOJIS PERSONALIZADOS ──────────────────────────────────────
EMOJI_GREEN_DOT = "<a:fmd_green_dot:1526742445323190272>"
EMOJI_LOADER    = "<a:fmd_loader:1526741970226253834>"
EMOJI_CROWN     = "<a:fmd_crown:1526742765311098980>"
EMOJI_SUCCESS   = "<:fmd_success:1526742163050991616>"
EMOJI_KEY       = "<:fmd_key:1526743159038803978>"
EMOJI_CLOCK     = "<a:fmd_clock:1525380296852377711>"
EMOJI_PC        = "<:emojigg_pc:1526858555544572035>"
EMOJI_PHONE     = "📱"

# Para los botones
EMOJI_COPY_BTN    = discord.PartialEmoji(name="fmd_copy", id=1526743644894138479)
EMOJI_DISCORD_BTN = discord.PartialEmoji(name="fmd_discord", id=1526743527642501273)
EMOJI_INVITE_BTN  = discord.PartialEmoji(name="fmd_invite", id=1526743390488756236)

# ── COLORES ──────────────────────────────────────────────────────
C_GREEN  = 0x00FF66  # Neon Green premium
C_WARN   = 0xFFA500
C_ERROR  = 0xED4245

# ── HELPERS ──────────────────────────────────────────────────────
BOT_START_TIME = datetime.now(timezone.utc)
_URL_RE = re.compile(r"https?://[^\s<>\"']+")

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START_TIME
    t = int(d.total_seconds())
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _footer() -> str:
    return "Made by KING\nFMD BOT • BYPASS"

def _get_platform(interaction: discord.Interaction) -> str:
    try:
        member = interaction.guild.get_member(interaction.user.id)
        if member and member.is_on_mobile():
            return EMOJI_PHONE
        else:
            return EMOJI_PC
    except Exception:
        return EMOJI_PC

# ── MANEJO DE JSON ──────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"save_json: {e}")

autobypass_channels = set(load_json(AUTOBYPASS_CHANNELS_FILE, []))

# ── MOTOR DE BYPASS (4PI API) ──────────────────────────────────
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "FMD-Bot/1.0"})

_BYPASS_RESULT_KEYS = (
    "content", "result", "loadstring", "bypassed", "bypassed_link",
    "bypassed_url", "final_url", "destination", "url", "link", "key", "output"
)

def _extract_bypass_result(data):
    if isinstance(data, dict):
        for k in _BYPASS_RESULT_KEYS:
            if k in data:
                v = data[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (dict, list)):
                    nested = _extract_bypass_result(v)
                    if nested:
                        return nested
        for v in data.values():
            if isinstance(v, (dict, list)):
                nested = _extract_bypass_result(v)
                if nested:
                    return nested
    elif isinstance(data, list):
        for item in data:
            nested = _extract_bypass_result(item)
            if nested:
                return nested
    return None

def _bypass_sync(url: str):
    last_error = "Error desconocido"
    for attempt in range(1, VPS_BYPASS_MAX_RETRIES + 1):
        try:
            full_url = VPS_BYPASS_ENDPOINT + quote(url, safe="")
            resp = _http_session.get(full_url, timeout=VPS_BYPASS_TIMEOUT)

            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"):
                    return txt, None
                last_error = "Respuesta inválida de la API"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            api_says_error = False
            if isinstance(data, dict):
                status_val = str(data.get("status", "")).lower()
                if data.get("success") is False or data.get("error") or status_val == "error":
                    api_says_error = True

            result = _extract_bypass_result(data)

            if result and not api_says_error:
                return str(result), None

            if api_says_error:
                err_msg = None
                if isinstance(data, dict):
                    err_msg = data.get("message") or data.get("error")
                last_error = str(err_msg or "La API reportó un error.")
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            return None, "No se encontró resultado en la API."

        except requests.exceptions.Timeout:
            last_error = f"Tiempo de espera agotado ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
        except Exception as e:
            last_error = str(e)[:100]
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)

    return None, last_error

# ── EMBEDS (Diseño Premium Verde/Cyber) ───────────────────────
def embed_loading():
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS")
    e.title = f"{EMOJI_LOADER} Generating Bypass..."
    e.description = "Processing your link...\nPlease wait..."
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif")
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform_emoji: str):
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.description = f"Generated successfully.\n{EMOJI_CLOCK} Auto delete in `120s`"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    
    e.add_field(
        name=f"{EMOJI_KEY} Result",
        value=f"```txt\n{result[:900]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{EMOJI_CLOCK} Duration",
        value=f"`{elapsed:.2f}s`",
        inline=True
    )
    e.add_field(
        name=f"{EMOJI_SUCCESS} Status",
        value="`Successfully Generated`",
        inline=True
    )
    e.add_field(
        name="Platform",
        value=platform_emoji,
        inline=True
    )
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, platform_emoji: str):
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Failed"
    e.description = "Something went wrong!"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name="Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name="Platform", value=platform_emoji, inline=True)
    e.set_footer(text=_footer())
    return e

# ── VISTA DE BOTONES (Solo Copy, Discord, Invite) ─────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        
        # Botón Discord (Link)
        self.add_item(Button(
            label="Discord", 
            emoji=EMOJI_DISCORD_BTN, 
            url=SUPPORT_SERVER_URL, 
            style=discord.ButtonStyle.link,
            row=0
        ))
        # Botón Invite (Link)
        self.add_item(Button(
            label="Invite", 
            emoji=EMOJI_INVITE_BTN, 
            url=BOT_INVITE_URL, 
            style=discord.ButtonStyle.link,
            row=0
        ))

    # Botón Copy (Interactivo)
    @discord.ui.button(
        emoji=EMOJI_COPY_BTN, 
        label="Copy", 
        style=discord.ButtonStyle.success, 
        row=0
    )
    async def copy_btn(self, interaction: discord.Interaction, button: Button):
        # Envía un mensaje efímero con bloque de código para copiar al instante
        await interaction.response.send_message(
            f"```txt\n{self._result}\n```",
            ephemeral=True
        )

# ── CUENTA REGRESIVA EN VIVO Y AUTO ELIMINACIÓN ───────────────
async def _start_countdown(message: discord.Message, base_embed: discord.Embed, view: View, seconds: int = 120):
    clock_emoji = EMOJI_CLOCK
    while seconds > 0:
        try:
            new_embed = base_embed.copy()
            field_updated = False
            
            # Buscar el campo existente y actualizarlo
            for i, field in enumerate(new_embed.fields):
                if field.name == f"{clock_emoji} Auto Delete":
                    new_embed.set_field_at(
                        i, 
                        name=field.name, 
                        value=f"`{seconds}s remaining`", 
                        inline=field.inline
                    )
                    field_updated = True
                    break
            
            # Si no existe, lo agregamos en el primer tick
            if not field_updated:
                new_embed.add_field(
                    name=f"{clock_emoji} Auto Delete", 
                    value=f"`{seconds}s remaining`", 
                    inline=False
                )
            
            await message.edit(embed=new_embed, view=view)
            await asyncio.sleep(1)
            seconds -= 1
        except (discord.NotFound, discord.HTTPException):
            break
            
    # Al llegar a 0, elimina el mensaje
    try:
        await message.delete()
    except Exception:
        pass

# ── CLASE DEL BOT ──────────────────────────────────────────────
class FmdBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Comandos globales sincronizados.")

    async def on_ready(self):
        logger.info(f"✅ {self.user.name} Online! en {len(self.guilds)} servidores.")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
            
        # AUTO-BYPASS
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                # Borrar mensaje original
                try:
                    await message.delete()
                except Exception:
                    pass
                
                # Procesar solo el primer link
                url = urls[0]
                if _is_valid_url(url):
                    loop = asyncio.get_running_loop()
                    status_msg = await message.channel.send(embed=embed_loading())
                    
                    t0 = time.time()
                    result, error = await loop.run_in_executor(None, _bypass_sync, url)
                    elapsed = time.time() - t0
                    
                    try:
                        if result:
                            # Detectar plataforma (Auto-Bypass no tiene interacción, asumimos PC)
                            platform = EMOJI_PC
                            embed = embed_success(result, elapsed, platform)
                            view = FmdBypassView(result)
                            msg = await status_msg.edit(embed=embed, view=view)
                            asyncio.create_task(_start_countdown(msg, embed, view))
                        else:
                            platform = EMOJI_PC
                            embed = embed_fail(error, elapsed, platform)
                            msg = await status_msg.edit(embed=embed)
                            asyncio.create_task(_start_countdown(msg, embed, View()))
                    except Exception:
                        pass

bot = FmdBot()

# ── SLASH COMMANDS ─────────────────────────────────────────────

# ── /bypass ─────────────────────────────────────────────────────
@bot.tree.command(name="bypass", description="🔓 Bypass un enlace y obtén el destino real")
@app_commands.describe(url="El enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        e = discord.Embed(description="⚠️ URL inválida. Asegúrate de incluir `http://` o `https://`.", color=C_WARN)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)

    # Mostrar embed de carga
    await interaction.response.send_message(embed=embed_loading())

    # Ejecutar bypass en un hilo aparte
    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, _bypass_sync, url)
    elapsed = time.time() - t0
    platform_emoji = _get_platform(interaction)

    try:
        if result:
            embed = embed_success(result, elapsed, platform_emoji)
            view = FmdBypassView(result)
            msg = await interaction.edit_original_response(embed=embed, view=view)
            # Iniciar cuenta regresiva de 120s
            asyncio.create_task(_start_countdown(msg, embed, view))
        else:
            embed = embed_fail(error, elapsed, platform_emoji)
            msg = await interaction.edit_original_response(embed=embed)
            # Iniciar cuenta regresiva de 120s con vista vacía
            asyncio.create_task(_start_countdown(msg, embed, View()))
    except Exception as e:
        logger.error(f"Error al editar respuesta: {e}")

# ── /setautobypass ──────────────────────────────────────────────
@bot.tree.command(name="setautobypass", description="⚙️ [Admin] Activar/desactivar auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, list(autobypass_channels))
        e = discord.Embed(
            title="Auto-Bypass DESACTIVADO",
            description=f"{interaction.channel.mention} ya no hará bypass automático.",
            color=C_ERROR
        )
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, list(autobypass_channels))
        e = discord.Embed(
            title="Auto-Bypass ACTIVADO",
            description=f"Cada enlace en {interaction.channel.mention} será bypasseado automáticamente.",
            color=C_GREEN
        )
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS", icon_url="")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Necesitas permiso de Administrador!", ephemeral=True)

# ── /ping ───────────────────────────────────────────────────────
@bot.tree.command(name="ping", description="🏓 Ver la latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(title=f"{EMOJI_GREEN_DOT} Pong!", color=C_GREEN)
    e.add_field(name="📡 Latencia", value=f"`{ms}ms`", inline=True)
    e.add_field(name="⏰ Uptime", value=f"`{_uptime()}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── /gif (API pública de Tenor) ────────────────────────────────
@bot.tree.command(name="gif", description="🎥 Busca un GIF en Tenor")
@app_commands.describe(busqueda="Término de búsqueda")
async def cmd_gif(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    tenor_key = "AIzaSyC2-7bLmQ0lB7p3mO_qB3X0D5TdYbKjU8s" # Key pública funcional
    
    try:
        r = requests.get(
            f"https://tenor.googleapis.com/v2/search?q={quote(busqueda)}&key={tenor_key}&limit=1&media_filter=gif",
            timeout=10
        ).json()
        if not r.get("results"):
            return await interaction.followup.send("❌ No se encontraron GIFs.")
        gif_url = r["results"][0]["media_formats"]["gif"]["url"]
        e = discord.Embed(title=f"{EMOJI_GREEN_DOT} Resultado de búsqueda", color=C_GREEN)
        e.set_image(url=gif_url)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener el GIF.")

# ── HEALTH SERVER (Para Render, corrige Error 501) ─────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'{{"status":"online","bot":"FMD BOT","uptime":"{_uptime()}"}}'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
    def log_message(self, *_): pass

def start_web():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"🌐 Servidor de salud en puerto :{PORT}")

# ── MAIN ──────────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado.")
        return
    start_web()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
