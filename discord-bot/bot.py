import os
import re
import json
import time
import asyncio
import logging
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote
from pathlib import Path

import discord
from discord import app_commands
from discord.ui import Button, View
import requests
from dotenv import load_dotenv

load_dotenv()

# ── CONFIGURACIÓN ─────────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525629900038475969")
BOT_NAME           = "FMD BOT • BYPASS"
BOT_CREDIT         = "KING"

# ── API Y ARCHIVOS ──────────────────────────────────────────────
VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

AUTOBYPASS_FILE = "autobypass_channels.json"
USER_LANG_FILE  = "user_lang.json"
LOG_FILE        = "bot_logs.txt"
LOCALES_DIR     = Path("locales")

# ── LOGGING ──────────────────────────────────────────────────────
logger = logging.getLogger("FMD_BOT")
logger.setLevel(logging.INFO)
_file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_file_handler.formatter)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# ── URLs DE TUS EMOJIS ──────────────────────────────────────────
URL_GREEN_DOT = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
URL_CROWN     = "https://cdn.discordapp.com/emojis/1511381348433264851.webp?size=100&animated=true"
URL_KEY       = "https://cdn.discordapp.com/emojis/1525381310200414310.webp?size=100"
URL_CLOCK     = "https://cdn.discordapp.com/emojis/1525380296852377711.webp?size=100&animated=true"
URL_SUCCESS   = "https://cdn.discordapp.com/emojis/1502854400769790003.webp?size=100"
URL_LOADING   = "https://cdn.discordapp.com/emojis/1493714096795943063.webp?size=100&animated=true"
URL_COPY      = "https://cdn.discordapp.com/emojis/1525379105111932958.webp?size=100"
URL_DISCORD   = "https://cdn.discordapp.com/emojis/1440409825979928706.webp?size=100"
URL_INVITE    = "https://cdn.discordapp.com/emojis/1377273773710905414.webp?size=100"

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

# ── SISTEMA DE IDIOMAS (MODULAR) ──────────────────────────────
class LocalizationManager:
    def __init__(self):
        self.translations = {}
        self.load_locales()

    def load_locales(self):
        if not LOCALES_DIR.exists():
            LOCALES_DIR.mkdir()
        # Carga los archivos de idioma
        for file in LOCALES_DIR.glob("*.json"):
            lang_code = file.stem
            try:
                with open(file, "r", encoding="utf-8") as f:
                    self.translations[lang_code] = json.load(f)
            except Exception as e:
                logger.error(f"Error loading locale {lang_code}: {e}")
        # Siempre debe existir inglés como fallback
        if "en" not in self.translations:
            logger.warning("English locale not found, creating fallback.")
            self.translations["en"] = {
                "language_name": "English",
                "bypass_loading_title": "Generating Bypass...",
                "bypass_loading_desc": "Please wait...",
                "bypass_completed_title": "Bypass Completed",
                "bypass_result_label": "Result",
                "bypass_duration_label": "Duration",
                "bypass_duration_value": "Seconds",
                "bypass_status_label": "Status",
                "bypass_status_value": "Successfully Generated",
                "bypass_platform_label": "Platform",
                "bypass_pc": "PC",
                "bypass_mobile": "Mobile",
                "bypass_footer": "Made by KING • FMD BOT • BYPASS",
                "bypass_footer_autodelete": "Auto delete in 120 seconds",
                "button_copy": "Copy",
                "button_discord": "Discord",
                "button_invite": "Invite",
                "copy_success": "✅ Copied Successfully!",
                "invalid_url": "⚠️ Invalid URL. Make sure to include `http://` or `https://`.",
                "autobypass_enabled_title": "Auto-Bypass Enabled",
                "autobypass_enabled_desc": "Every link in {channel} will be bypassed automatically.",
                "autobypass_disabled_title": "Auto-Bypass Disabled",
                "autobypass_disabled_desc": "{channel} will no longer auto-bypass.",
                "admin_only": "🚫 You need **Administrator** permissions!",
                "ping_title": "Pong!",
                "ping_latency": "Latency",
                "ping_uptime": "Uptime",
                "ping_servers": "Servers",
                "command_language_desc": "Change the bot's language",
                "command_language_ephemeral": "🌐 Language set to **English**!"
            }

    def get(self, lang_code: str, key: str, **kwargs) -> str:
        # Fallback si no existe el idioma o la clave
        if lang_code in self.translations and key in self.translations[lang_code]:
            text = self.translations[lang_code][key]
        else:
            text = self.translations.get("en", {}).get(key, key)
        # Formateo de variables (ej: {channel})
        return text.format(**kwargs) if kwargs else text

    def detect_language(self, interaction: discord.Interaction) -> str:
        # 1. Usuario guardó idioma manualmente
        user_lang = load_json(USER_LANG_FILE, {})
        if str(interaction.user.id) in user_lang:
            return user_lang[str(interaction.user.id)]
        # 2. Detección automática por locale de Discord
        locale_map = {
            "en-US": "en", "en-GB": "en", "es-ES": "es", "es-LA": "es",
            "pt-BR": "pt", "fr": "fr", "de": "de", "it": "it",
            "ru": "ru", "tr": "tr", "ar": "ar", "ja": "ja",
            "ko": "ko", "zh-CN": "zh", "zh-TW": "zh"
        }
        detected = locale_map.get(str(interaction.locale), "en")
        return detected if detected in self.translations else "en"

