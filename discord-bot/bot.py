import os
import re
import json
import time
import random
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from logging.handlers import RotatingFileHandler
from urllib.parse import unquote, quote

import discord
from discord import app_commands
from discord.ui import Button, View
from discord.ext import tasks
import aiohttp
import requests

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# ══════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════
LOG_FILE = "bot_logs.txt"
logger = logging.getLogger("BotLogger")
logger.setLevel(logging.INFO)
_fh  = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_ch  = logging.StreamHandler()
_fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_fh.setFormatter(_fmt)
_ch.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_ch)

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
DISCORD_TOKEN  = os.environ.get("DISCORD_TOKEN", "")
OWNER_ID       = int(os.environ.get("OWNER_ID", "0"))
PORT           = int(os.environ.get("PORT", "8080"))
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL     = "llama3-8b-8192"
ROBLOX_API_KEY = os.environ.get("ROBLOX_API_KEY", "")

BOT_NAME           = "KOD BOT"
BOT_CREDIT         = "By king"
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525040833814855710")
BYPASS_SERVICE_NAME      = "KOD BYPASS"
BYPASS_FOOTER_SIGNATURE  = "KING"

EMOJI_SUCCESS = "<:greendot:1525383175889485848>"
EMOJI_KEY     = "<:goldenkey:1525381310200414310>"
EMOJI_CLOCK   = "<a:clock:1525380296852377711>"
EMOJI_COPY    = "<:copy:1525379105111932958>"
EMOJI_LINK    = "<:link:1525379856034959422>"

BYPASS_BANNER_URL = "https://cdn.discordapp.com/attachments/1509409338354303157/1525397585458888855/ezgif-2225e2913bbda08b.gif"

EMOJI_GREEN_DOT   = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
EMOJI_GREEN_ARROW = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"
EMOJI_SUCCESS_URL = "https://cdn.discordapp.com/emojis/1525379448768303207.webp?size=100&animated=true"

WEAO_API       = "https://api.weao.xyz/v1/exploits"
CHECK_INTERVAL = 90

GLOBAL_EXPLOITS = [
    "Solara","Wave","AWP","Vega X","Delta","Hydrogen","Fluxus",
    "Electron","Nihon","Celestial","Velocity","Oxygen U","Comet",
    "Zypher","Krnl","Synapse X","Script-Ware","Evon","JJSploit",
    "Coco","Zen","Borealis","Sirius","Xeno","Rise","Valyse",
    "Elysian","Novus","Vynixius","Seliware","Exoliner","Neo",
    "Trigon","Eclipse","Oblivion","Fates","Arceus X","Mystic",
    "Aurora","Nexus","Quantum","Phantom","Infinity","Legendary",
    "Carbon","X-Code","Skrypt","Vortex","Horizon","Genesis",
    "Apex","Nova","Stellar","Pandora","Zeus","Hades","Ares",
    "Atlas","Eden","Frost","Storm","Blaze","Shadow","Light","Dark",
]

VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

_BYPASS_RESULT_KEYS = ("content","result","loadstring","bypassed","bypassed_link","bypassed_url","final_url","destination","url","link","key","output")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

CONFIG_FILE              = "config.json"
STATE_FILE               = "estado_anterior.json"
AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"
WARNINGS_FILE            = "warnings.json"
IA_CHANNELS_FILE         = "ia_channels.json"
WELCOME_CONFIG_FILE      = "welcome_config.json"
LOGS_CONFIG_FILE         = "logs_config.json"
GIVEAWAYS_FILE           = "giveaways.json"

BOT_START_TIME = datetime.now(timezone.utc)

# ══════════════════════════════════════════════════════════════════
#  COLORS & GIFS
# ══════════════════════════════════════════════════════════════════
C_BYPASS  = 0x00D9FF
C_SUCCESS = 0x57F287
C_ERROR   = 0xED4245
C_WARN    = 0xFEE75C
C_MOD     = 0xEB459E
C_FUN     = 0xFF7043
C_INFO    = 0x5865F2
C_ROBLOX  = 0x00B2FF
C_AUTO    = 0x9B59B6

GIF_LOADING = "https://media.tenor.com/wpSo-8CrXqUAAAAi/loading-loading-forever.gif"
GIF_SUCCESS = "https://media.tenor.com/nT8MLcQsEIYAAAAi/check.gif"
GIF_ERROR   = "https://media.tenor.com/0LF_JKlnPsgAAAAi/error-warning.gif"
GIF_MOD     = "https://media.tenor.com/vOCNEoM3GVYAAAAC/ban-hammer.gif"
GIF_FUN     = "https://media.tenor.com/2i5PCb0B6fUAAAAC/dice-game.gif"
GIF_ROBLOX  = "https://media.tenor.com/5g5JibBLMf0AAAAC/roblox.gif"
GIF_CAT     = "https://media.tenor.com/GZyqHLOaHhEAAAAC/cat-meow.gif"
GIF_COIN    = "https://media.tenor.com/DkElfr7vHKsAAAAC/coin-flip.gif"
GIF_BALL8   = "https://media.tenor.com/RR42W4NkUmcAAAAC/magic-8-ball.gif"

BALL8_RESPONSES = [
    "✅ Sí, definitivamente.","✅ Es cierto.","✅ Sin duda.",
    "✅ Puedes contar con eso.","✅ Muy probable.",
    "🟡 Las señales apuntan a sí.","🟡 Respuesta confusa, intenta de nuevo.",
    "🟡 Mejor no decirte ahora.","🟡 No lo puedo predecir ahora.",
    "🟡 Concéntrate y pregunta de nuevo.",
    "❌ No cuentes con eso.","❌ Mi respuesta es no.",
    "❌ Mis fuentes dicen no.","❌ Perspectiva no tan buena.","❌ Muy dudoso.",
]

# ══════════════════════════════════════════════════════════════════
#  HELPERS: JSON
# ══════════════════════════════════════════════════════════════════

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[JSON] Error guardando {path}: {e}")

# ══════════════════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════════════════
autobypass_channels: set = set(load_json(AUTOBYPASS_CHANNELS_FILE, []))
ia_channels:         set = set(load_json(IA_CHANNELS_FILE, []))
welcome_config:     dict = load_json(WELCOME_CONFIG_FILE, {})
logs_config:        dict = load_json(LOGS_CONFIG_FILE, {})
giveaways:          dict = load_json(GIVEAWAYS_FILE, {})
_warnings:          dict = load_json(WARNINGS_FILE, {})
reaction_roles:     dict = {}
_active_giveaways:  dict = {}

def _save_autobypass(): save_json(AUTOBYPASS_CHANNELS_FILE, list(autobypass_channels))
def _save_ia():         save_json(IA_CHANNELS_FILE,         list(ia_channels))
def _save_warnings():   save_json(WARNINGS_FILE,            _warnings)

# ══════════════════════════════════════════════════════════════════
#  HELPERS: MISC
# ══════════════════════════════════════════════════════════════════

def write_log(username, user_id, command, status, details=""):
    extra = f" | Details: {details}" if details else ""
    logger.info(f"User: {username} | ID: {user_id} | Command: {command} | Status: {status}{extra}")

def is_owner_or_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    if interaction.guild and isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False

def format_uptime(start: datetime) -> str:
    delta = datetime.now(timezone.utc) - start
    total = int(delta.total_seconds())
    days, rem     = divmod(total, 86400)
    hours, rem    = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:    parts.append(f"{days}d")
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def _footer(extra: str = "") -> str:
    base = f"{BOT_NAME} - {BOT_CREDIT}"
    return f"{base} - {extra}" if extra else base

def status_emoji(status: str) -> str:
    s = (status or "").lower()
    if s == "online":  return "🟢"
    if s == "patched": return "🔴"
    return "🟡"

def bypass_emoji(value) -> str:
    return "✅" if value else "❌"

def _mod_embed(title: str, desc: str, color=None) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color or C_ERROR, timestamp=discord.utils.utcnow())
    e.set_thumbnail(url=GIF_MOD)
    e.set_footer(text=_footer())
    return e

# ══════════════════════════════════════════════════════════════════
#  BYPASS ENGINE (4PI)
# ══════════════════════════════════════════════════════════════════

_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "KodBot/2.0"})

def _extract_bypass_result(data):
    if isinstance(data, dict):
        for key in _BYPASS_RESULT_KEYS:
            if key in data:
                v = data[key]
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

def bypass_url_vps(url: str):
    last_error = "Unknown error"
    for attempt in range(1, VPS_BYPASS_MAX_RETRIES + 1):
        try:
            full_url = VPS_BYPASS_ENDPOINT + quote(url, safe="")
            resp = _http_session.get(full_url, timeout=VPS_BYPASS_TIMEOUT)
            if resp.status_code in (502, 503, 504):
                last_error = f"4PI API sobrecargada (HTTP {resp.status_code})"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error
            try:
                data = resp.json()
            except Exception:
                text = resp.text.strip()
                if text.startswith("http"):
                    return text, None
                last_error = "No se pudo parsear la respuesta de 4PI"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            api_error = False
            if isinstance(data, dict):
                if data.get("success") is False or data.get("error") or str(data.get("status","")).lower() == "error":
                    api_error = True

            result = _extract_bypass_result(data)
            if result and not api_error:
                return str(result), None
            if api_error:
                err_msg = data.get("message") or data.get("error") if isinstance(data, dict) else None
                last_error = str(err_msg or "La API de 4PI reportó un error")
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error
            return None, "No se encontró resultado en la respuesta de la API"

        except requests.exceptions.Timeout:
            last_error = f"Timeout ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
                continue
        except requests.exceptions.ConnectionError as ex:
            last_error = f"Error de conexión: {str(ex)[:80]}"
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
                continue
        except Exception as ex:
            last_error = str(ex)
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
                continue
    return None, last_error

def _bypass_ts() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

def build_bypass_result_embed(result: str, elapsed: float) -> discord.Embed:
    embed = discord.Embed(color=0x00FF00)
    embed.description = f"{EMOJI_SUCCESS} **{BYPASS_SERVICE_NAME} • Success**"
    embed.add_field(name=f"{EMOJI_KEY} Result:",    value=f"```txt\n{result[:1000]}\n```", inline=False)
    embed.add_field(name=f"{EMOJI_CLOCK} Velocidad:", value=f"`{elapsed:.2f}s`",           inline=False)
    if BYPASS_BANNER_URL:
        embed.set_image(url=BYPASS_BANNER_URL)
    embed.set_footer(text=f"Made by: {BYPASS_FOOTER_SIGNATURE} • {_bypass_ts()}")
    return embed

