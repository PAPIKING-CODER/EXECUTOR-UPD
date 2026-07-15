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

# ── NUEVOS EMOJIS PERSONALIZADOS (SIN UNICODE, SOLO IDs) ──────
# Formato Normal: <:Nombre:ID>
# Formato Animado: <a:Nombre:ID>

# Emojis para usar en texto de Embeds
EMOJI_GREEN_DOT = "<a:fmd_green_dot:1526742445323190272>"
EMOJI_LOADER    = "<a:fmd_loader:1526741970226253834>"
EMOJI_CROWN     = "<a:fmd_crown:1526742765311098980>"
EMOJI_KEY       = "<:fmd_key:1526743159038803978>"
EMOJI_CLOCK     = "<a:fmd_clock:1525380296852377711>"
EMOJI_SUCCESS   = "<:fmd_success:1526742163050991616>"

# Emojis para usar en los Botones (se necesita objeto PartialEmoji)
EMOJI_COPY_OBJ = discord.PartialEmoji(name="fmd_copy", id=1526743644894138479)
EMOJI_DISCORD_OBJ = discord.PartialEmoji(name="fmd_discord", id=1526743527642501273)
EMOJI_INVITE_OBJ = discord.PartialEmoji(name="fmd_invite", id=1526743390488756236)

# ── COLORES ──────────────────────────────────────────────────────
C_GREEN  = 0x00FF66  # Verde neón elegante
C_WARN   = 0xFFA500  # Naranja para carga
C_ERROR  = 0xED4245  # Rojo para errores

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
    return "Made by KING • FMD BOT • BYPASS"

def _get_platform(interaction: discord.Interaction) -> tuple:
    """
    Detecta si el usuario está en PC o Móvil.
    Retorna: (Texto string) -> "PC" o "Mobile"
    """
    try:
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if member and member.is_on_mobile():
            return "Mobile"
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

# ── EMBEDS (Diseño Verde Premium, SIN Unicode) ────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_LOADER} Generating Bypass..."
    e.description = "Please wait..."
    e.set_thumbnail(url="") # Omitimos la miniatura o podemos poner un placeholder vacío, pero usar el emoji personalizado en el título es suficiente.
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, interaction: discord.Interaction) -> discord.Embed:
    platform_text = _get_platform(interaction)
    
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS"
    e.description = "Generated successfully • Auto delete in 120 seconds"
    e.set_thumbnail(url="") # Sin imagen, solo el texto del título y el autor.
    
    e.add_field(name=f"{EMOJI_KEY} Result", value=f"```txt\n{result[:900]}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name=f"{EMOJI_SUCCESS} Status", value="Successfully Generated", inline=True)
    e.add_field(name="Platform", value=platform_text, inline=True)
    
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, interaction: discord.Interaction) -> discord.Embed:
    platform_text = _get_platform(interaction)
    
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS"
    e.description = "Something went wrong!"
    e.set_thumbnail(url="")
    
    e.add_field(name="Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name="Platform", value=platform_text, inline=True)
    
    e.set_footer(text=_footer())
    return e

# ── VIEW (Solo 3 Botones con EMOJIS PERSONALIZADOS) ────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        
        # Botón de Discord (Link)
        self.add_item(Button(label="Discord", emoji=EMOJI_DISCORD_OBJ, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))
        # Botón de Invite (Link)
        self.add_item(Button(label="Invite", emoji=EMOJI_INVITE_OBJ, url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="Copy", emoji=EMOJI_COPY_OBJ, style=discord.ButtonStyle.success, row=0)
    async def copy_btn(self, interaction: discord.Interaction, button: Button):
        # El bloque de código permite copiar con un clic en móvil y PC
        await interaction.response.send_message(
            f"```txt\n{self._result}\n```\nCopied Successfully!",
            ephemeral=True
        )

# ── AUTO ELIMINACIÓN (120 segundos) ────────────────────────────
async def auto_delete_msg(message: discord.Message, delay: int = 120):
    await asyncio.sleep(delay)
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
                    embed = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
                    embed.set_author(name="FMD BOT • BYPASS", icon_url="")
                    embed.title = f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS"
                    embed.description = "Generated successfully • Auto delete in 120 seconds"
                    embed.set_thumbnail(url="")
                    embed.add_field(name=f"{EMOJI_KEY} Result", value=f"```txt\n{result[:900]}\n```", inline=False)
                    embed.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
                    embed.add_field(name=f"{EMOJI_SUCCESS} Status", value="Successfully Generated", inline=True)
                    embed.add_field(name="Platform", value="Auto-Bypass", inline=True)
                    embed.set_footer(text=_footer())

                    msg = await status_msg.edit(
                        content=message.author.mention,
                        embed=embed,
                        view=FmdBypassView(result)
                    )
                else:
                    msg = await status_msg.edit(
                        content=message.author.mention,
                        embed=embed_fail(error, elapsed, None) 
                    )
                asyncio.create_task(auto_delete_msg(msg, 120))
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
            msg = await interaction.edit_original_response(
                embed=embed_success(result, elapsed, interaction),
                view=FmdBypassView(result)
            )
        else:
            msg = await interaction.edit_original_response(
                embed=embed_fail(error, elapsed, interaction)
            )
        asyncio.create_task(auto_delete_msg(msg, 120))
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
