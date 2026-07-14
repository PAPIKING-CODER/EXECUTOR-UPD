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

# ── CONFIG ──────────────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525629900038475969")

BOT_NAME   = "FMD BOT"
BOT_CREDIT = "KING"

VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"

# ── URLs DE TUS NUEVOS EMOJIS E IMÁGENES ─────────────────────────
URL_GREEN_DOT = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
URL_THUMBNAIL = "https://cdn.discordapp.com/emojis/1511381348433264851.webp?size=100&animated=true"
URL_CLOCK     = "https://cdn.discordapp.com/emojis/1525380296852377711.webp?size=100&animated=true"
URL_KEY       = "https://cdn.discordapp.com/emojis/1525381310200414310.webp?size=100"
URL_SUCCESS   = "https://cdn.discordapp.com/emojis/1525379448768303207.webp?size=100&animated=true"
URL_MAIN_GIF  = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a57d17b&is=6a567ffb&hm=7c1a8b24541be5b90396964acf5480a6802bdd2c6bb4600dfac870013575af0e&"

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

def _footer(extra: str = "") -> str:
    base = f"Made with 💪 by {BOT_CREDIT} • {BOT_NAME}"
    return f"{base} - {extra}" if extra else base

# ── BYPASS ENGINE ──────────────────────────────────────────────
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

# ── JSON ──────────────────────────────────────────────────────────
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

# ── EMBEDS (Diseño Verde) ──────────────────────────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=0xFFA500, timestamp=datetime.now(timezone.utc))
    e.set_author(name="PROCESSING BYPASS...", icon_url=URL_GREEN_DOT)
    e.set_thumbnail(url=URL_THUMBNAIL)
    e.description = "⏳ Bypass en proceso, espera un momento..."
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=0x57F287, timestamp=datetime.now(timezone.utc))
    # Autor con icono de punto verde al lado del título
    e.set_author(name="FMD BYPASS • Success", icon_url=URL_GREEN_DOT)
    # Miniatura con el emoji que enviaste
    e.set_thumbnail(url=URL_THUMBNAIL)
    # Resultado (acortado a 900 caracteres para que quepa)
    e.add_field(name="🔑 Result:", value=f"```txt\n{result[:900]}\n```", inline=False)
    # Tiempo de respuesta
    e.add_field(name="⏰ Time:", value=f"`{elapsed:.2f}s`", inline=False)
    # Banner principal
    e.set_image(url=URL_MAIN_GIF)
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=0xED4245, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BYPASS • Failed", icon_url=URL_GREEN_DOT)
    e.set_thumbnail(url=URL_THUMBNAIL)
    e.add_field(name="⚠️ Error:", value=f"```\n{error or '?'}\n```", inline=False)
    e.add_field(name="⏰ Time:", value=f"`{elapsed:.2f}s`", inline=False)
    e.set_image(url=URL_MAIN_GIF)
    e.set_footer(text=_footer())
    return e

# ── VIEW (Botones) ──────────────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str, elapsed: float):
        super().__init__(timeout=None)
        self._result = result
        # Botón de Invite (Link)
        self.add_item(Button(label="Invite", emoji="🤖", url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="📋  Copy", style=discord.ButtonStyle.primary, row=0)
    async def copy_btn(self, interaction: discord.Interaction, button: Button):
        # Al hacer clic, se abre un mensaje efímero con el código listo para copiar
        await interaction.response.send_message(
            f"📋 Click dentro del bloque de código abajo para copiar:\n```txt\n{self._result[:1000]}\n```",
            ephemeral=True
        )

# ── FUNCIÓN DE AUTO ELIMINACIÓN ─────────────────────────────────
async def auto_delete_msg(message: discord.Message, delay: int = 120):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass # Si ya fue eliminado o hay errores, ignorar

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
        logger.info(f"✅ {BOT_NAME} Online: {self.user.name}")
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
                    msg = await status_msg.edit(
                        content=message.author.mention,
                        embed=embed_success(result, elapsed, message.author),
                        view=FmdBypassView(result, elapsed)
                    )
                else:
                    msg = await status_msg.edit(
                        content=message.author.mention,
                        embed=embed_fail(error, elapsed, message.author)
                    )
                # Auto-eliminar el mensaje a los 120 segundos
                asyncio.create_task(auto_delete_msg(msg, 120))
            except Exception:
                pass

bot = FmdBot()

# ── SLASH COMMANDS ──────────────────────────────────────────────

@bot.tree.command(name="bypass", description="🔓 Bypass un enlace y obtén el destino real")
@app_commands.describe(url="El enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        e = discord.Embed(description="⚠️ URL inválida. Asegúrate de incluir `http://` o `https://`.", color=0xFFA500)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)

    await interaction.response.send_message(embed=embed_loading())

    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_vps, url)
    elapsed = time.time() - t0

    try:
        if result:
            msg = await interaction.edit_original_response(
                embed=embed_success(result, elapsed, interaction.user),
                view=FmdBypassView(result, elapsed)
            )
        else:
            msg = await interaction.edit_original_response(
                embed=embed_fail(error, elapsed, interaction.user)
            )
        # Auto-eliminar el mensaje a los 120 segundos
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
            title="🔴 Auto-Bypass DESACTIVADO",
            description=f"{interaction.channel.mention} ya no hará bypass automático.",
            color=0xED4245
        )
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, autobypass_channels)
        e = discord.Embed(
            title="🟢 Auto-Bypass ACTIVADO",
            description=f"Cada enlace en {interaction.channel.mention} será bypasseado automáticamente.",
            color=0x57F287
        )
    e.set_author(name=BOT_NAME, icon_url=URL_GREEN_DOT)
    e.set_footer(text=_footer(f"Canales activos: {len(autobypass_channels)}"))
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Necesitas permiso de **Administrador**!", ephemeral=True)

@bot.tree.command(name="ping", description="🏓 Ver la latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(color=0x57F287, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Ping", icon_url=URL_GREEN_DOT)
    e.add_field(name="📡 Latencia", value=f"`{ms}ms`", inline=True)
    e.add_field(name="⏰ Uptime", value=f"`{_uptime()}`", inline=True)
    e.add_field(name="🏰 Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── HEALTH SERVER (Para Render) ─────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'{{"status":"online","bot":"{BOT_NAME}","uptime":"{_uptime()}"}}'.encode()
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
    logger.info(f"🚀 Iniciando {BOT_NAME}...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