class BypassResultView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        self.add_item(Button(label="Add Bot", emoji=EMOJI_LINK, url=BOT_INVITE_URL,     style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Server",  emoji=EMOJI_LINK, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="Copy", emoji=EMOJI_COPY, style=discord.ButtonStyle.secondary, row=0)
    async def copy_button(self, interaction: discord.Interaction, _b):
        await interaction.response.send_message(f"```txt\n{self._result[:1000]}\n```", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  GROQ AI
# ══════════════════════════════════════════════════════════════════
_groq_client = AsyncGroq(api_key=GROQ_API_KEY) if (AsyncGroq and GROQ_API_KEY) else None

async def _ask_groq(prompt: str, system: str = "Eres KOD BOT, un asistente de Discord amigable y útil. Responde siempre en español de forma clara y concisa.") -> str:
    if not _groq_client:
        return "❌ GROQ_API_KEY no configurada. Agrégala en Render como variable de entorno."
    try:
        response = await _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"system","content":system},{"role":"user","content":prompt[:4000]}],
            max_tokens=800, temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as ex:
        logger.error(f"[GROQ] {ex}")
        return f"❌ Error con Groq AI: `{str(ex)[:200]}`"

# ══════════════════════════════════════════════════════════════════
#  WEAO API (executor tracker)
# ══════════════════════════════════════════════════════════════════

async def fetch_exploits() -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEAO_API, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data  = await resp.json(content_type=None)
                    items = data if isinstance(data, list) else data.get("exploits", data.get("data", []))
                    return {item.get("name","").lower(): item for item in items if item.get("name")}
    except Exception as ex:
        logger.warning(f"[WEAO] Error: {ex}")
    return {}

def get_exploit_info(api_data: dict, name: str):
    return api_data.get(name.lower())

# ══════════════════════════════════════════════════════════════════
#  BOT CLIENT
# ══════════════════════════════════════════════════════════════════

class BotClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Comandos slash sincronizados globalmente.")

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} Online: {self.user.name} ({self.user.id})")
        logger.info(f"📡 Sirviendo {len(self.guilds)} servidor(es)")
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception:
                pass
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help • KOD BOT"))
        check_exploits.start()
        logger.info(f"🔄 Verificación de exploits activa cada {CHECK_INTERVAL}s")

    async def on_member_join(self, member: discord.Member):
        guild_key = str(member.guild.id)
        wcfg = welcome_config.get(guild_key, {})
        if wcfg.get("welcome_enabled") and wcfg.get("welcome_channel"):
            ch = member.guild.get_channel(wcfg["welcome_channel"])
            if ch:
                msg = (wcfg.get("welcome_message","¡Bienvenido {user} a {server}! 🎉")
                       .replace("{user}", member.mention)
                       .replace("{server}", member.guild.name))
                try:
                    await ch.send(msg)
                except Exception:
                    pass
        # auto-role
        if wcfg.get("auto_role"):
            role = member.guild.get_role(wcfg["auto_role"])
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role KOD BOT")
                except Exception:
                    pass
        # join logs
        lcfg = logs_config.get(guild_key, {})
        if lcfg.get("join_logs_enabled") and lcfg.get("join_log_channel"):
            ch = member.guild.get_channel(lcfg["join_log_channel"])
            if ch:
                e = discord.Embed(title="📥 Miembro se Unió", description=f"{member.mention} (`{member.id}`)",
                                  color=C_SUCCESS, timestamp=discord.utils.utcnow())
                e.set_thumbnail(url=member.display_avatar.url)
                e.set_footer(text=_footer(f"Total: {member.guild.member_count}"))
                try:
                    await ch.send(embed=e)
                except Exception:
                    pass

    async def on_member_remove(self, member: discord.Member):
        guild_key = str(member.guild.id)
        wcfg = welcome_config.get(guild_key, {})
        if wcfg.get("goodbye_enabled") and wcfg.get("goodbye_channel"):
            ch = member.guild.get_channel(wcfg["goodbye_channel"])
            if ch:
                msg = (wcfg.get("goodbye_message","**{user}** ha abandonado **{server}** 👋")
                       .replace("{user}", str(member))
                       .replace("{server}", member.guild.name))
                try:
                    await ch.send(msg)
                except Exception:
                    pass
        lcfg = logs_config.get(guild_key, {})
        if lcfg.get("join_logs_enabled") and lcfg.get("join_log_channel"):
            ch = member.guild.get_channel(lcfg["join_log_channel"])
            if ch:
                e = discord.Embed(title="📤 Miembro Salió", description=f"**{member}** (`{member.id}`)",
                                  color=C_ERROR, timestamp=discord.utils.utcnow())
                e.set_thumbnail(url=member.display_avatar.url)
                e.set_footer(text=_footer(f"Total: {member.guild.member_count}"))
                try:
                    await ch.send(embed=e)
                except Exception:
                    pass

    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        guild_key = str(message.guild.id)
        lcfg = logs_config.get(guild_key, {})
        if lcfg.get("message_logs_enabled") and lcfg.get("message_log_channel"):
            ch = message.guild.get_channel(lcfg["message_log_channel"])
            if ch:
                e = discord.Embed(title="🗑️ Mensaje Eliminado", color=C_WARN, timestamp=discord.utils.utcnow())
                e.add_field(name="Autor",   value=message.author.mention, inline=True)
                e.add_field(name="Canal",   value=message.channel.mention, inline=True)
                e.add_field(name="Contenido", value=message.content[:500] or "*Sin texto*", inline=False)
                e.set_footer(text=_footer())
                try:
                    await ch.send(embed=e)
                except Exception:
                    pass

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        # Auto-bypass
        if message.channel.id in autobypass_channels:
            urls = _URL_PATTERN.findall(message.content)
            if urls:
                asyncio.create_task(handle_autobypass_message(message, urls))
                return
        # Auto-IA
        if message.channel.id in ia_channels and message.content.strip():
            asyncio.create_task(handle_ia_message(message))

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        guild_key = str(payload.guild_id)
        msg_data  = reaction_roles.get(guild_key, {}).get(str(payload.message_id), {})
        role_id   = msg_data.get(str(payload.emoji))
        if not role_id:
            return
        guild = self.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role   = guild.get_role(role_id)
        if member and role and not member.bot:
            try:
                await member.add_roles(role, reason="Reaction role KOD BOT")
            except Exception:
                pass

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        guild_key = str(payload.guild_id)
        msg_data  = reaction_roles.get(guild_key, {}).get(str(payload.message_id), {})
        role_id   = msg_data.get(str(payload.emoji))
        if not role_id:
            return
        guild = self.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role   = guild.get_role(role_id)
        if member and role and not member.bot:
            try:
                await member.remove_roles(role, reason="Reaction role KOD BOT")
            except Exception:
                pass

bot = BotClient()

# ══════════════════════════════════════════════════════════════════
#  AUTO-BYPASS MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════════

async def handle_autobypass_message(message: discord.Message, urls: list):
    author  = message.author
    channel = message.channel
    try:
        await message.delete()
    except Exception:
        pass
    loop = asyncio.get_running_loop()
    for url in urls[:3]:
        if not _is_valid_url(url):
            continue
        start = time.time()
        status_msg = None
        try:
            e = discord.Embed(title="[ Procesando ] KOD BYPASS", color=C_WARN, timestamp=discord.utils.utcnow())
            e.set_author(name="KOD BOT - Auto-Bypass", icon_url=bot.user.display_avatar.url if bot.user else None)
            e.set_thumbnail(url=GIF_LOADING)
            e.set_footer(text=_footer())
            status_msg = await channel.send(content=author.mention, embed=e)
        except Exception:
            continue
        try:
            result, error = await loop.run_in_executor(None, bypass_url_vps, url)
            elapsed = time.time() - start
            if result:
                embed = build_bypass_result_embed(result, elapsed)
                view  = BypassResultView(result)
                await status_msg.edit(content=author.mention, embed=embed, view=view)
            else:
                err_e = discord.Embed(title="[ Fallido ] Bypass",
                                      description=f"```diff\n- {error or 'Error desconocido'}\n```",
                                      color=C_ERROR, timestamp=discord.utils.utcnow())
                err_e.set_thumbnail(url=GIF_ERROR)
                err_e.set_footer(text=_footer())
                await status_msg.edit(content=author.mention, embed=err_e)
        except Exception as ex:
            logger.error(f"[AUTOBYPASS] {ex}")

async def handle_ia_message(message: discord.Message):
    async with message.channel.typing():
        reply = await _ask_groq(message.content)
    try:
        e = discord.Embed(description=reply, color=C_INFO, timestamp=discord.utils.utcnow())
        e.set_author(name="KOD BOT IA", icon_url=bot.user.display_avatar.url if bot.user else None)
        e.set_footer(text=_footer("Groq • llama3-8b"))
        await message.reply(embed=e, mention_author=False)
    except Exception as ex:
        logger.error(f"[IA_MSG] {ex}")

# ══════════════════════════════════════════════════════════════════
#  TAREA: VERIFICACIÓN AUTOMÁTICA DE EXPLOITS
# ══════════════════════════════════════════════════════════════════

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_exploits():
    config   = load_json(CONFIG_FILE, {})
    previous = load_json(STATE_FILE, {})
    api_data = await fetch_exploits()
    if not api_data:
        return
    changed = False
    for guild_id, guild_cfg in config.items():
        if not guild_cfg.get("enabled"):
            continue
        ch_id = guild_cfg.get("channel_id")
        if not ch_id or ch_id == "none":
            continue
        guild = bot.get_guild(int(guild_id))
        if not guild:
            continue
        channel = guild.get_channel(int(ch_id))
        if not channel:
            continue
        role_id = guild_cfg.get("role_id")
        exploits_list = guild_cfg.get("exploits", GLOBAL_EXPLOITS)
        for exp_name in exploits_list:
            info = get_exploit_info(api_data, exp_name)
            if not info:
                continue
            real_name   = info.get("name", exp_name)
            key         = f"{guild_id}_{real_name.lower()}"
            cur_status  = info.get("status", "Unknown")
            cur_version = info.get("version", "N/A")
            prev        = previous.get(key, {})
            prev_status  = prev.get("status")
            prev_version = prev.get("version")
            previous[key] = {"status": cur_status, "version": cur_version}
            changed = True
            if not (prev_status is not None and prev_status != cur_status) and \
               not (prev_version is not None and prev_version != cur_version):
                continue
            platform = info.get("platform","N/A")
            updated  = info.get("updated_at", info.get("last_updated","N/A"))
            dl_link  = info.get("download", info.get("download_link", info.get("link",None)))
            is_on    = cur_status.lower() == "online"
            color    = C_SUCCESS if is_on else (C_ERROR if cur_status.lower()=="patched" else C_WARN)
            embed = discord.Embed(title=f"🎉 Actualización en {real_name}", color=color, timestamp=discord.utils.utcnow())
            if prev_status and prev_status != cur_status:
                embed.add_field(name="🔄 Cambio de estado",   value=f"`{prev_status}` → `{cur_status}`",   inline=False)
            if prev_version and prev_version != cur_version:
                embed.add_field(name="📦 Cambio de versión",  value=f"`{prev_version}` → `{cur_version}`", inline=False)
            embed.add_field(name="Estado actual",        value=f"{status_emoji(cur_status)} {cur_status}", inline=True)
            embed.add_field(name="Versión actual",       value=cur_version,   inline=True)
            embed.add_field(name="Plataforma",           value=platform,      inline=True)
            embed.add_field(name="Última actualización", value=str(updated),  inline=False)
            if dl_link:
                embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl_link})", inline=False)
            embed.set_thumbnail(url=EMOJI_GREEN_DOT if is_on else EMOJI_GREEN_ARROW)
            embed.set_footer(text="Datos de api.weao.xyz")
            mention = ""
            if role_id:
                role = guild.get_role(int(role_id))
                mention = role.mention if role else ""
            if not mention:
                mention = "@everyone"
            try:
                await channel.send(content=mention, embed=embed)
            except discord.Forbidden:
                logger.warning(f"[ALERT] Sin permisos en #{channel.name}")
            except Exception as ex:
                logger.error(f"[ALERT] {ex}")
    if changed:
        save_json(STATE_FILE, previous)

@check_exploits.before_loop
async def before_check():
    await bot.wait_until_ready()
    await asyncio.sleep(10)

# ══════════════════════════════════════════════════════════════════
#  HELPER: MOD LOG
# ══════════════════════════════════════════════════════════════════

async def _send_mod_log(guild: discord.Guild, embed: discord.Embed):
    lcfg = logs_config.get(str(guild.id), {})
    if lcfg.get("mod_log_channel") and lcfg.get("mod_logs_enabled"):
        ch = guild.get_channel(lcfg["mod_log_channel"])
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass

# ══════════════════════════════════════════════════════════════════
#  GIVEAWAY HELPER
# ══════════════════════════════════════════════════════════════════

