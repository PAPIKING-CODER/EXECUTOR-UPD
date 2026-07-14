"""
FMD BOT — Bypass + Auto-Bypass System
Creador: KING
"""
import sys, types

try:
    import audioop
except ImportError:
    sys.modules["audioop"] = types.ModuleType("audioop")

import os, re, json, time, asyncio, logging, threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
import requests

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

# ── LOGGING ──────────────────────────────────────────────────────
logger = logging.getLogger("FMD")
logger.setLevel(logging.INFO)
for _h in (RotatingFileHandler("bot.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"),
           logging.StreamHandler()):
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(_h)

# ── CONFIG ───────────────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL",
    "https://discord.com/oauth2/authorize?client_id=1525629900038475969")

BOT_NAME   = "FMD BOT"
BOT_CREDIT = "KING"

BYPASS_API_URL = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT = 30
BYPASS_RETRIES = 3
BYPASS_DELAY   = 3

AUTOBYPASS_FILE = "autobypass_channels.json"

# ── COLORES ──────────────────────────────────────────────────────
C_RED   = 0xC80000   # rojo oscuro principal
C_DARK  = 0x1A0000   # casi negro con tono rojo
C_WARN  = 0xFF4500   # rojo-naranja para loading
C_INFO  = 0x8B0000   # rojo profundo

# ── IMAGENES Y EMOJIS (URLs) ─────────────────────────────────────
# Tus emojis e imágenes personalizadas
URL_VERIFIED = "https://cdn.discordapp.com/emojis/1511381303872716820.webp?size=100&animated=true"
URL_LOADING  = "https://cdn.discordapp.com/emojis/1254460771883028661.webp?size=100&animated=true"
URL_CROWN    = "https://cdn.discordapp.com/emojis/1461735621985833061.webp?size=100&animated=true"
URL_KEY      = "https://cdn.discordapp.com/emojis/1483938936253317371.webp?size=100"
URL_CLOCK    = "https://cdn.discordapp.com/emojis/1525380296852377711.webp?size=100&animated=true"
URL_PIN      = "https://cdn.discordapp.com/emojis/1409375664003354626.webp?size=100"
URL_NOTIF    = "https://cdn.discordapp.com/emojis/1516326060449595464.webp?size=100&animated=true"
URL_WARN     = "https://cdn.discordapp.com/emojis/1495901573476520106.webp?size=100"
URL_REDMAIL  = "https://cdn.discordapp.com/emojis/1433333582050365461.webp?size=100"
URL_REDSETA  = "https://cdn.discordapp.com/emojis/1433037312224264294.webp?size=100"
URL_AVISO    = "https://cdn.discordapp.com/emojis/1399216286353064028.webp?size=100"
URL_MAIN_GIF = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a57d17b&is=6a567ffb&hm=7c1a8b24541be5b90396964acf5480a6802bdd2c6bb4600dfac870013575af0e&"

BOT_START = datetime.now(timezone.utc)

# ── JSON ─────────────────────────────────────────────────────────
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

autobypass_channels: set = set(load_json(AUTOBYPASS_FILE, []))
def _save_ab(): save_json(AUTOBYPASS_FILE, list(autobypass_channels))

# ── HELPERS ──────────────────────────────────────────────────────
_URL_RE = re.compile(r"https?://[^\s<>\"']{6,}")

def _is_url(u: str) -> bool:
    return bool(re.match(r"^https?://\S{6,}", u))

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START
    t = int(d.total_seconds())
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _footer() -> str:
    return f"MADE WITH 💪 BY {BOT_CREDIT} • {BOT_NAME}"

# ── BYPASS ENGINE ────────────────────────────────────────────────
_KEYS = ("content","result","loadstring","bypassed","bypassed_link",
         "bypassed_url","final_url","destination","url","link","key","output")
_http = requests.Session()
_http.headers.update({"User-Agent": "FMD-Bot/1.0"})

def _extract(data):
    if isinstance(data, dict):
        for k in _KEYS:
            if k in data:
                v = data[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (dict, list)):
                    r = _extract(v)
                    if r: return r
        for v in data.values():
            if isinstance(v, (dict, list)):
                r = _extract(v)
                if r: return r
    elif isinstance(data, list):
        for item in data:
            r = _extract(item)
            if r: return r
    return None