i18n = LocalizationManager()

# ── JSON HELPERS ────────────────────────────────────────────────
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

autobypass_channels = set(load_json(AUTOBYPASS_FILE, []))
def _save_ab(): save_json(AUTOBYPASS_FILE, list(autobypass_channels))

# ── MOTOR DE BYPASS ──────────────────────────────────────────────
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "FMD-Bot/1.0"})

_BYPASS_KEYS = ("content","result","loadstring","bypassed","bypassed_link","bypassed_url","final_url","destination","url","link","key","output")

def _extract_bypass_result(data):
    if isinstance(data, dict):
        for k in _BYPASS_KEYS:
            if k in data:
                v = data[k]
                if isinstance(v, str) and v.strip(): return v.strip()
                if isinstance(v, (dict, list)): return _extract_bypass_result(v)
        for v in data.values():
            if isinstance(v, (dict, list)): return _extract_bypass_result(v)
    elif isinstance(data, list):
        for item in data: return _extract_bypass_result(item)
    return None

def bypass_url_sync(url: str):
    last_err = "Unknown error"
    for attempt in range(1, VPS_BYPASS_MAX_RETRIES + 1):
        try:
            resp = _http_session.get(VPS_BYPASS_ENDPOINT + quote(url, safe=""), timeout=VPS_BYPASS_TIMEOUT)
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY); continue
                return None, last_err
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"): return txt, None
                last_err = "Invalid API response"
                if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY); continue
                return None, last_err
            api_err = isinstance(data, dict) and (data.get("success") is False or data.get("error") or str(data.get("status","")).lower() == "error")
            result = _extract_bypass_result(data)
            if result and not api_err: return result, None
            if api_err:
                msg = (data.get("message") or data.get("error")) if isinstance(data, dict) else None
                last_err = str(msg or "No result found")
                if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY); continue
                return None, last_err
            return None, "No result found"
        except requests.exceptions.Timeout:
            last_err = f"Timeout ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY)
        except Exception as e:
            last_err = str(e)[:100]
            if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY)
    return None, last_err

# ── EMBEDS DISEÑO VERDE ──────────────────────────────────────────
def embed_loading(lang: str) -> discord.Embed:
    e = discord.Embed(color=0xFFA500, timestamp=datetime.now(timezone.utc))
    e.set_author(name=i18n.get(lang, "bypass_loading_title"), icon_url=URL_LOADING)
    e.description = i18n.get(lang, "bypass_loading_desc")
    e.set_footer(text=i18n.get(lang, "bypass_footer"))
    return e