async def _giveaway_countdown(channel, msg_id, premio, winners, end_time, host):
    try:
        await asyncio.sleep(max(0, (end_time - datetime.now(timezone.utc)).total_seconds()))
        msg      = await channel.fetch_message(msg_id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if not reaction:
            await channel.send("❌ Nadie participó en el giveaway.")
            return
        users    = [u async for u in reaction.users() if not u.bot]
        if not users:
            await channel.send("❌ No hay participantes válidos.")
            return
        selected = random.sample(users, min(winners, len(users)))
        mentions = " ".join(u.mention for u in selected)
        e = discord.Embed(title="〔 🎉 〕 ¡GIVEAWAY TERMINADO!",
                          description=f"**Premio:** {premio}\n\n🏆 **Ganador(es):** {mentions}",
                          color=C_FUN, timestamp=discord.utils.utcnow())
        e.set_footer(text=_footer(f"Host: {host}"))
        await channel.send(content=mentions, embed=e)
        giveaways.pop(str(msg_id), None)
        save_json(GIVEAWAYS_FILE, giveaways)
    except Exception as ex:
        logger.error(f"[GIVEAWAY] {ex}")

# ══════════════════════════════════════════════════════════════════
#  SETUP VIEW (executor alert config)
# ══════════════════════════════════════════════════════════════════

class SetupView(discord.ui.View):
    def __init__(self, guild: discord.Guild, current_config: dict):
        super().__init__(timeout=120)
        self.guild = guild
        self.cfg   = current_config.copy()
        self._build_selects()

    def _build_selects(self):
        text_channels = [c for c in self.guild.channels if isinstance(c, discord.TextChannel)][:25]
        ch_opts = [discord.SelectOption(label=f"#{c.name}", value=str(c.id),
                                        default=(str(c.id)==str(self.cfg.get("channel_id","")))) for c in text_channels]
        ch_sel = discord.ui.Select(placeholder="📢 Selecciona el canal de alertas",
                                   options=ch_opts or [discord.SelectOption(label="Sin canales",value="none")],
                                   custom_id="channel_select", row=0)
        ch_sel.callback = self.channel_callback
        self.add_item(ch_sel)

        roles = [r for r in self.guild.roles if r.name != "@everyone"][:24]
        r_opts = [discord.SelectOption(label="Ninguno", value="none", default=not self.cfg.get("role_id"))]
        r_opts += [discord.SelectOption(label=f"@{r.name}", value=str(r.id),
                                        default=(str(r.id)==str(self.cfg.get("role_id","")))) for r in roles]
        r_sel = discord.ui.Select(placeholder="👥 Rol a mencionar (opcional)",
                                  options=r_opts[:25], custom_id="role_select", row=1)
        r_sel.callback = self.role_callback
        self.add_item(r_sel)

    async def channel_callback(self, interaction: discord.Interaction):
        self.cfg["channel_id"] = interaction.data["values"][0]
        await interaction.response.defer()

    async def role_callback(self, interaction: discord.Interaction):
        v = interaction.data["values"][0]
        self.cfg["role_id"] = None if v == "none" else v
        await interaction.response.defer()

    @discord.ui.button(label="✅ Activar alertas",    style=discord.ButtonStyle.success, row=2)
    async def toggle_on(self, interaction: discord.Interaction, _b):
        self.cfg["enabled"] = True
        await interaction.response.send_message("✅ Alertas **activadas**.", ephemeral=True)

    @discord.ui.button(label="🔕 Desactivar alertas", style=discord.ButtonStyle.danger,  row=2)
    async def toggle_off(self, interaction: discord.Interaction, _b):
        self.cfg["enabled"] = False
        await interaction.response.send_message("🔕 Alertas **desactivadas**.", ephemeral=True)

    @discord.ui.button(label="💾 Guardar configuración", style=discord.ButtonStyle.primary, row=3)
    async def save(self, interaction: discord.Interaction, _b):
        config   = load_json(CONFIG_FILE, {})
        guild_id = str(self.guild.id)
        config.setdefault(guild_id, {}).update(self.cfg)
        config[guild_id].setdefault("exploits", GLOBAL_EXPLOITS)
        save_json(CONFIG_FILE, config)
        ch_id   = self.cfg.get("channel_id")
        role_id = self.cfg.get("role_id")
        enabled = self.cfg.get("enabled", False)
        channel = self.guild.get_channel(int(ch_id)) if ch_id and ch_id != "none" else None
        role    = self.guild.get_role(int(role_id))  if role_id else None
        embed = discord.Embed(title="⚙️ Configuración guardada", color=C_SUCCESS, timestamp=discord.utils.utcnow())
        embed.add_field(name="Canal",   value=channel.mention if channel else "No configurado", inline=True)
        embed.add_field(name="Rol",     value=role.mention    if role    else "Sin mención",    inline=True)
        embed.add_field(name="Alertas", value="✅ Activas"    if enabled else "🔕 Desactivadas", inline=True)
        embed.set_thumbnail(url=EMOJI_SUCCESS_URL)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — BYPASS
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="bypass", description="🔓 Bypass un enlace y obtén el destino real")
@app_commands.describe(url="El enlace a bypasear")
async def bypass_cmd(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        await interaction.response.send_message(
            embed=discord.Embed(description="⚠️ **URL inválida.** Provee un enlace `http://` o `https://` válido.", color=C_WARN), ephemeral=True)
        return
    start  = time.time()
    init_e = discord.Embed(title="[ Procesando ] KOD BYPASS",
                           description="```fix\nConectando con el servidor...\nEsto puede tardar unos segundos.\n```",
                           color=C_WARN, timestamp=discord.utils.utcnow())
    init_e.set_author(name="KOD BOT - Bypass Engine", icon_url=bot.user.display_avatar.url if bot.user else None)
    init_e.set_thumbnail(url=GIF_LOADING)
    init_e.set_footer(text=_footer(f"Solicitado por {interaction.user.name}"))
    try:
        await interaction.response.send_message(embed=init_e)
    except Exception:
        return
    loop = asyncio.get_running_loop()
    result, error = await loop.run_in_executor(None, bypass_url_vps, url)
    ms = int((time.time() - start) * 1000)
    try:
        if result:
            embed = build_bypass_result_embed(result, ms/1000)
            view  = BypassResultView(result)
            await interaction.edit_original_response(embed=embed, view=view)
            write_log(interaction.user.name, interaction.user.id, "/bypass", "Success", url[:80])
        else:
            err_e = discord.Embed(title="[ Fallido ] Bypass",
                                  description=f"```diff\n- {error or 'Error desconocido'}\n```\nVerifica el enlace o inténtalo más tarde.",
                                  color=C_ERROR, timestamp=discord.utils.utcnow())
            err_e.set_author(name="KOD BOT - Bypass Engine", icon_url=bot.user.display_avatar.url if bot.user else None)
            err_e.add_field(name="Enlace probado", value=f"```{url[:300]}```", inline=False)
            err_e.add_field(name="Tiempo",         value=f"`{ms}ms`",          inline=True)
            err_e.set_thumbnail(url=GIF_ERROR)
            err_e.set_footer(text=_footer())
            v = View()
            v.add_item(Button(label="Pide ayuda en Soporte", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
            await interaction.edit_original_response(embed=err_e, view=v)
            write_log(interaction.user.name, interaction.user.id, "/bypass", "Failed", url[:80])
    except Exception:
        pass


@bot.tree.command(name="setautobypass", description="⚙️ [Admin] Activar/desactivar auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def setautobypass_cmd(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        _save_autobypass()
        embed = discord.Embed(title="🔴 Auto-Bypass DESACTIVADO",
                              description=f"{interaction.channel.mention} ya no hará bypass automático.", color=C_ERROR)
    else:
        autobypass_channels.add(cid)
        _save_autobypass()
        embed = discord.Embed(title="🟢 Auto-Bypass ACTIVADO",
                              description=f"Cada enlace en {interaction.channel.mention} será bypasseado automáticamente.", color=C_SUCCESS)
    embed.set_footer(text=_footer(f"Canales activos: {len(autobypass_channels)}"))
    await interaction.response.send_message(embed=embed, ephemeral=True)

@setautobypass_cmd.error
async def setautobypass_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso de **Administrador**.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — EXECUTOR TRACKER
# ══════════════════════════════════════════════════════════════════

executors_group = app_commands.Group(name="executors", description="Información sobre exploits de Roblox")

@executors_group.command(name="stat", description="Estado de todos los exploits o de uno específico")
@app_commands.describe(nombre="Nombre del exploit (opcional)")
async def executors_stat(interaction: discord.Interaction, nombre: str = None):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id, {}).get("exploits", GLOBAL_EXPLOITS)

    if not nombre:
        lines = []
        for exp_name in guild_exploits:
            info = get_exploit_info(api_data, exp_name)
            if info:
                estado = info.get("status","Unknown")
                lines.append(f"{status_emoji(estado)} **{exp_name}** — {estado}")
            else:
                lines.append(f"⚪ **{exp_name}** — Sin datos")
        chunks, chunk = [], []
        for line in lines:
            chunk.append(line)
            if len(chunk) == 20:
                chunks.append("\n".join(chunk))
                chunk = []
        if chunk:
            chunks.append("\n".join(chunk))
        embed = discord.Embed(title="📋 Estado de todos los Exploits",
                              description=chunks[0] if chunks else "No hay exploits registrados.",
                              color=C_INFO, timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"Total: {len(guild_exploits)} exploits • Actualizado")
        await interaction.followup.send(embed=embed)
        for extra in chunks[1:]:
            await interaction.followup.send(embed=discord.Embed(description=extra, color=C_INFO))
        return

    info = get_exploit_info(api_data, nombre)
    if not info:
        await interaction.followup.send(f"❌ No se encontró **{nombre}**.", ephemeral=True)
        return
    estado   = info.get("status","Unknown")
    version  = info.get("version","N/A")
    platform = info.get("platform","N/A")
    updated  = info.get("updated_at", info.get("last_updated","N/A"))
    dl_link  = info.get("download", info.get("download_link", info.get("link",None)))
    color    = C_SUCCESS if estado.lower()=="online" else (C_ERROR if estado.lower()=="patched" else C_WARN)
    embed = discord.Embed(title=f"{status_emoji(estado)} {info.get('name',nombre)}",
                          color=color, timestamp=discord.utils.utcnow())
    embed.add_field(name="Estado",    value=estado,   inline=True)
    embed.add_field(name="Versión",   value=version,  inline=True)
    embed.add_field(name="Plataforma", value=platform, inline=True)
    embed.add_field(name="Última actualización", value=str(updated), inline=False)
    if dl_link:
        embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl_link})", inline=False)
    embed.set_thumbnail(url=EMOJI_GREEN_DOT if estado.lower()=="online" else EMOJI_GREEN_ARROW)
    embed.set_footer(text="Datos de api.weao.xyz")
    await interaction.followup.send(embed=embed)

bot.tree.add_command(executors_group)

# Bypass command group (extended)
bypass_group = app_commands.Group(name="bypass-info", description="Información de bypass de exploits")

@bypass_group.command(name="check", description="Verifica el estado de bypass de un exploit")
@app_commands.describe(exploit="Nombre del exploit")
async def bypass_check(interaction: discord.Interaction, exploit: str):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    info = get_exploit_info(api_data, exploit)
    if not info:
        await interaction.followup.send(f"❌ No se encontró **{exploit}**.", ephemeral=True)
        return
    nombre   = info.get("name", exploit)
    estado   = info.get("status","Unknown")
    version  = info.get("version","N/A")
    platform = info.get("platform","N/A")
    dl_link  = info.get("download", info.get("download_link", info.get("link",None)))
    is_on    = estado.lower() == "online"
    byfron   = info.get("byfron_bypass",   info.get("bypass",    is_on))
    hyperion = info.get("hyperion_bypass",  info.get("anti_cheat", is_on))
    luau     = info.get("luau_support",     True)
    ux       = info.get("ux_bypass",        is_on)
    embed = discord.Embed(title=f"🛡️ Bypass Info — {nombre}",
                          color=C_SUCCESS if is_on else C_ERROR, timestamp=discord.utils.utcnow())
    embed.add_field(name="Estado",          value=f"{status_emoji(estado)} {estado}", inline=True)
    embed.add_field(name="Versión",         value=version,                            inline=True)
    embed.add_field(name="Plataforma",      value=platform,                           inline=True)
    embed.add_field(name="Byfron Bypass",   value=bypass_emoji(byfron),               inline=True)
    embed.add_field(name="Hyperion Bypass", value=bypass_emoji(hyperion),             inline=True)
    embed.add_field(name="LuaU Support",    value=bypass_emoji(luau),                 inline=True)
    embed.add_field(name="UX Bypass",       value=bypass_emoji(ux),                   inline=True)
    if dl_link:
        embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl_link})",    inline=False)
    embed.set_thumbnail(url=EMOJI_GREEN_DOT if is_on else EMOJI_GREEN_ARROW)
    embed.set_footer(text="Datos de api.weao.xyz")
    await interaction.followup.send(embed=embed)