def _bypass_sync(url: str):
    last_err = "Error desconocido"
    for attempt in range(1, BYPASS_RETRIES + 1):
        try:
            resp = _http.get(BYPASS_API_URL + quote(url, safe=""), timeout=BYPASS_TIMEOUT)
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"): return txt, None
                last_err = "Respuesta inválida"
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            api_err = isinstance(data, dict) and (
                data.get("success") is False or data.get("error")
                or str(data.get("status","")).lower() == "error")
            result = _extract(data)
            if result and not api_err: return result, None
            if api_err:
                msg = (data.get("message") or data.get("error")) if isinstance(data, dict) else None
                last_err = str(msg or "Sin resultado")
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            return None, "Sin resultado"
        except requests.exceptions.Timeout:
            last_err = f"Timeout ({BYPASS_TIMEOUT}s)"
            if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY)
        except Exception as ex:
            last_err = str(ex)[:100]
            if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY)
    return None, last_err

# ── EMBEDS ───────────────────────────────────────────────────────

def embed_ok(result: str, elapsed: float, url: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"BYPASSED SUCCESSFULLY", icon_url=URL_VERIFIED)
    e.set_thumbnail(url=URL_KEY)  # El emoji de llave como miniatura
    e.add_field(
        name=f"🔑 RESULT:",
        value=f"```\n{result[:900]}\n```",
        inline=False
    )
    e.add_field(
        name=f"👤 REQUEST BY",
        value=user.mention,
        inline=False
    )
    e.add_field(
        name=f"🔗 URL",
        value=f"```\n{url[:200]}\n```",
        inline=False
    )
    e.set_image(url=URL_MAIN_GIF)
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, url: str, elapsed: float, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name="BYPASS FAILED", icon_url=URL_WARN)
    e.set_thumbnail(url=URL_AVISO)
    e.add_field(
        name=f"⚠️ ERROR",
        value=f"```\n{error or '?'}\n```",
        inline=False
    )
    e.add_field(
        name=f"🔗 URL",
        value=f"```\n{url[:200]}\n```",
        inline=False
    )
    e.add_field(
        name=f"👤 REQUEST BY",
        value=user.mention,
        inline=False
    )
    e.set_image(url=URL_MAIN_GIF)
    e.set_footer(text=_footer())
    return e

def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="PROCESSING BYPASS...", icon_url=URL_LOADING)
    e.set_thumbnail(url=URL_LOADING)
    e.description = "⏳ Bypass en proceso, espera un momento..."
    e.set_footer(text=_footer())
    return e

# ── VIEWS (Botones) ──────────────────────────────────────────────

