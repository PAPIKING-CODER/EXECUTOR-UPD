import os
import re
import json
import time
import asyncio
import logging
import threading
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

# ── NUEVOS EMOJIS PERSONALIZADOS (SIN UNICODE, EXCEPTO 📱) ────
# Formato Normal: <:Nombre:ID>
# Formato Animado: <a:Nombre:ID>

EMOJI_GREEN_DOT = "<a:fmd_green_dot:1526742445323190272>"
EMOJI_LOADER    = "<a:fmd_loader:1526741970226253834>"
EMOJI_CROWN     = "<a:fmd_crown:1526742765311098980>"
EMOJI_KEY       = "<:fmd_key:1526743159038803978>"
EMOJI_CLOCK     = "<a:fmd_clock:1525380296852377711>"
EMOJI_SUCCESS   = "<:fmd_success:1526742163050991616>"

# Emojis para Botones
EMOJI_COPY_OBJ    = discord.PartialEmoji(name="fmd_copy", id=1526743644894138479)
EMOJI_DISCORD_OBJ = discord.PartialEmoji(name="fmd_discord", id=1526743527642501273)
EMOJI_INVITE_OBJ  = discord.PartialEmoji(name="fmd_invite", id=1526743390488756236)

# ── COLORES ──────────────────────────────────────────────────────
C_GREEN  = 0x00FF66  # Neon Green Premium
C_WARN   = 0xFFA500  # Naranja
C_ERROR  = 0xED4245  # Rojo

# ── HELPERS ──────────────────────────────────────────────────────
BOT_START_TIME = datetime.now(timezone.utc)
_URL_RE = re.compile(r"https?://[^\s<>\"']+")

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START_TIME
    t = int(d.total_seconds())
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _footer() -> str:
    return "Made by KING\nFMD BOT • BYPASS"

def _get_platform(interaction: discord.Interaction) -> str:
    try:
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if member and member.is_on_mobile():
            return "📱"  # Excepción explícita permitida para móvil
        else:
            return "PC"
    except Exception:
        return "PC"

# ── MOTOR DE BYPASS (Robusto) ──────────────────────────────────
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "FMD-Bot/1.0"})

_BYPASS_RESULT_KEYS = (
    "content", "result", "loadstring", "bypassed", "bypassed_link",
    "bypassed_url", "final_url", "destination", "url", "link", "key", "output"
)

def _extract_bypass_result(data):
    if isinstance(data, dict):
        for key in _BYPASS_RESULT_KEYS:
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, (dict, list)):
                    nested = _extract_bypass_result(value)
                    if nested:
                        return nested
        for value in data.values():
            if isinstance(value, (dict, list)):
                nested = _extract_bypass_result(value)
                if nested:
                    return nested
    elif isinstance(data, list):
        for item in data:
            nested = _extract_bypass_result(item)
            if nested:
                return nested
    return None

def bypass_url_vps(url: str):
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

# ── ARCHIVOS JSON ──────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(data), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"save_json: {e}")

autobypass_channels = load_json(AUTOBYPASS_CHANNELS_FILE, set())