@bypass_group.command(name="working", description="Lista exploits con bypass activo ahora mismo")
async def bypass_working(interaction: discord.Interaction):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id, {}).get("exploits", GLOBAL_EXPLOITS)
    working = []
    for exp_name in guild_exploits:
        info = get_exploit_info(api_data, exp_name)
        if info and info.get("status","").lower() == "online":
            working.append(f"🟢 **{info.get('name',exp_name)}** — v`{info.get('version','N/A')}` | {info.get('platform','N/A')}")
    if not working:
        embed = discord.Embed(title="🛡️ Exploits con Bypass Activo",
                              description="⚠️ Ningún exploit está activo en este momento.", color=C_ERROR, timestamp=discord.utils.utcnow())
    else:
        chunks, chunk = [], []
        for line in working:
            chunk.append(line)
            if len(chunk) == 20:
                chunks.append("\n".join(chunk))
                chunk = []
        if chunk:
            chunks.append("\n".join(chunk))
        embed = discord.Embed(title=f"🛡️ Exploits con Bypass Activo ({len(working)})",
                              description=chunks[0], color=C_SUCCESS, timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"{len(working)} de {len(guild_exploits)} exploits activos")
    await interaction.followup.send(embed=embed)

@bypass_group.command(name="compare", description="Compara el bypass de dos exploits")
@app_commands.describe(exploit1="Primer exploit", exploit2="Segundo exploit")
async def bypass_compare(interaction: discord.Interaction, exploit1: str, exploit2: str):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    def get_fields(info, name):
        if not info:
            return {"nombre":name,"estado":"N/A","version":"N/A","byfron":False,"hyperion":False,"luau":False}
        st = info.get("status","Unknown")
        on = st.lower() == "online"
        return {"nombre":info.get("name",name),"estado":st,"version":info.get("version","N/A"),
                "byfron":info.get("byfron_bypass",on),"hyperion":info.get("hyperion_bypass",on),"luau":info.get("luau_support",True)}
    d1 = get_fields(get_exploit_info(api_data,exploit1), exploit1)
    d2 = get_fields(get_exploit_info(api_data,exploit2), exploit2)
    embed = discord.Embed(title="⚔️ Comparación de Bypass", color=0x9B59B6, timestamp=discord.utils.utcnow())
    for d, icon in [(d1,"🔹"),(d2,"🔸")]:
        embed.add_field(name=f"{icon} {d['nombre']}",
                        value=f"Estado: {status_emoji(d['estado'])} {d['estado']}\nVersioni: `{d['version']}`\nByfron: {bypass_emoji(d['byfron'])}\nHyperion: {bypass_emoji(d['hyperion'])}\nLuaU: {bypass_emoji(d['luau'])}",
                        inline=True)
    embed.set_footer(text="Datos de api.weao.xyz")
    await interaction.followup.send(embed=embed)

bot.tree.add_command(bypass_group)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — SUPPORTED / SET
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="supported", description="Lista de exploits vigilados en este servidor")
async def supported(interaction: discord.Interaction):
    config = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id,{}).get("exploits", GLOBAL_EXPLOITS)
    lines = [f"• {e}" for e in guild_exploits]
    chunks, chunk = [], []
    for line in lines:
        chunk.append(line)
        if len(chunk) == 30:
            chunks.append("\n".join(chunk))
            chunk = []
    if chunk:
        chunks.append("\n".join(chunk))
    embed = discord.Embed(title="🗂️ Exploits vigilados en este servidor",
                          description=chunks[0] if chunks else "No hay exploits configurados.",
                          color=C_INFO, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"Total: {len(guild_exploits)} exploits")
    await interaction.response.send_message(embed=embed)
    for extra in chunks[1:]:
        await interaction.followup.send(embed=discord.Embed(description=extra, color=C_INFO))


@bot.tree.command(name="set", description="⚙️ Configura las alertas automáticas de exploits")
@app_commands.default_permissions(manage_guild=True)
async def set_auto(interaction: discord.Interaction):
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    current  = config.get(guild_id, {})
    ch_val  = f"<#{current['channel_id']}>" if current.get("channel_id") else "No configurado"
    rol_val = f"<@&{current['role_id']}>"   if current.get("role_id")    else "Sin mención"
    al_val  = "✅ Activas" if current.get("enabled") else "🔕 Desactivadas"
    embed = discord.Embed(title="⚙️ Configuración de Alertas Automáticas",
                          description="Usa los menús para configurar el canal y el rol, luego guarda.", color=C_INFO)
    embed.add_field(name="Estado actual", value=f"Canal: {ch_val}\nRol: {rol_val}\nAlertas: {al_val}", inline=False)
    await interaction.response.send_message(embed=embed, view=SetupView(interaction.guild, current), ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — UTILIDAD
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="ping", description="🏓 Ver la latencia del bot")
async def ping_cmd(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    color = C_SUCCESS if ms < 100 else (C_WARN if ms < 200 else C_ERROR)
    e = discord.Embed(title="🏓 ¡Pong!", description=f"Latencia: `{ms}ms`", color=color)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="info", description="🤖 Información del bot")
async def info_cmd(interaction: discord.Interaction):
    cmd_count = len(bot.tree.get_commands())
    e = discord.Embed(title="🤖 Información del Bot", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="📛 Nombre",     value=f"`{BOT_NAME}`",        inline=True)
    e.add_field(name="👑 Creador",    value="`KING`",               inline=True)
    e.add_field(name="📚 Librería",   value="`discord.py 2.3+`",    inline=True)
    e.add_field(name="🌐 Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="⚡ Comandos",   value=f"`{cmd_count}`",       inline=True)
    e.add_field(name="⏱️ Uptime",     value=f"`{format_uptime(BOT_START_TIME)}`", inline=True)
    e.add_field(name="📡 Latencia",   value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="uptime", description="⏱️ Tiempo activo del bot")
async def uptime_cmd(interaction: discord.Interaction):
    e = discord.Embed(title="⏱️ Tiempo Activo", description=f"El bot lleva encendido:\n\n**`{format_uptime(BOT_START_TIME)}`**",
                      color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="stats", description="📊 [Admin] Estadísticas del bot")
async def stats_cmd(interaction: discord.Interaction):
    if not is_owner_or_admin(interaction):
        await interaction.response.send_message("🚫 Solo el dueño o admins.", ephemeral=True)
        return
    e = discord.Embed(title="📊 Estadísticas del Bot", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="🌐 Servidores", value=f"`{len(bot.guilds)}`",                                    inline=True)
    e.add_field(name="👥 Usuarios",   value=f"`{sum(g.member_count or 0 for g in bot.guilds):,}`",     inline=True)
    e.add_field(name="⏱️ Uptime",     value=f"`{format_uptime(BOT_START_TIME)}`",                      inline=True)
    e.add_field(name="📡 Latencia",   value=f"`{round(bot.latency*1000)}ms`",                          inline=True)
    e.set_footer(text=_footer())
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="serverinfo", description="📋 Información del servidor")
async def serverinfo_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ Solo en servidores.", ephemeral=True)
        return
    g = interaction.guild
    e = discord.Embed(title=f"📋 {g.name}", color=C_WARN, timestamp=discord.utils.utcnow())
    e.add_field(name="👑 Dueño",    value=g.owner.mention if g.owner else "Desconocido", inline=True)
    e.add_field(name="👥 Miembros", value=f"`{g.member_count}`",   inline=True)
    e.add_field(name="📁 Canales",  value=f"`{len(g.channels)}`",  inline=True)
    e.add_field(name="🎭 Roles",    value=f"`{len(g.roles)}`",     inline=True)
    e.add_field(name="😀 Emojis",   value=f"`{len(g.emojis)}`",    inline=True)
    e.add_field(name="🆙 Boosts",   value=f"`{g.premium_subscription_count}`", inline=True)
    e.add_field(name="📅 Creado",   value=f"<t:{int(g.created_at.timestamp())}:R>", inline=False)
    e.add_field(name="🆔 ID",       value=f"`{g.id}`",             inline=True)
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="avatar", description="🖼️ Ver el avatar de un usuario")
@app_commands.describe(miembro="Usuario (opcional, por defecto tú)")
async def avatar_cmd(interaction: discord.Interaction, miembro: discord.Member = None):
    target = miembro or interaction.user
    e = discord.Embed(title=f"🖼️ Avatar de {target.display_name}", color=C_AUTO)
    e.set_image(url=target.display_avatar.url)
    e.set_footer(text=_footer(f"ID: {target.id}"))
    v = View()
    v.add_item(Button(label="Abrir en navegador", url=target.display_avatar.url, style=discord.ButtonStyle.link, emoji="🖼️"))
    await interaction.response.send_message(embed=e, view=v)

@bot.tree.command(name="userinfo", description="👤 Información detallada de un miembro")
@app_commands.describe(miembro="Miembro a consultar (opcional)")
async def userinfo_cmd(interaction: discord.Interaction, miembro: discord.Member = None):
    target = miembro or interaction.user
    color  = target.top_role.color if isinstance(target, discord.Member) and target.top_role else C_INFO
    roles  = [r.mention for r in target.roles if r.name != "@everyone"][:10]
    e      = discord.Embed(title=f"👤 {target.display_name}", color=color, timestamp=discord.utils.utcnow())
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="🆔 ID",            value=f"`{target.id}`",              inline=True)
    e.add_field(name="🤖 Es Bot",        value="✅" if target.bot else "❌",  inline=True)
    e.add_field(name="📅 Cuenta Creada", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=False)
    if isinstance(target, discord.Member) and target.joined_at:
        e.add_field(name="📥 Se Unió",      value=f"<t:{int(target.joined_at.timestamp())}:R>", inline=False)
        e.add_field(name="🎭 Rol Más Alto", value=target.top_role.mention, inline=True)
    if roles:
        e.add_field(name=f"🏷️ Roles ({len(roles)})", value=" ".join(roles), inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="say", description="📢 [Admin] Enviar un mensaje como el bot")
@app_commands.describe(message="El mensaje a enviar")
async def say_cmd(interaction: discord.Interaction, message: str):
    if not is_owner_or_admin(interaction):
        await interaction.response.send_message("🚫 Solo el dueño o admins.", ephemeral=True)
        return
    if not message.strip() or len(message) > 2000:
        await interaction.response.send_message("⚠️ Mensaje vacío o muy largo (máx 2000 chars).", ephemeral=True)
        return
    await interaction.response.send_message("✅ Mensaje enviado.", ephemeral=True)
    await interaction.channel.send(message)