class BypassView(View):
    def __init__(self, result: str, elapsed: float):
        super().__init__(timeout=None)
        self._r = result
        # Botón de tiempo deshabilitado
        self.add_item(Button(
            label=f"⏰  {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True, row=0))
        # Botón COPY
        self.add_item(Button(
            label="📋 COPY RESULT",
            style=discord.ButtonStyle.success,
            row=0))
        # Botón DELETE
        self.add_item(Button(
            label="🗑️ DELETE",
            style=discord.ButtonStyle.danger,
            row=0))
        # Botones de links
        self.add_item(Button(
            label="JOIN",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link, row=1))
        self.add_item(Button(
            label="INVITE",
            url=BOT_INVITE_URL,
            style=discord.ButtonStyle.link, row=1))

    @discord.ui.button(label="📋  COPY RESULT", style=discord.ButtonStyle.success, row=0)
    async def copy_btn(self, interaction: discord.Interaction, _):
        # El formato especial que pediste para móvil y PC
        # Móvil ve `RSU` y en PC lo puede copiar con un click en el bloque
        await interaction.response.send_message(
            content=f"```RSU\n{self._r}\n```", ephemeral=True)

    @discord.ui.button(label="🗑️  DELETE", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, _):
        try:
            await interaction.message.delete()
        except Exception:
            await interaction.response.send_message("❌ No pude eliminar el mensaje.", ephemeral=True)

class FailView(View):
    def __init__(self, elapsed: float):
        super().__init__(timeout=None)
        self.add_item(Button(
            label=f"⏰  {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True, row=0))
        self.add_item(Button(
            label="JOIN",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link, row=1))
        self.add_item(Button(
            label="INVITE",
            url=BOT_INVITE_URL,
            style=discord.ButtonStyle.link, row=1))

# ── BOT CLIENT ────────────────────────────────────────────────────

class FMD_Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online como {self.user} | {len(self.guilds)} servidor(es)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"/help • {BOT_NAME}"))

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(_auto_bypass(message, urls))

bot = FMD_Bot()

# ── AUTO-BYPASS ───────────────────────────────────────────────────

async def _auto_bypass(message: discord.Message, urls: list):
    try: await message.delete()
    except Exception: pass
    loop = asyncio.get_running_loop()
    for url in urls[:3]:
        if not _is_url(url): continue
        try: msg = await message.channel.send(
            content=message.author.mention, embed=embed_loading())
        except Exception: continue
        t0 = time.time()
        result, error = await loop.run_in_executor(None, _bypass_sync, url)
        elapsed = time.time() - t0
        try:
            if result:
                await msg.edit(content=message.author.mention,
                               embed=embed_ok(result, elapsed, url, message.author),
                               view=BypassView(result, elapsed))
            else:
                await msg.edit(content=message.author.mention,
                               embed=embed_fail(error, url, elapsed, message.author),
                               view=FailView(elapsed))
        except Exception: pass

# ── SLASH COMMANDS ───────────────────────────────────────────────

@bot.tree.command(name="bypass", description="Bypassea un enlace")
@app_commands.describe(url="Enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_url(url):
        e = discord.Embed(description=f"⚠️ URL inválida.", color=C_RED)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)
    await interaction.response.send_message(embed=embed_loading())
    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, _bypass_sync, url)
    elapsed = time.time() - t0
    if result:
        await interaction.edit_original_response(
            embed=embed_ok(result, elapsed, url, interaction.user),
            view=BypassView(result, elapsed))
    else:
        await interaction.edit_original_response(
            embed=embed_fail(error, url, elapsed, interaction.user),
            view=FailView(elapsed))

@bot.tree.command(name="setautobypass",
                  description="Activa o desactiva auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid); _save_ab()
        e = discord.Embed(
            description=f"❌ Auto-bypass **desactivado** en {interaction.channel.mention}.",
            color=C_RED)
    else:
        autobypass_channels.add(cid); _save_ab()
        e = discord.Embed(
            description=f"✅ Auto-bypass **activado** en {interaction.channel.mention}.\n🔗 Los enlaces se bypasean automáticamente.",
            color=C_RED)
    e.set_author(name=BOT_NAME, icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ae(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(
            f"⚠️ Necesitas permisos de **Administrador**.", ephemeral=True)

@bot.tree.command(name="help", description="Ver todos los comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Comandos", icon_url=URL_CROWN)
    e.set_thumbnail(url=URL_CROWN)
    e.add_field(
        name=f"⚡ Bypass",
        value=(f"`/bypass` — Bypass manual de enlaces\n"
               f"`/setautobypass` — Auto-bypass en este canal *(Admin)*"),
        inline=False)
    e.add_field(
        name=f"👑 Utilidad",
        value="`/ping` — Latencia del bot\n`/help` — Esta lista de comandos",
        inline=False)
    e.set_image(url=URL_MAIN_GIF)
    e.set_footer(text=_footer())
    v = View()
    v.add_item(Button(label="JOIN", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
    v.add_item(Button(label="INVITE", url=BOT_INVITE_URL, style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=e, view=v)

@bot.tree.command(name="ping", description="Ver latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🏓 Ping", icon_url=URL_CROWN)
    e.add_field(name=f"📶 Latencia", value=f"```{ms}ms```", inline=True)
    e.add_field(name=f"⏰ Uptime", value=f"```{_uptime()}```", inline=True)
    e.add_field(name=f"🏰 Servidores", value=f"```{len(bot.guilds)}```", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── HEALTH SERVER (Para Render) ──────────────────────────────────

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
    logger.info(f"🌐 Health server corriendo en puerto :{PORT}")

# ── MAIN ──────────────────────────────────────────────────────────

async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado en variables de entorno.")
        return
    start_web()
    logger.info(f"🚀 Iniciando {BOT_NAME}...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