def embed_success(result: str, elapsed: float, user: discord.User, lang: str, is_mobile: bool) -> discord.Embed:
    e = discord.Embed(color=0x00FF66, timestamp=datetime.now(timezone.utc))
    # Título con punto verde y texto
    e.set_author(name=f"🟢 {i18n.get(lang, 'bypass_completed_title')}", icon_url=URL_GREEN_DOT)
    # Miniatura (Corona)
    e.set_thumbnail(url=URL_CROWN)
    # Campo Resultado (el más grande)
    e.add_field(name=f"🔑 {i18n.get(lang, 'bypass_result_label')}", value=f"```txt\n{result[:900]}\n```", inline=False)
    # Campo Duración
    e.add_field(name=f"🕒 {i18n.get(lang, 'bypass_duration_label')}", value=f"**{elapsed:.2f}** {i18n.get(lang, 'bypass_duration_value')}", inline=True)
    # Campo Estado
    e.add_field(name=f"✅ {i18n.get(lang, 'bypass_status_label')}", value=f"**{i18n.get(lang, 'bypass_status_value')}**", inline=True)
    # Campo Plataforma
    platform_icon = "📱" if is_mobile else "🖥️"
    platform_name = i18n.get(lang, "bypass_mobile") if is_mobile else i18n.get(lang, "bypass_pc")
    e.add_field(name=i18n.get(lang, "bypass_platform_label"), value=f"{platform_icon} {platform_name}", inline=True)
    # Footer con auto-eliminación
    e.set_footer(text=f"{i18n.get(lang, 'bypass_footer')} • {i18n.get(lang, 'bypass_footer_autodelete')}")
    return e

def embed_fail(error: str, elapsed: float, user: discord.User, lang: str) -> discord.Embed:
    e = discord.Embed(color=0xED4245, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"⚠️ {i18n.get(lang, 'bypass_completed_title')}", icon_url=URL_GREEN_DOT)
    e.set_thumbnail(url=URL_CROWN)
    e.add_field(name="⚠️ Error", value=f"```\n{error or '?'}\n```", inline=False)
    e.add_field(name=f"🕒 {i18n.get(lang, 'bypass_duration_label')}", value=f"**{elapsed:.2f}** {i18n.get(lang, 'bypass_duration_value')}", inline=False)
    e.set_footer(text=i18n.get(lang, "bypass_footer"))
    return e

# ── VIEW (BOTONES) ──────────────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str, elapsed: float, lang: str):
        super().__init__(timeout=None)
        self._result = result
        self._lang = lang

        self.add_item(Button(label=i18n.get(lang, "button_invite"), emoji="➕", url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label=i18n.get(lang, "button_discord"), emoji="💬", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="📋 Copy", style=discord.ButtonStyle.primary, row=0)
    async def copy_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"```txt\n{self._result[:1000]}\n```",
            ephemeral=True
        )
        # Ephemeral no se puede editar/eliminar fácilmente, pero enviamos la confirmación aparte si se desea.
        # El mensaje efímero ya tiene el contenido. Mandaremos un followup de confirmación.
        await interaction.followup.send(i18n.get(self._lang, "copy_success"), ephemeral=True)

# ── AUTO ELIMINACIÓN ─────────────────────────────────────────────
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
        logger.info("✅ Global commands synced.")

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online! Servers: {len(self.guilds)}")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(self._auto_bypass(message, urls))

    async def _auto_bypass(self, message: discord.Message, urls: list):
        try: await message.delete()
        except Exception: pass
        lang = i18n.detect_language(message) # No tenemos interaction aquí, pasamos el mensaje
        # Detectar idioma del usuario en auto-bypass (usamos el guardado o inglés)
        user_lang = load_json(USER_LANG_FILE, {}).get(str(message.author.id), "en")

        loop = asyncio.get_running_loop()
        for url in urls[:3]:
            if not _is_valid_url(url): continue
            try:
                status_msg = await message.channel.send(content=message.author.mention, embed=embed_loading(user_lang))
            except Exception: continue
            t0 = time.time()
            result, error = await loop.run_in_executor(None, bypass_url_sync, url)
            elapsed = time.time() - t0
            try:
                if result:
                    msg = await status_msg.edit(
                        content=message.author.mention,
                        embed=embed_success(result, elapsed, message.author, user_lang, message.author.is_mobile()),
                        view=FmdBypassView(result, elapsed, user_lang)
                    )
                else:
                    msg = await status_msg.edit(
                        content=message.author.mention,
                        embed=embed_fail(error, elapsed, message.author, user_lang)
                    )
                asyncio.create_task(auto_delete_msg(msg, 120))
            except Exception: pass