@bot.tree.command(name="help", description="📖 Ver todos los comandos del bot")
async def help_cmd(interaction: discord.Interaction):
    e = discord.Embed(title=f"📖 {BOT_NAME} — Lista de Comandos",
                      description=f"Support: [Únete]({SUPPORT_SERVER_URL})",
                      color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="🔓 Bypass",        value="`/bypass` `/setautobypass` `/bypass-info check` `/bypass-info working` `/bypass-info compare`", inline=False)
    e.add_field(name="🎮 Executors",     value="`/executors stat` `/supported` `/set`",                         inline=False)
    e.add_field(name="📊 Utilidad",      value="`/info` `/ping` `/stats` `/uptime` `/serverinfo` `/avatar` `/userinfo` `/say`", inline=False)
    e.add_field(name="🛡️ Moderación",   value="`/clear` `/kick` `/ban` `/unban` `/slowmode` `/lock` `/unlock` `/timeout` `/warn` `/warnings`\n`/ban-member` `/kick-member` `/timeout-member` `/remove-timeout` `/warn-member` `/view-warnings` `/clear-messages` `/lock-channel` `/unlock-channel`", inline=False)
    e.add_field(name="🎲 Diversión",     value="`/random` `/coinflip` `/dice` `/8ball` `/meme` `/cat` `/dog` `/trivia` `/joke` `/meow`", inline=False)
    e.add_field(name="🎮 Roblox",        value="`/roblox_user` `/roblox_id` `/joinserver` `/generar_servidor`", inline=False)
    e.add_field(name="🤖 IA",            value="`/ai-chat` `/ask-ai` `/translate-text` `/summarize-text` `/generate-image` `/set-ia-channel`", inline=False)
    e.add_field(name="🎉 Giveaways",     value="`/start-giveaway` `/create-poll`",                              inline=False)
    e.add_field(name="⚙️ Configuración", value="`/welcome-setup` `/goodbye-setup` `/auto-role` `/verification-setup` `/reaction-roles`\n`/logs-setup` `/moderation-logs` `/join-logs` `/message-logs`\n`/server-setup` `/server-settings` `/permissions-setup`\n`/create-embed` `/report-user`", inline=False)
    e.set_footer(text=_footer())
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
    v = View()
    v.add_item(Button(label="Servidor de Soporte", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, emoji="💬"))
    await interaction.response.send_message(embed=e, view=v)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — MODERACIÓN
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="clear", description="🧹 [Mod] Eliminar mensajes del canal")
@app_commands.describe(cantidad="Cantidad de mensajes (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_cmd(interaction: discord.Interaction, cantidad: int):
    if not 1 <= cantidad <= 100:
        await interaction.response.send_message("⚠️ Valor entre 1 y 100.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=cantidad)
    e = _mod_embed("🧹 Mensajes Eliminados", f"Se eliminaron **{len(deleted)}** mensajes.", C_SUCCESS)
    await interaction.followup.send(embed=e, ephemeral=True)

@clear_cmd.error
async def _clear_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Mensajes**.", ephemeral=True)

@bot.tree.command(name="kick", description="👢 [Mod] Expulsar un usuario")
@app_commands.describe(miembro="Usuario", razon="Razón")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_cmd(interaction: discord.Interaction, miembro: discord.Member, razon: str = "Sin razón"):
    try:
        await miembro.kick(reason=razon)
        await interaction.response.send_message(embed=_mod_embed("👢 Usuario Expulsado", f"**{miembro}** expulsado.\n**Razón:** {razon}"), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ No puedo expulsar a ese usuario.", ephemeral=True)

@kick_cmd.error
async def _kick_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Expulsar Miembros**.", ephemeral=True)

@bot.tree.command(name="ban", description="🔨 [Mod] Banear un usuario")
@app_commands.describe(miembro="Usuario", razon="Razón")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_cmd(interaction: discord.Interaction, miembro: discord.Member, razon: str = "Sin razón"):
    try:
        await miembro.ban(reason=razon, delete_message_days=0)
        await interaction.response.send_message(embed=_mod_embed("🔨 Usuario Baneado", f"**{miembro}** baneado.\n**Razón:** {razon}"), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ No puedo banear a ese usuario.", ephemeral=True)

@ban_cmd.error
async def _ban_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Banear Miembros**.", ephemeral=True)

@bot.tree.command(name="unban", description="✅ [Mod] Desbanear por ID")
@app_commands.describe(user_id="ID del usuario baneado")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_cmd(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=_mod_embed("✅ Usuario Desbaneado", f"**{user}** desbaneado.", C_SUCCESS), ephemeral=True)
    except (ValueError, discord.NotFound):
        await interaction.response.send_message("❌ ID inválido o usuario no baneado.", ephemeral=True)

@unban_cmd.error
async def _unban_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Banear Miembros**.", ephemeral=True)

@bot.tree.command(name="slowmode", description="🐌 [Mod] Modo lento en el canal")
@app_commands.describe(segundos="Segundos (0 para desactivar, máx 21600)")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode_cmd(interaction: discord.Interaction, segundos: int):
    if not 0 <= segundos <= 21600:
        await interaction.response.send_message("⚠️ Valor entre 0 y 21600.", ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=segundos)
    color = C_SUCCESS if segundos == 0 else C_WARN
    desc  = f"Modo lento desactivado." if segundos == 0 else f"Modo lento de **{segundos}s** activado."
    await interaction.response.send_message(embed=_mod_embed("🐌 Slowmode", desc, color), ephemeral=True)

@slowmode_cmd.error
async def _slow_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Canales**.", ephemeral=True)

@bot.tree.command(name="lock", description="🔒 [Mod] Cerrar el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock_cmd(interaction: discord.Interaction):
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
    await interaction.response.send_message(embed=_mod_embed("🔒 Canal Cerrado", f"{interaction.channel.mention} ha sido cerrado."))

@lock_cmd.error
async def _lock_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Canales**.", ephemeral=True)

@bot.tree.command(name="unlock", description="🔓 [Mod] Abrir el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock_cmd(interaction: discord.Interaction):
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
    await interaction.response.send_message(embed=_mod_embed("🔓 Canal Abierto", f"{interaction.channel.mention} está abierto.", C_SUCCESS))

@unlock_cmd.error
async def _unlock_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Canales**.", ephemeral=True)

@bot.tree.command(name="timeout", description="⏱️ [Mod] Silenciar usuario temporalmente")
@app_commands.describe(miembro="Usuario", minutos="Duración en minutos (1-40320)", razon="Razón")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_cmd(interaction: discord.Interaction, miembro: discord.Member, minutos: int, razon: str = "Sin razón"):
    if not 1 <= minutos <= 40320:
        await interaction.response.send_message("⚠️ Valor entre 1 y 40320 minutos.", ephemeral=True)
        return
    await miembro.timeout(discord.utils.utcnow() + timedelta(minutes=minutos), reason=razon)
    await interaction.response.send_message(embed=_mod_embed("⏱️ Timeout Aplicado", f"**{miembro}** silenciado **{minutos}min**.\n**Razón:** {razon}"), ephemeral=True)

@timeout_cmd.error
async def _to_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Silenciar Miembros**.", ephemeral=True)

@bot.tree.command(name="warn", description="⚠️ [Mod] Advertir a un usuario")
@app_commands.describe(miembro="Usuario", razon="Razón")
@app_commands.checks.has_permissions(kick_members=True)
async def warn_cmd(interaction: discord.Interaction, miembro: discord.Member, razon: str = "Sin razón"):
    gid, uid = str(interaction.guild_id), str(miembro.id)
    _warnings.setdefault(gid,{}).setdefault(uid,[]).append({"mod":str(interaction.user.id),"reason":razon,"ts":int(time.time())})
    _save_warnings()
    count = len(_warnings[gid][uid])
    e = discord.Embed(title="⚠️ Advertencia Registrada", color=C_WARN, timestamp=discord.utils.utcnow())
    e.description = f"**{miembro}** recibió una advertencia.\n**Razón:** {razon}\n**Total:** `{count}`"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)
    try:
        dm_e = discord.Embed(title="⚠️ Has recibido una advertencia", color=C_WARN)
        dm_e.description = f"**Servidor:** {interaction.guild.name}\n**Razón:** {razon}\n**Total:** `{count}`"
        await miembro.send(embed=dm_e)
    except Exception:
        pass

@warn_cmd.error
async def _warn_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Expulsar Miembros**.", ephemeral=True)

@bot.tree.command(name="warnings", description="📋 [Mod] Ver advertencias de un usuario")
@app_commands.describe(miembro="Usuario")
@app_commands.checks.has_permissions(kick_members=True)
async def warnings_cmd(interaction: discord.Interaction, miembro: discord.Member):
    gid, uid = str(interaction.guild_id), str(miembro.id)
    warns = _warnings.get(gid,{}).get(uid,[])
    if not warns:
        e = discord.Embed(title="📋 Sin Advertencias", description=f"**{miembro}** no tiene advertencias.", color=C_SUCCESS)
        await interaction.response.send_message(embed=e, ephemeral=True)
        return
    e = discord.Embed(title=f"📋 Warns de {miembro.display_name}", color=C_WARN, timestamp=discord.utils.utcnow())
    for i, w in enumerate(warns[-10:], 1):
        e.add_field(name=f"⚠️ #{i}", value=f"**Razón:** {w['reason']}\n**Mod:** <@{w['mod']}>\n**Fecha:** <t:{w['ts']}:R>", inline=False)
    e.set_footer(text=_footer(f"Total: {len(warns)}"))
    await interaction.response.send_message(embed=e, ephemeral=True)

@warnings_cmd.error
async def _warnings_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Expulsar Miembros**.", ephemeral=True)

# Extended mod commands (with dash)
@bot.tree.command(name="ban-member", description="🔨 [Mod] Banear miembro (con log)")
@app_commands.describe(usuario="Usuario", razon="Razón", eliminar_mensajes="Días de mensajes a borrar (0-7)")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_member_cmd(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón", eliminar_mensajes: int = 0):
    if usuario.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("🚫 No puedes banear a alguien con igual/mayor rol.", ephemeral=True)
    await interaction.response.defer()
    await usuario.ban(reason=f"{razon} | Mod: {interaction.user}", delete_message_days=min(eliminar_mensajes,7))
    e = discord.Embed(title="〔 🔨 〕 Miembro Baneado", color=C_ERROR, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Usuario",    value=f"`{usuario}` (`{usuario.id}`)", inline=True)
    e.add_field(name="🛡️ Moderador", value=interaction.user.mention,        inline=True)
    e.add_field(name="📋 Razón",      value=razon,                           inline=False)
    e.set_thumbnail(url=usuario.display_avatar.url)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e)
    await _send_mod_log(interaction.guild, e)

@ban_member_cmd.error
async def ban_member_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Banear Miembros**.", ephemeral=True)

@bot.tree.command(name="kick-member", description="👢 [Mod] Expulsar miembro (con log)")
@app_commands.describe(usuario="Usuario", razon="Razón")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_member_cmd(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón"):
    if usuario.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("🚫 No puedes expulsar a alguien con igual/mayor rol.", ephemeral=True)
    await interaction.response.defer()
    await usuario.kick(reason=f"{razon} | Mod: {interaction.user}")
    e = discord.Embed(title="〔 👢 〕 Miembro Expulsado", color=C_WARN, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Usuario",    value=f"`{usuario}`",             inline=True)
    e.add_field(name="🛡️ Moderador", value=interaction.user.mention,   inline=True)
    e.add_field(name="📋 Razón",      value=razon,                      inline=False)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e)
    await _send_mod_log(interaction.guild, e)

@kick_member_cmd.error
async def kick_member_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Expulsar Miembros**.", ephemeral=True)

@bot.tree.command(name="timeout-member", description="⏱️ [Mod] Silenciar miembro (con log)")
@app_commands.describe(usuario="Usuario", minutos="Duración en minutos", razon="Razón")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_member_cmd(interaction: discord.Interaction, usuario: discord.Member, minutos: int = 10, razon: str = "Sin razón"):
    await interaction.response.defer()
    await usuario.timeout(discord.utils.utcnow() + timedelta(minutes=minutos), reason=f"{razon} | Mod: {interaction.user}")
    e = discord.Embed(title="〔 ⏱️ 〕 Timeout Aplicado", color=C_WARN, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Usuario",    value=f"`{usuario}`",             inline=True)
    e.add_field(name="⏱️ Duración",  value=f"`{minutos}m`",            inline=True)
    e.add_field(name="🛡️ Moderador", value=interaction.user.mention,   inline=True)
    e.add_field(name="📋 Razón",      value=razon,                      inline=False)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e)
    await _send_mod_log(interaction.guild, e)

@timeout_member_cmd.error
async def timeout_member_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Silenciar Miembros**.", ephemeral=True)

@bot.tree.command(name="remove-timeout", description="✅ [Mod] Quitar timeout a un miembro")
@app_commands.describe(usuario="Usuario", razon="Razón")
@app_commands.checks.has_permissions(moderate_members=True)
async def remove_timeout_cmd(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón"):
    await interaction.response.defer()
    await usuario.timeout(None, reason=f"{razon} | Mod: {interaction.user}")
    e = discord.Embed(title="〔 ✅ 〕 Timeout Removido", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Usuario",    value=f"`{usuario}`",             inline=True)
    e.add_field(name="🛡️ Moderador", value=interaction.user.mention,   inline=True)
    e.add_field(name="📋 Razón",      value=razon,                      inline=False)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e)

@remove_timeout_cmd.error
async def remove_timeout_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Silenciar Miembros**.", ephemeral=True)

@bot.tree.command(name="warn-member", description="⚠️ [Mod] Advertir miembro (con log)")
@app_commands.describe(usuario="Usuario", razon="Razón")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn_member_cmd(interaction: discord.Interaction, usuario: discord.Member, razon: str):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    _warnings.setdefault(gid,{}).setdefault(uid,[]).append({"razon":razon,"mod":str(interaction.user),"timestamp":datetime.now(timezone.utc).isoformat()})
    _save_warnings()
    count = len(_warnings[gid][uid])
    e = discord.Embed(title="〔 ⚠️ 〕 Advertencia Registrada", color=C_WARN, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Usuario",      value=usuario.mention,           inline=True)
    e.add_field(name="⚠️ Total Warns", value=f"`{count}`",              inline=True)
    e.add_field(name="🛡️ Moderador",   value=interaction.user.mention,  inline=True)
    e.add_field(name="📋 Razón",        value=razon,                     inline=False)
    e.set_thumbnail(url=usuario.display_avatar.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)
    await _send_mod_log(interaction.guild, e)

@warn_member_cmd.error
async def warn_member_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Silenciar Miembros**.", ephemeral=True)

@bot.tree.command(name="view-warnings", description="📋 Ver advertencias de un miembro")
@app_commands.describe(usuario="Usuario")
async def view_warnings_cmd(interaction: discord.Interaction, usuario: discord.Member):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warns    = _warnings.get(gid,{}).get(uid,[])
    e = discord.Embed(title=f"〔 📋 〕 Advertencias de {usuario.display_name}", color=C_WARN, timestamp=discord.utils.utcnow())
    e.set_thumbnail(url=usuario.display_avatar.url)
    if not warns:
        e.description = "✅ Sin advertencias."
    else:
        for i, w in enumerate(warns[-10:], 1):
            e.add_field(name=f"#{i}", value=f"**{w.get('razon',w.get('reason','?'))}**\n*Mod: {w.get('mod','?')}*", inline=True)
    e.set_footer(text=_footer(f"Total: {len(warns)}"))
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="clear-messages", description="🗑️ [Mod] Eliminar mensajes del canal")
@app_commands.describe(cantidad="Número de mensajes (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_messages_cmd(interaction: discord.Interaction, cantidad: int = 10):
    if not 1 <= cantidad <= 100:
        return await interaction.response.send_message("⚠️ Entre 1 y 100.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=cantidad)
    e = discord.Embed(title="〔 🗑️ 〕 Mensajes Eliminados",
                      description=f"```diff\n+ {len(deleted)} mensajes eliminados\n```", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer(f"Por {interaction.user.name}"))
    await interaction.followup.send(embed=e, ephemeral=True)

@clear_messages_cmd.error
async def clear_messages_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Mensajes**.", ephemeral=True)

@bot.tree.command(name="lock-channel", description="🔒 [Mod] Bloquear el canal actual")
@app_commands.describe(razon="Razón del bloqueo")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock_channel_cmd(interaction: discord.Interaction, razon: str = "Sin razón"):
    await interaction.response.defer()
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow, reason=razon)
    e = discord.Embed(title="〔 🔒 〕 Canal Bloqueado", description=f"**Razón:** {razon}", color=C_ERROR, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer(f"Por {interaction.user.name}"))
    await interaction.followup.send(embed=e)

@lock_channel_cmd.error
async def lock_channel_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Canales**.", ephemeral=True)

@bot.tree.command(name="unlock-channel", description="🔓 [Mod] Desbloquear el canal actual")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock_channel_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
    e = discord.Embed(title="〔 🔓 〕 Canal Desbloqueado", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer(f"Por {interaction.user.name}"))
    await interaction.followup.send(embed=e)

@unlock_channel_cmd.error
async def unlock_channel_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Canales**.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — DIVERSIÓN
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="random", description="🎲 Generar un número aleatorio")
@app_commands.describe(minimo="Mínimo (default 1)", maximo="Máximo (default 100)")
async def random_cmd(interaction: discord.Interaction, minimo: int = 1, maximo: int = 100):
    if minimo > maximo:
        await interaction.response.send_message("⚠️ El mínimo no puede ser mayor que el máximo.", ephemeral=True)
        return
    num = random.randint(minimo, maximo)
    e = discord.Embed(title="🎲 Número Aleatorio", description=f"Entre **{minimo}** y **{maximo}**:\n\n# `{num}`", color=C_SUCCESS)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="coinflip", description="🪙 Lanzar una moneda")
async def coinflip_cmd(interaction: discord.Interaction):
    result = random.choice(["🦅 Cara", "📀 Cruz"])
    e = discord.Embed(title="🪙 Lanzamiento de Moneda", description=f"## **{result}**", color=C_WARN)
    e.set_thumbnail(url=GIF_COIN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="dice", description="🎯 Lanzar un dado")
@app_commands.describe(caras="Caras (4-100, default 6)")
async def dice_cmd(interaction: discord.Interaction, caras: int = 6):
    if not 4 <= caras <= 100:
        await interaction.response.send_message("⚠️ Caras entre 4 y 100.", ephemeral=True)
        return
    result = random.randint(1, caras)
    e = discord.Embed(title="🎯 Dado Lanzado", description=f"Dado d{caras}:\n\n# `{result}`", color=C_SUCCESS)
    e.set_thumbnail(url=GIF_FUN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="8ball", description="🎱 Pregunta a la bola mágica")
@app_commands.describe(pregunta="Tu pregunta")
async def ball8_cmd(interaction: discord.Interaction, pregunta: str):
    e = discord.Embed(title="🎱 Bola Mágica", color=0x2B2D31)
    e.add_field(name="❓ Pregunta",  value=pregunta,                           inline=False)
    e.add_field(name="🔮 Respuesta", value=f"**{random.choice(BALL8_RESPONSES)}**", inline=False)
    e.set_thumbnail(url=GIF_BALL8)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="meme", description="😂 Meme aleatorio de Reddit")
async def meme_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    sub = random.choice(["memes","dankmemes","me_irl","AdviceAnimals"])
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://www.reddit.com/r/{sub}/random.json?limit=1",
                                   headers={"User-Agent":"KodBot/2.0"}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ No se pudo obtener el meme.", ephemeral=True)
                    return
                data = await resp.json()
                post = data[0]["data"]["children"][0]["data"]
                title  = post.get("title","Sin título")[:200]
                img    = post.get("url","")
                author = post.get("author","desconocido")
                if not img.lower().endswith((".jpg",".jpeg",".png",".gif")):
                    await interaction.followup.send("❌ Sin imagen. Intenta de nuevo.", ephemeral=True)
                    return
                e = discord.Embed(title=f"😂 {title}", color=C_FUN)
                e.set_image(url=img)
                e.set_footer(text=_footer(f"👤 u/{author} • r/{sub}"))
                await interaction.followup.send(embed=e)
    except Exception as ex:
        await interaction.followup.send("❌ Error al obtener meme.", ephemeral=True)

@bot.tree.command(name="cat", description="🐱 Foto aleatoria de un gato")
async def cat_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                e = discord.Embed(title="🐱 ¡Gato Aleatorio!", color=0xFFB6C1)
                e.set_image(url=data[0]["url"])
                e.set_footer(text=_footer("TheCatAPI"))
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener foto de gato.", ephemeral=True)

@bot.tree.command(name="dog", description="🐶 Foto aleatoria de un perro")
async def dog_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                e = discord.Embed(title="🐶 ¡Perro Aleatorio!", color=0xD2B48C)
                e.set_image(url=data["message"])
                e.set_footer(text=_footer("dog.ceo"))
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener foto de perro.", ephemeral=True)

@bot.tree.command(name="trivia", description="🧠 Pregunta de cultura general")
async def trivia_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://opentdb.com/api.php?amount=1&type=multiple&encode=url3986", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("response_code",1) != 0:
                    await interaction.followup.send("❌ No se pudo obtener pregunta.", ephemeral=True)
                    return
                item      = data["results"][0]
                question  = unquote(item["question"])
                correct   = unquote(item["correct_answer"])
                incorrect = [unquote(a) for a in item["incorrect_answers"]]
                category  = unquote(item["category"])
                difficulty = unquote(item["difficulty"]).capitalize()
                options = incorrect + [correct]
                random.shuffle(options)
                letters = ["🇦","🇧","🇨","🇩"]
                opts_text = "\n".join(f"{letters[i]} {op}" for i,op in enumerate(options))
                e = discord.Embed(title="🧠 Trivia", color=C_AUTO, timestamp=discord.utils.utcnow())
                e.add_field(name="❓ Pregunta",    value=question,   inline=False)
                e.add_field(name="📝 Opciones",    value=opts_text,  inline=False)
                e.add_field(name="📚 Categoría",   value=category,   inline=True)
                e.add_field(name="⚡ Dificultad",  value=difficulty, inline=True)
                e.set_footer(text=_footer("Respuesta oculta • ¡Piensa bien!"))
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener trivia.", ephemeral=True)

@bot.tree.command(name="joke", description="😄 Chiste aleatorio")
async def joke_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://official-joke-api.appspot.com/random_joke", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                e = discord.Embed(title="😄 Chiste", color=C_WARN)
                e.add_field(name="❓ Setup",    value=data["setup"],    inline=False)
                e.add_field(name="😂 Punchline", value=data["punchline"], inline=False)
                e.set_footer(text=_footer())
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener chiste.", ephemeral=True)

@bot.tree.command(name="meow", description="🐱 Dato curioso sobre gatos")
async def meow_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://catfact.ninja/fact", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                e = discord.Embed(title="🐱 Dato Felino", description=data.get("fact","Los gatos son increíbles 🐱"),
                                  color=0xFFB6C1)
                e.set_thumbnail(url=GIF_CAT)
                e.set_footer(text=_footer("catfact.ninja"))
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — ROBLOX
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="roblox_user", description="🎮 Buscar usuario de Roblox por nombre")
@app_commands.describe(nombre="Nombre del usuario")
async def roblox_user_cmd(interaction: discord.Interaction, nombre: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://users.roblox.com/v1/users/search?keyword={quote(nombre)}&limit=5", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data  = await resp.json()
                users = data.get("data",[])
                if not users:
                    await interaction.followup.send("❌ No se encontraron usuarios.", ephemeral=True)
                    return
                e = discord.Embed(title=f"🎮 Resultados: '{nombre}'", color=C_ROBLOX)
                e.set_thumbnail(url=GIF_ROBLOX)
                for u in users[:5]:
                    uid = u["id"]
                    e.add_field(name=f"👤 {u.get('displayName',u['name'])} (@{u['name']})",
                                value=f"🆔 `{uid}` • [Ver Perfil](https://www.roblox.com/users/{uid}/profile)", inline=False)
                e.set_footer(text=_footer())
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al buscar usuario de Roblox.", ephemeral=True)

@bot.tree.command(name="roblox_id", description="🆔 Info de Roblox por ID")
@app_commands.describe(user_id="ID del usuario de Roblox")
async def roblox_id_cmd(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer()
    try:
        uid = int(user_id)
    except ValueError:
        await interaction.followup.send("⚠️ El ID debe ser numérico.", ephemeral=True)
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://users.roblox.com/v1/users/{uid}", timeout=aiohttp.ClientTimeout(total=10)) as r1:
                if r1.status != 200:
                    await interaction.followup.send("❌ Usuario no encontrado.", ephemeral=True)
                    return
                user_data = await r1.json()
            async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png", timeout=aiohttp.ClientTimeout(total=10)) as r2:
                thumb_data = await r2.json()
                thumb = thumb_data.get("data",[{}])[0].get("imageUrl","")
        name        = user_data.get("name","Desconocido")
        display     = user_data.get("displayName", name)
        description = user_data.get("description","Sin descripción") or "Sin descripción"
        banned      = user_data.get("isBanned", False)
        created_raw = user_data.get("created","")
        e = discord.Embed(title=f"🎮 {display} (@{name})", color=C_ROBLOX)
        e.add_field(name="🆔 ID",      value=f"`{uid}`",               inline=True)
        e.add_field(name="🚫 Baneado", value="Sí" if banned else "No", inline=True)
        e.add_field(name="📝 Bio",     value=description[:200],         inline=False)
        e.add_field(name="🔗 Perfil",  value=f"[Ver en Roblox](https://www.roblox.com/users/{uid}/profile)", inline=False)
        if created_raw:
            try:
                dt = datetime.fromisoformat(created_raw.replace("Z","+00:00"))
                e.add_field(name="📅 Creado", value=f"<t:{int(dt.timestamp())}:R>", inline=True)
            except Exception:
                pass
        if thumb:
            e.set_thumbnail(url=thumb)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener info del usuario.", ephemeral=True)

@bot.tree.command(name="joinserver", description="🔗 Generar enlace de servidor privado de Roblox")
@app_commands.describe(game_id="ID del juego", server_code="Código del servidor privado")
async def joinserver_cmd(interaction: discord.Interaction, game_id: str, server_code: str):
    link = f"https://www.roblox.com/games/{game_id}?privateServerLinkCode={server_code}"
    e = discord.Embed(title="🔗 Enlace de Servidor Roblox", color=C_ROBLOX)
    e.add_field(name="🎮 Game ID", value=f"`{game_id}`",    inline=True)
    e.add_field(name="🔑 Código",  value=f"`{server_code}`", inline=True)
    e.add_field(name="🌐 Enlace",  value=f"[Unirse al Servidor]({link})", inline=False)
    e.set_thumbnail(url=GIF_ROBLOX)
    e.set_footer(text=_footer())
    v = View()
    v.add_item(Button(label="Unirse al Servidor", url=link, style=discord.ButtonStyle.link, emoji="🎮"))
    await interaction.response.send_message(embed=e, view=v)

@bot.tree.command(name="generar_servidor", description="🎮 [Roblox] Crear servidor privado vía API")
@app_commands.describe(game_id="ID del juego de Roblox")
async def generar_servidor_cmd(interaction: discord.Interaction, game_id: str):
    if not ROBLOX_API_KEY:
        await interaction.response.send_message(
            embed=discord.Embed(title="⚠️ API Key Requerida",
                                description="Agrega `ROBLOX_API_KEY` en variables de entorno.", color=C_WARN), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://games.roblox.com/v1/games/{game_id}/servers/private",
                                    headers={"x-api-key":ROBLOX_API_KEY,"Content-Type":"application/json"},
                                    json={}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                join_link = data.get("joinLink") or data.get("accessCode")
                if not join_link:
                    await interaction.followup.send(f"❌ No se pudo crear: `{data}`", ephemeral=True)
                    return
                e = discord.Embed(title="🎮 Servidor Privado Creado", color=C_SUCCESS)
                e.add_field(name="🔗 Enlace", value=f"[Unirse]({join_link})", inline=False)
                e.set_thumbnail(url=GIF_ROBLOX)
                e.set_footer(text=_footer())
                v = View()
                v.add_item(Button(label="Unirse al Servidor", url=join_link, style=discord.ButtonStyle.link, emoji="🎮"))
                await interaction.followup.send(embed=e, view=v, ephemeral=True)
    except Exception:
        await interaction.followup.send("❌ Error al crear servidor privado.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — IA
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="set-ia-channel", description="🤖 [Admin] Activar/desactivar IA auto-respuesta en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def set_ia_channel_cmd(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in ia_channels:
        ia_channels.discard(cid)
        _save_ia()
        e = discord.Embed(title="〔 🔴 〕 Canal IA Desactivado", description=f"{interaction.channel.mention} ya no responderá con IA.", color=C_ERROR)
    else:
        ia_channels.add(cid)
        _save_ia()
        e = discord.Embed(title="〔 🟢 〕 Canal IA Activado",
                          description=f"{interaction.channel.mention} ahora responderá con IA Groq.\n```yaml\nModelo : llama3-8b-8192\nCanales activos : {len(ia_channels)}\n```", color=C_SUCCESS)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@set_ia_channel_cmd.error
async def set_ia_channel_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso de **Administrador**.", ephemeral=True)

@bot.tree.command(name="ai-chat", description="🤖 Habla con la IA (Groq)")
@app_commands.describe(mensaje="Tu mensaje")
async def ai_chat_cmd(interaction: discord.Interaction, mensaje: str):
    await interaction.response.defer()
    reply = await _ask_groq(mensaje)
    e = discord.Embed(title="〔 🤖 〕 KOD BOT IA", color=C_INFO, timestamp=discord.utils.utcnow())
    e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    e.add_field(name="💬 Tu mensaje", value=f"```{mensaje[:500]}```", inline=False)
    e.add_field(name="🤖 Respuesta",  value=reply[:1000],             inline=False)
    e.set_footer(text=_footer("Groq • llama3-8b"))
    await interaction.followup.send(embed=e)

@bot.tree.command(name="ask-ai", description="❓ Pregúntale algo a la IA")
@app_commands.describe(pregunta="Tu pregunta")
async def ask_ai_cmd(interaction: discord.Interaction, pregunta: str):
    await interaction.response.defer()
    reply = await _ask_groq(pregunta, system="Eres un asistente experto. Responde de forma precisa y concisa en español.")
    e = discord.Embed(title="〔 ❓ 〕 Respuesta IA", description=reply[:2000], color=C_INFO, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer(f"Pregunta de {interaction.user.name}"))
    await interaction.followup.send(embed=e)

@bot.tree.command(name="translate-text", description="🌐 Traduce texto a cualquier idioma")
@app_commands.describe(texto="Texto a traducir", idioma="Idioma destino (ej: inglés, japonés)")
async def translate_text_cmd(interaction: discord.Interaction, texto: str, idioma: str = "inglés"):
    await interaction.response.defer()
    result = await _ask_groq(texto, system=f"Eres un traductor experto. Traduce exactamente al {idioma} sin añadir comentarios.")
    e = discord.Embed(title="〔 🌐 〕 Traducción", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="📝 Original",        value=f"```{texto[:500]}```",  inline=False)
    e.add_field(name=f"🌐 {idioma.title()}", value=f"```{result[:500]}```", inline=False)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e)

@bot.tree.command(name="summarize-text", description="📋 Resume un texto largo")
@app_commands.describe(texto="Texto a resumir")
async def summarize_text_cmd(interaction: discord.Interaction, texto: str):
    await interaction.response.defer()
    result = await _ask_groq(texto, system="Eres un experto en resúmenes. Resume en bullet points claros en español.")
    e = discord.Embed(title="〔 📋 〕 Resumen IA", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="📝 Resumen", value=result[:1900], inline=False)
    e.set_footer(text=_footer(f"Texto original: {len(texto)} chars"))
    await interaction.followup.send(embed=e)

@bot.tree.command(name="generate-image", description="🎨 Genera una imagen con IA")
@app_commands.describe(prompt="Descripción de la imagen")
async def generate_image_cmd(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    safe  = quote(prompt[:200])
    img_url = f"https://image.pollinations.ai/prompt/{safe}?width=512&height=512&nologo=true"
    e = discord.Embed(title="〔 🎨 〕 Imagen Generada", description=f"**Prompt:** {prompt[:300]}",
                      color=C_FUN, timestamp=discord.utils.utcnow())
    e.set_image(url=img_url)
    e.set_footer(text=_footer("Pollinations.ai"))
    v = View()
    v.add_item(Button(label="🔗 Abrir en navegador", url=img_url, style=discord.ButtonStyle.link))
    await interaction.followup.send(embed=e, view=v)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — CONFIGURACIÓN / BIENVENIDA / LOGS
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="welcome-setup", description="👋 [Admin] Configurar mensaje de bienvenida")
@app_commands.describe(canal="Canal de bienvenida", mensaje="Mensaje (usa {user} {server})")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_setup_cmd(interaction: discord.Interaction, canal: discord.TextChannel,
                             mensaje: str = "¡Bienvenido {user} a **{server}**! 🎉"):
    gk = str(interaction.guild_id)
    welcome_config.setdefault(gk,{}).update({"welcome_channel":canal.id,"welcome_message":mensaje,"welcome_enabled":True})
    save_json(WELCOME_CONFIG_FILE, welcome_config)
    e = discord.Embed(title="〔 👋 〕 Bienvenida Configurada", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.add_field(name="📌 Canal",   value=canal.mention,  inline=True)
    e.add_field(name="📝 Mensaje", value=mensaje[:200], inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@welcome_setup_cmd.error
async def welcome_setup_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="goodbye-setup", description="👋 [Admin] Configurar mensaje de despedida")
@app_commands.describe(canal="Canal de despedida", mensaje="Mensaje (usa {user} {server})")
@app_commands.checks.has_permissions(administrator=True)
async def goodbye_setup_cmd(interaction: discord.Interaction, canal: discord.TextChannel,
                             mensaje: str = "**{user}** ha abandonado **{server}** 👋"):
    gk = str(interaction.guild_id)
    welcome_config.setdefault(gk,{}).update({"goodbye_channel":canal.id,"goodbye_message":mensaje,"goodbye_enabled":True})
    save_json(WELCOME_CONFIG_FILE, welcome_config)
    e = discord.Embed(title="〔 👋 〕 Despedida Configurada", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.add_field(name="📌 Canal",   value=canal.mention,  inline=True)
    e.add_field(name="📝 Mensaje", value=mensaje[:200], inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@goodbye_setup_cmd.error
async def goodbye_setup_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="auto-role", description="🎭 [Admin] Rol automático al unirse")
@app_commands.describe(rol="Rol a asignar (no seleccionar para desactivar)")
@app_commands.checks.has_permissions(administrator=True)
async def auto_role_cmd(interaction: discord.Interaction, rol: discord.Role = None):
    gk = str(interaction.guild_id)
    welcome_config.setdefault(gk,{})["auto_role"] = rol.id if rol else None
    save_json(WELCOME_CONFIG_FILE, welcome_config)
    desc  = f"Auto-role configurado: {rol.mention}" if rol else "Auto-role **desactivado**."
    color = C_SUCCESS if rol else C_ERROR
    e = discord.Embed(title="〔 🎭 〕 Auto-Role", description=desc, color=color, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@auto_role_cmd.error
async def auto_role_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="verification-setup", description="✅ [Admin] Panel de verificación con botón")
@app_commands.describe(rol="Rol al verificarse", mensaje="Mensaje del panel")
@app_commands.checks.has_permissions(administrator=True)
async def verification_setup_cmd(interaction: discord.Interaction, rol: discord.Role,
                                  mensaje: str = "Haz clic en el botón para verificarte y acceder al servidor."):
    class VerifyView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
        @discord.ui.button(label="✅ Verificarme", style=discord.ButtonStyle.success, custom_id=f"verify:{rol.id}")
        async def verify(self, inter: discord.Interaction, btn: discord.ui.Button):
            target_role = inter.guild.get_role(rol.id)
            if target_role and target_role not in inter.user.roles:
                try:
                    await inter.user.add_roles(target_role, reason="Verificación KOD BOT")
                    await inter.response.send_message(f"✅ ¡Verificado! Rol {target_role.mention} asignado.", ephemeral=True)
                except Exception:
                    await inter.response.send_message("❌ No pude asignarte el rol.", ephemeral=True)
            else:
                await inter.response.send_message("Ya estás verificado.", ephemeral=True)
    e = discord.Embed(title="〔 ✅ 〕 Verificación — KOD BOT", description=mensaje, color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.channel.send(embed=e, view=VerifyView())
    await interaction.response.send_message("✅ Panel de verificación enviado.", ephemeral=True)

@verification_setup_cmd.error
async def verification_setup_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="reaction-roles", description="🎭 [Admin] Crear mensaje de reaction roles")
@app_commands.describe(rol1="Primer rol", emoji1="Emoji para rol 1", rol2="Segundo rol (opcional)", emoji2="Emoji para rol 2")
@app_commands.checks.has_permissions(administrator=True)
async def reaction_roles_cmd(interaction: discord.Interaction, rol1: discord.Role, emoji1: str,
                              rol2: discord.Role = None, emoji2: str = None):
    e = discord.Embed(title="〔 🎭 〕 Reaction Roles", description="Reacciona con el emoji del rol que quieres.", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name=f"{emoji1} {rol1.name}", value=rol1.mention, inline=True)
    if rol2 and emoji2:
        e.add_field(name=f"{emoji2} {rol2.name}", value=rol2.mention, inline=True)
    e.set_footer(text=_footer())
    msg = await interaction.channel.send(embed=e)
    await msg.add_reaction(emoji1)
    if rol2 and emoji2:
        await msg.add_reaction(emoji2)
    gk = str(interaction.guild_id)
    reaction_roles.setdefault(gk,{})[str(msg.id)] = {emoji1: rol1.id}
    if rol2 and emoji2:
        reaction_roles[gk][str(msg.id)][emoji2] = rol2.id
    await interaction.response.send_message("✅ Reaction roles creado.", ephemeral=True)

@reaction_roles_cmd.error
async def reaction_roles_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="logs-setup", description="📜 [Admin] Configurar canal de logs")
@app_commands.describe(canal="Canal de logs")
@app_commands.checks.has_permissions(administrator=True)
async def logs_setup_cmd(interaction: discord.Interaction, canal: discord.TextChannel):
    gk = str(interaction.guild_id)
    logs_config.setdefault(gk,{})["mod_log_channel"] = canal.id
    save_json(LOGS_CONFIG_FILE, logs_config)
    e = discord.Embed(title="〔 📜 〕 Logs Configurado", description=f"Canal de logs: {canal.mention}", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@logs_setup_cmd.error
async def logs_setup_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="moderation-logs", description="📜 [Admin] Activar/desactivar logs de moderación")
@app_commands.checks.has_permissions(administrator=True)
async def moderation_logs_cmd(interaction: discord.Interaction):
    gk = str(interaction.guild_id)
    logs_config.setdefault(gk,{})
    current = logs_config[gk].get("mod_logs_enabled", False)
    logs_config[gk]["mod_logs_enabled"] = not current
    save_json(LOGS_CONFIG_FILE, logs_config)
    status = "✅ Activados" if not current else "❌ Desactivados"
    e = discord.Embed(title=f"〔 📜 〕 Logs de Moderación {status}", color=C_SUCCESS if not current else C_ERROR, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@moderation_logs_cmd.error
async def moderation_logs_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="join-logs", description="📜 [Admin] Logs de entradas/salidas")
@app_commands.describe(canal="Canal para los logs")
@app_commands.checks.has_permissions(administrator=True)
async def join_logs_cmd(interaction: discord.Interaction, canal: discord.TextChannel):
    gk = str(interaction.guild_id)
    logs_config.setdefault(gk,{}).update({"join_log_channel":canal.id,"join_logs_enabled":True})
    save_json(LOGS_CONFIG_FILE, logs_config)
    e = discord.Embed(title="〔 📜 〕 Join Logs Configurado", description=f"Logs en {canal.mention}", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@join_logs_cmd.error
async def join_logs_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="message-logs", description="📜 [Admin] Logs de mensajes editados/borrados")
@app_commands.describe(canal="Canal para los logs")
@app_commands.checks.has_permissions(administrator=True)
async def message_logs_cmd(interaction: discord.Interaction, canal: discord.TextChannel):
    gk = str(interaction.guild_id)
    logs_config.setdefault(gk,{}).update({"message_log_channel":canal.id,"message_logs_enabled":True})
    save_json(LOGS_CONFIG_FILE, logs_config)
    e = discord.Embed(title="〔 📜 〕 Message Logs Configurado", description=f"Logs en {canal.mention}", color=C_SUCCESS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@message_logs_cmd.error
async def message_logs_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="server-setup", description="⚙️ [Admin] Ver el estado de configuración del bot")
@app_commands.checks.has_permissions(administrator=True)
async def server_setup_cmd(interaction: discord.Interaction):
    gk   = str(interaction.guild_id)
    wcfg = welcome_config.get(gk,{})
    lcfg = logs_config.get(gk,{})
    e = discord.Embed(title="〔 ⚙️ 〕 Configuración del Servidor",
                      description=(f"```yaml\n"
                                   f"Bienvenida : {'✅' if wcfg.get('welcome_channel') else '❌ No configurado'}\n"
                                   f"Despedida  : {'✅' if wcfg.get('goodbye_channel') else '❌ No configurado'}\n"
                                   f"Mod Logs   : {'✅' if lcfg.get('mod_log_channel') else '❌ No configurado'}\n"
                                   f"Join Logs  : {'✅' if lcfg.get('join_log_channel') else '❌ No configurado'}\n"
                                   f"IA Canales : {len(ia_channels)}\n"
                                   f"Auto-role  : {'✅' if wcfg.get('auto_role') else '❌ No configurado'}\n```"),
                      color=C_BYPASS, timestamp=discord.utils.utcnow())
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@server_setup_cmd.error
async def server_setup_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="server-settings", description="⚙️ [Admin] Configuraciones actuales del bot")
@app_commands.checks.has_permissions(administrator=True)
async def server_settings_cmd(interaction: discord.Interaction):
    gk   = str(interaction.guild_id)
    wcfg = welcome_config.get(gk,{})
    lcfg = logs_config.get(gk,{})
    e = discord.Embed(title="〔 ⚙️ 〕 Configuración Actual", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="👋 Bienvenida",  value=f"<#{wcfg['welcome_channel']}>" if wcfg.get("welcome_channel") else "❌ No config", inline=True)
    e.add_field(name="👋 Despedida",   value=f"<#{wcfg['goodbye_channel']}>" if wcfg.get("goodbye_channel") else "❌ No config", inline=True)
    e.add_field(name="📜 Mod Logs",    value=f"<#{lcfg['mod_log_channel']}>" if lcfg.get("mod_log_channel") else "❌ No config", inline=True)
    e.add_field(name="🤖 IA Canales",  value=f"`{len(ia_channels)}` activo(s)",                                                   inline=True)
    e.add_field(name="🎭 Auto-Role",   value=f"<@&{wcfg['auto_role']}>"  if wcfg.get("auto_role") else "❌ No config",           inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@server_settings_cmd.error
async def server_settings_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

@bot.tree.command(name="permissions-setup", description="🔐 [Admin] Ver permisos del bot en este servidor")
@app_commands.checks.has_permissions(administrator=True)
async def permissions_setup_cmd(interaction: discord.Interaction):
    me    = interaction.guild.me
    perms = me.guild_permissions
    def chk(p): return "✅" if p else "❌"
    e = discord.Embed(title="〔 🔐 〕 Permisos del Bot", color=C_INFO, timestamp=discord.utils.utcnow())
    e.add_field(name="🛡️ Moderación",
                value=f"{chk(perms.ban_members)} Banear\n{chk(perms.kick_members)} Expulsar\n{chk(perms.moderate_members)} Timeout\n{chk(perms.manage_messages)} Gestionar Mensajes",
                inline=True)
    e.add_field(name="📌 Canales",
                value=f"{chk(perms.manage_channels)} Gestionar Canales\n{chk(perms.manage_roles)} Gestionar Roles\n{chk(perms.read_message_history)} Historial\n{chk(perms.add_reactions)} Reacciones",
                inline=True)
    e.add_field(name="👥 Generales",
                value=f"{chk(perms.manage_nicknames)} Apodos\n{chk(perms.view_audit_log)} Auditoría\n{chk(perms.send_messages)} Enviar Mensajes\n{chk(perms.embed_links)} Embeds",
                inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@permissions_setup_cmd.error
async def permissions_setup_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso **Administrador**.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — GIVEAWAYS / POLLS
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="start-giveaway", description="🎉 Iniciar un sorteo")
@app_commands.describe(minutos="Duración en minutos", premio="Premio", ganadores="Número de ganadores")
@app_commands.checks.has_permissions(manage_guild=True)
async def start_giveaway_cmd(interaction: discord.Interaction, minutos: int, premio: str, ganadores: int = 1):
    await interaction.response.defer()
    end_time = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    e = discord.Embed(title="〔 🎉 〕 GIVEAWAY",
                      description=(f"**Premio:** {premio}\n```yaml\n"
                                   f"🎟️  Reacciona con 🎉 para participar\n"
                                   f"🏆  Ganadores  : {ganadores}\n"
                                   f"⏱️  Termina    : <t:{int(end_time.timestamp())}:R>\n"
                                   f"👤  Host       : {interaction.user.name}\n```"),
                      color=C_FUN, timestamp=end_time)
    e.set_footer(text=_footer("🎉 Reacciona para participar"))
    msg = await interaction.followup.send(embed=e)
    await msg.add_reaction("🎉")
    giveaways[str(msg.id)] = {"prize":premio,"winners":ganadores,"end":end_time.isoformat(),"host":str(interaction.user),"channel":interaction.channel_id}
    save_json(GIVEAWAYS_FILE, giveaways)
    task = asyncio.create_task(_giveaway_countdown(interaction.channel, msg.id, premio, ganadores, end_time, str(interaction.user)))
    _active_giveaways[str(msg.id)] = task

@start_giveaway_cmd.error
async def start_giveaway_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Servidor**.", ephemeral=True)

@bot.tree.command(name="create-poll", description="📊 Crear una encuesta con reacciones")
@app_commands.describe(pregunta="Pregunta", opcion1="Opción 1", opcion2="Opción 2", opcion3="Opción 3 (opcional)", opcion4="Opción 4 (opcional)")
async def create_poll_cmd(interaction: discord.Interaction, pregunta: str, opcion1: str, opcion2: str,
                           opcion3: str = None, opcion4: str = None):
    emojis  = ["1️⃣","2️⃣","3️⃣","4️⃣"]
    opciones = [o for o in [opcion1,opcion2,opcion3,opcion4] if o]
    desc     = "\n".join(f"{emojis[i]} {op}" for i,op in enumerate(opciones))
    e = discord.Embed(title=f"〔 📊 〕 {pregunta}", description=desc, color=C_INFO, timestamp=discord.utils.utcnow())
    e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    e.set_footer(text=_footer(f"Encuesta de {interaction.user.name}"))
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    for i in range(len(opciones)):
        await msg.add_reaction(emojis[i])

@bot.tree.command(name="report-user", description="🚨 Reportar a un usuario al staff")
@app_commands.describe(usuario="Usuario a reportar", razon="Razón del reporte")
async def report_user_cmd(interaction: discord.Interaction, usuario: discord.Member, razon: str):
    gk = str(interaction.guild_id)
    report_ch_id = logs_config.get(gk,{}).get("mod_log_channel")
    e = discord.Embed(title="〔 🚨 〕 Nuevo Reporte", color=C_ERROR, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Reportado", value=f"{usuario.mention} (`{usuario.id}`)", inline=True)
    e.add_field(name="📢 Reporter",  value=interaction.user.mention,              inline=True)
    e.add_field(name="📋 Razón",     value=razon,                                 inline=False)
    e.add_field(name="📌 Canal",     value=interaction.channel.mention,            inline=True)
    e.set_thumbnail(url=usuario.display_avatar.url)
    e.set_footer(text=_footer())
    if report_ch_id:
        ch = interaction.guild.get_channel(report_ch_id)
        if ch:
            await ch.send(embed=e)
    await interaction.response.send_message("✅ Reporte enviado al staff.", ephemeral=True)

@bot.tree.command(name="create-embed", description="✨ [Mod] Crear y enviar un embed personalizado")
@app_commands.describe(titulo="Título", descripcion="Descripción", color="Color hex (ej: #5865F2)", canal="Canal destino")
@app_commands.checks.has_permissions(manage_messages=True)
async def create_embed_cmd(interaction: discord.Interaction, titulo: str, descripcion: str,
                            color: str = "#5865F2", canal: discord.TextChannel = None):
    try:
        color_int = int(color.strip("#"), 16)
    except ValueError:
        color_int = C_INFO
    e = discord.Embed(title=titulo, description=descripcion, color=color_int, timestamp=discord.utils.utcnow())
    e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    e.set_footer(text=_footer())
    dest = canal or interaction.channel
    await dest.send(embed=e)
    await interaction.response.send_message(f"✅ Embed enviado a {dest.mention}.", ephemeral=True)

@create_embed_cmd.error
async def create_embed_error(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Gestionar Mensajes**.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  WEB SERVER (Render Web Service — PORT binding)
# ══════════════════════════════════════════════════════════════════

async def health_handler(_request):
    return aiohttp.web.Response(text='{"status":"ok","bot":"KOD BOT"}',
                                content_type="application/json", status=200)

async def start_web_server():
    app = aiohttp.web.Application()
    app.router.add_get("/",       health_handler)
    app.router.add_get("/health", health_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Health server activo en puerto {PORT}")

# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ Falta la variable de entorno DISCORD_TOKEN.")
        return
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