# ── EMBEDS (Diseño Premium Verde) ──────────────────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_LOADER} Generating Bypass..."
    e.description = "Please wait while we process your request."
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif") # Loader
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.description = "Generated successfully"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif") # Corona obligatoria
    
    e.add_field(name=f"{EMOJI_KEY} Result", value=f"```txt\n{result[:900]}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name=f"{EMOJI_SUCCESS} Status", value="Successfully Generated", inline=True)
    e.add_field(name="Platform", value=platform, inline=True)
    
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_GREEN_DOT} Bypass Failed"
    e.description = "Something went wrong!"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    
    e.add_field(name="Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name="Platform", value=platform, inline=True)
    
    e.set_footer(text=_footer())
    return e

# ── VIEW (SOLO 3 BOTONES) ──────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        
        self.add_item(Button(label="Discord", emoji=EMOJI_DISCORD_OBJ, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Invite", emoji=EMOJI_INVITE_OBJ, url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(emoji=EMOJI_COPY_OBJ, label="Copy", style=discord.ButtonStyle.success, row=0)
    async def copy_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"{EMOJI_SUCCESS} Copied Successfully!",
            ephemeral=True
        )

# ── CUENTA REGRESIVA EN VIVO Y AUTO ELIMINACIÓN ────────────────
async def start_countdown(message: discord.Message, base_embed: discord.Embed, view: View, seconds: int = 120):
    clock_emoji = EMOJI_CLOCK
    while seconds > 0:
        try:
            new_embed = base_embed.copy()
            
            # Buscamos y actualizamos el campo de Auto Delete
            field_updated = False
            for i, field in enumerate(new_embed.fields):
                if field.name == f"{clock_emoji} Auto Delete":
                    new_embed.set_field_at(i, name=field.name, value=f"Message expires in: `{seconds}s`", inline=field.inline)
                    field_updated = True
                    break
            
            # Si no existe (primer tick), lo agregamos
            if not field_updated:
                new_embed.add_field(name=f"{clock_emoji} Auto Delete", value=f"Message expires in: `{seconds}s`", inline=False)
            
            await message.edit(embed=new_embed, view=view)
            await asyncio.sleep(1)
            seconds -= 1
        except (discord.NotFound, discord.HTTPException):
            break
            
    # Al llegar a 0, eliminar mensaje
    try:
        await message.delete()
    except Exception:
        pass

# ── BOT CLIENT ──────────────────────────────────────────────────
class FmdBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Comandos globales sincronizados.")

    async def on_ready(self):
        logger.info("=========================================")
        logger.info(f"✅ {self.user.name} Online!")
        logger.info(f"📡 Servidores: {len(self.guilds)}")
        logger.info("=========================================")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(self._auto_bypass(message, urls))

    async def _auto_bypass(self, message: discord.Message, urls: list):
        try:
            await message.delete()
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        for url in urls[:3]:
            if not _is_valid_url(url):
                continue

            try:
                status_msg = await message.channel.send(content=message.author.mention, embed=embed_loading())
            except Exception:
                continue

            t0 = time.time()
            result, error = await loop.run_in_executor(None, bypass_url_vps, url)
            elapsed = time.time() - t0

            try:
                if result:
                    embed = embed_success(result, elapsed, platform="Auto-Bypass")
                    view = FmdBypassView(result)
                    msg = await status_msg.edit(content=message.author.mention, embed=embed, view=view)
                    asyncio.create_task(start_countdown(msg, embed, view))
                else:
                    embed = embed_fail(error, elapsed, platform="Auto-Bypass")
                    msg = await status_msg.edit(content=message.author.mention, embed=embed)
                    asyncio.create_task(start_countdown(msg, embed, View()))
            except Exception:
                pass

bot = FmdBot()

# ── SLASH COMMANDS ──────────────────────────────────────────────

@bot.tree.command(name="bypass", description="🔓 Bypass un enlace y obtén el destino real")
@app_commands.describe(url="El enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        e = discord.Embed(description="⚠️ URL inválida. Asegúrate de incluir `http://` o `https://`.", color=C_WARN)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)

    await interaction.response.send_message(embed=embed_loading())

    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_vps, url)
    elapsed = time.time() - t0

    try:
        if result:
            platform = _get_platform(interaction)
            embed = embed_success(result, elapsed, platform)
            view = FmdBypassView(result)
            msg = await interaction.edit_original_response(embed=embed, view=view)
            asyncio.create_task(start_countdown(msg, embed, view))
        else:
            platform = _get_platform(interaction)
            embed = embed_fail(error, elapsed, platform)
            msg = await interaction.edit_original_response(embed=embed)
            asyncio.create_task(start_countdown(msg, embed, View()))
    except Exception as e:
        logger.error(f"Error al editar respuesta: {e}")

@bot.tree.command(name="setautobypass", description="⚙️ [Admin] Activar/desactivar auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, autobypass_channels)
        e = discord.Embed(
            title="Auto-Bypass DESACTIVADO",
            description=f"{interaction.channel.mention} ya no hará bypass automático.",
            color=C_ERROR
        )
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, autobypass_channels)
        e = discord.Embed(
            title="Auto-Bypass ACTIVADO",
            description=f"Cada enlace en {interaction.channel.mention} será bypasseado automáticamente.",
            color=C_GREEN
        )
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Necesitas permiso de Administrador!", ephemeral=True)

@bot.tree.command(name="ping", description="🏓 Ver la latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.add_field(name="Latencia", value=f"`{ms}ms`", inline=True)
    e.add_field(name="Uptime", value=f"`{_uptime()}`", inline=True)
    e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── HEALTH SERVER (Para Render) ─────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'{{"status":"online","bot":"FMD BOT","uptime":"{_uptime()}"}}'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        # Soluciona el error 501 de UptimeRobot
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def log_message(self, *_): pass

def start_web():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"🌐 Servidor de salud corriendo en puerto :{PORT}")

# ── MAIN ──────────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado en variables de entorno.")
        return
    start_web()
    logger.info(f"🚀 Iniciando FMD BOT...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