bot = FmdBot()

# ── SLASH COMMANDS ──────────────────────────────────────────────

@bot.tree.command(name="bypass", description="Bypass a link and get the real destination")
@app_commands.describe(url="The link to bypass")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    lang = i18n.detect_language(interaction)
    if not _is_valid_url(url):
        e = discord.Embed(description=i18n.get(lang, "invalid_url"), color=0xFFA500)
        e.set_footer(text=i18n.get(lang, "bypass_footer"))
        return await interaction.response.send_message(embed=e, ephemeral=True)

    await interaction.response.send_message(embed=embed_loading(lang))
    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_sync, url)
    elapsed = time.time() - t0
    try:
        if result:
            msg = await interaction.edit_original_response(
                embed=embed_success(result, elapsed, interaction.user, lang, interaction.user.is_mobile()),
                view=FmdBypassView(result, elapsed, lang)
            )
        else:
            msg = await interaction.edit_original_response(
                embed=embed_fail(error, elapsed, interaction.user, lang)
            )
        asyncio.create_task(auto_delete_msg(msg, 120))
    except Exception as e:
        logger.error(f"Error editing response: {e}")

@bot.tree.command(name="setautobypass", description="[Admin] Enable/Disable auto-bypass in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    lang = i18n.detect_language(interaction)
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid); _save_ab()
        e = discord.Embed(
            title=i18n.get(lang, "autobypass_disabled_title"),
            description=i18n.get(lang, "autobypass_disabled_desc", channel=interaction.channel.mention),
            color=0xED4245
        )
    else:
        autobypass_channels.add(cid); _save_ab()
        e = discord.Embed(
            title=i18n.get(lang, "autobypass_enabled_title"),
            description=i18n.get(lang, "autobypass_enabled_desc", channel=interaction.channel.mention),
            color=0x00FF66
        )
    e.set_author(name=BOT_NAME, icon_url=URL_GREEN_DOT)
    e.set_footer(text=i18n.get(lang, "bypass_footer"))
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(i18n.get(i18n.detect_language(interaction), "admin_only"), ephemeral=True)

@bot.tree.command(name="ping", description="Check the bot's latency")
async def cmd_ping(interaction: discord.Interaction):
    lang = i18n.detect_language(interaction)
    ms = round(bot.latency * 1000)
    e = discord.Embed(color=0x00FF66, timestamp=datetime.now(timezone.utc))
    e.set_author(name=i18n.get(lang, "ping_title"), icon_url=URL_GREEN_DOT)
    e.add_field(name=f"📡 {i18n.get(lang, 'ping_latency')}", value=f"`{ms}ms`", inline=True)
    e.add_field(name=f"⏰ {i18n.get(lang, 'ping_uptime')}", value=f"`{_uptime()}`", inline=True)
    e.add_field(name=f"🏰 {i18n.get(lang, 'ping_servers')}", value=f"`{len(bot.guilds)}`", inline=True)
    e.set_footer(text=i18n.get(lang, "bypass_footer"))
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="language", description="Change the bot's language")
@app_commands.describe(language="Choose your preferred language")
@app_commands.choices(language=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="Español", value="es"),
    # Añade más aquí según tus archivos en la carpeta locales
])
async def cmd_language(interaction: discord.Interaction, language: str):
    # Guardar preferencia del usuario
    user_lang = load_json(USER_LANG_FILE, {})
    user_lang[str(interaction.user.id)] = language
    save_json(USER_LANG_FILE, user_lang)
    # Responder en el nuevo idioma
    lang = language
    e = discord.Embed(description=i18n.get(lang, "command_language_ephemeral"), color=0x00FF66)
    e.set_footer(text=i18n.get(lang, "bypass_footer"))
    await interaction.response.send_message(embed=e, ephemeral=True)

# ── HEALTH SERVER (Render) ──────────────────────────────────────
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
    logger.info(f"🌐 Health server on port {PORT}")

# ── MAIN ────────────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN missing in environment variables.")
        return
    start_web()
    logger.info(f"🚀 Starting {BOT_NAME}...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
