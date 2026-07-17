import os
import re
import json
import time
import random
import asyncio
import logging
import threading
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from logging.handlers import RotatingFileHandler
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote, unquote

import discord
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
import requests
import aiohttp
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# LOGGING
LOG_FILE = "bot_logs.txt"
logger = logging.getLogger("BotLogger")
logger.setLevel(logging.INFO)
_file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# ==================== CONFIG ====================
TOKEN = os.environ.get("DISCORD_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or "0")
PORT = int(os.environ.get("PORT", "10000"))
BOT_NAME = "KING BOT"
BOT_CREDIT = "KING"
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525040833814855710")

# ==================== OPENROUTER CONFIG ====================
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")

# ==================== GIF / FUN API KEYS ====================
GIPHY_API_KEY = "dc6zaTOxFJmzC"

# ==================== BYPASS ENGINE ====================
BYPASS_API_ENDPOINT = "https://4pi-bypass.vercel.app/api/bypass?url="
AUTOBYPASS_FILE = "autobypass_channels.json"

def bypass_url_vps(url: str) -> tuple:
    try:
        resp = requests.get(BYPASS_API_ENDPOINT + quote(url, safe=""), timeout=30)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        data = resp.json()
        if data.get("success") is False:
            return None, data.get("error", "API error")
        result = data.get("result") or data.get("url") or data.get("bypassed_url")
        return result, None
    except Exception as e:
        return None, str(e)

# ==================== JSON HELPERS ====================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not save {path}: {e}")

# ==================== STORAGE FILES ====================
TICKETS_FILE = "tickets.json"
GIVEAWAYS_FILE = "giveaways.json"
ECONOMY_FILE = "economy.json"
LEVELS_FILE = "levels.json"
IA_CONFIG_FILE = "ia_config.json"
SERVER_CONFIG_FILE = "server_config.json"
WARNINGS_FILE = "warnings.json"
EXECUTOR_CONFIG_FILE = "executor_config.json"
EXECUTOR_CACHE_FILE = "executor_cache.json"

# ==================== INIT DATA ====================
autobypass_channels = set(load_json(AUTOBYPASS_FILE, []))
ia_config = load_json(IA_CONFIG_FILE, {})
server_config = load_json(SERVER_CONFIG_FILE, {})
tickets = load_json(TICKETS_FILE, {})
giveaways = load_json(GIVEAWAYS_FILE, {})
economy = load_json(ECONOMY_FILE, {})
levels = load_json(LEVELS_FILE, {})
warnings = load_json(WARNINGS_FILE, {})
executor_config = load_json(EXECUTOR_CONFIG_FILE, {})
executor_cache = load_json(EXECUTOR_CACHE_FILE, {})

def save_autobypass(): save_json(AUTOBYPASS_FILE, list(autobypass_channels))
def save_ia_config(): save_json(IA_CONFIG_FILE, ia_config)
def save_server_config(): save_json(SERVER_CONFIG_FILE, server_config)
def save_tickets(): save_json(TICKETS_FILE, tickets)
def save_giveaways(): save_json(GIVEAWAYS_FILE, giveaways)
def save_economy(): save_json(ECONOMY_FILE, economy)
def save_levels(): save_json(LEVELS_FILE, levels)
def save_warnings(): save_json(WARNINGS_FILE, warnings)
def save_executor_config(): save_json(EXECUTOR_CONFIG_FILE, executor_config)
def save_executor_cache(): save_json(EXECUTOR_CACHE_FILE, executor_cache)

# ==================== CUSTOM EMOJIS (ALL 81 PROVIDED) ====================
# Map all names to their IDs; if an ID is missing, fallback to Unicode.
# We define a helper to get emoji string; if ID is None, use Unicode fallback.

# First, list all IDs from the user's extraction.
EMOJI_IDS = {
    "add_symbol": 1527235736116527179,
    "Admin": 1526850858271248384,
    "Alarm": 1525787989354086411,
    "AnnouncementPingRoleIcon": 1526855584807256124,
    "Attention": 1526850359958704138,
    "Awesomeface14": 1526850663575982222,
    "BitCash": 1526850558726508564,
    "CameraRedLogo": 1526854158680981504,
    "Cart": 1526854833125195786,
    "Clipboard": 1527231830430842891,
    "clock": 1525380296852377711,
    "clown": 1526858087510835252,
    "clown2": 1526858673404510268,
    "copy_text": 1526743644894138479,
    "CopyPaste": 1525379105111932958,
    "Cursor_click": 1526857184116477962,
    "DarkBlueArrow": 1526850610547396690,
    "Database": 1527233297623679028,
    "Developer": 1527232205171068992,
    "Diamond": 1526858613572894780,
    "DiamondHand": 1527233825237745826,
    "Discount": 1527231806774847581,
    "DoubleRightArrow": 1527232622690033715,
    "Error": 1526854353619656805,
    "Error2": 1526855155797061754,
    "Folder": 1526854262280036372,
    "GreenArrow": 1526857606084268095,
    "GreenCheckmark": 1526855067586789386,
    "GreenTick": 1527233240899913748,
    "GreyArrow": 1527233584492933130,
    "grey_line": 1526859535623520276,
    "GreyQuestion": 1526859684391159808,
    "GreyQuestionMark": 1526857379436642394,
    "Heart": 1526856039885164554,
    "Image": 1526858395913934858,
    "Info": 1526855284914653205,
    "Join": 1527232869524662392,
    "LeftArrow": 1527235653216976906,
    "Link": 1527233749370886296,
    "Loading": 1526850199107266693,
    "lock": 1527235546362871838,
    "Mail": 1527235926974842930,
    "Members": 1527233062529878076,
    "Message": 1526859153673803786,
    "Moderator": 1527232335102081116,
    "Money": 1526857281906767944,
    "New": 1527233969806737458,
    "No": 1526854412717391955,
    "Nitro": 1526853872159705138,
    "Notification": 1526857834816436264,
    "Online": 1526854662970259556,
    "Owner": 1527232114523496540,
    "Partner": 1527232427577694329,
    "Pin": 1527231758586486846,
    "PinkArrow": 1526857848309250108,
    "Plus": 1526858484363405412,
    "Question": 1526854903945717761,
    "RedArrow": 1526856897289089064,
    "Reload": 1527232027449747547,
    "RightArrow": 1526856208559091772,
    "Robot": 1527233491450552391,
    "Rules": 1527235781577799740,
    "Search": 1527232943235352687,
    "Settings": 1526854350797013013,
    "Shield": 1527235705413294160,
    "Star": 1527231986333118464,
    "Support": 1527232769209557042,
    "Ticket": 1527232981135212545,
    "Time": 1527233417597370409,
    "Trash": 1527231903986342020,
    "Unlock": 1527235509477892206,
    "User": 1527232382631260190,
    "Verified": 1526857077157484606,
    "Warning": 1527233342573850744,
    "Welcome": 1526859860837029919,
    "WhiteArrow": 1526856107421829120,
    "WhiteTick": 1526854546389868677,
    "Wrench": 1527231882477826168,
    "x": 1526854695354466445,
    "YellowArrow": 1526857769141893130,
    "YellowQuestion": 1526857155486025760,
}

def emoji(name, fallback=""):
    """Return custom emoji string if ID exists, else fallback Unicode."""
    id_ = EMOJI_IDS.get(name)
    if id_ is None:
        return fallback
    # Determine if animated (usually based on name, but we can just try both formats)
    # For simplicity, we'll assume all are static unless name contains "Loading" etc.
    # We'll check known animated ones.
    animated_names = ["Loading", "Alarm", "Attention", "Awesomeface14", "BitCash", "CameraRedLogo", 
                      "Cursor_click", "DarkBlueArrow", "Diamond", "DiamondHand", "Giveaway", "Gift",
                      "GreenArrow", "GreenCheckmark", "GreenTick", "GreyArrow", "GreyQuestion", "GreyQuestionMark",
                      "Heart", "Image", "Info", "Join", "LeftArrow", "Link", "Loading", "lock", "Mail", "Members",
                      "Message", "Moderator", "Money", "New", "No", "Nitro", "Notification", "Online", "Owner",
                      "Partner", "Pin", "PinkArrow", "Plus", "Question", "RedArrow", "Reload", "RightArrow",
                      "Robot", "Rules", "Search", "Settings", "Shield", "Star", "Support", "Ticket", "Time",
                      "Trash", "Unlock", "User", "Verified", "Warning", "Welcome", "WhiteArrow", "WhiteTick",
                      "Wrench", "x", "YellowArrow", "YellowQuestion"]
    # Also clock, copy_text, etc. are static.
    if name in animated_names:
        return f"<a:{name}:{id_}>"
    else:
        return f"<:{name}:{id_}>"

# Now define all EMOJI_* constants we need.
# We'll use the emoji() helper. If not defined, fallback to Unicode.

EMOJI_ADD = emoji("add_symbol", "➕")
EMOJI_ADMIN = emoji("Admin", "🛡️")
EMOJI_ALARM = emoji("Alarm", "⏰")
EMOJI_ATTENTION = emoji("Attention", "⚠️")
EMOJI_BITCASH = emoji("BitCash", "💵")
EMOJI_CAMERA_RED = emoji("CameraRedLogo", "📷")
EMOJI_CART = emoji("Cart", "🛒")
EMOJI_CLIPBOARD = emoji("Clipboard", "📋")
EMOJI_CLOCK = emoji("clock", "🕒")
EMOJI_CLOWN = emoji("clown", "🤡")
EMOJI_COPY = emoji("copy_text", "📋")
EMOJI_COPYPASTE = emoji("CopyPaste", "📄")
EMOJI_CURSOR = emoji("Cursor_click", "🖱️")
EMOJI_DARK_BLUE_ARROW = emoji("DarkBlueArrow", "➡️")
EMOJI_DATABASE = emoji("Database", "🗄️")
EMOJI_DEVELOPER = emoji("Developer", "👨‍💻")
EMOJI_DIAMOND = emoji("Diamond", "💎")
EMOJI_DOWNLOAD = emoji("Download", "⬇️")  # fallback
EMOJI_ERROR = emoji("Error", "❌")
EMOJI_FOLDER = emoji("Folder", "📁")
EMOJI_GIFT = emoji("Gift", "🎁")
EMOJI_GIVEAWAY = emoji("Giveaway", "🎉")
EMOJI_GREEN_ARROW = emoji("GreenArrow", "➡️")
EMOJI_GREEN_CHECK = emoji("GreenCheckmark", "✅")
EMOJI_GREEN_DOT = emoji("GreenDot", "🟢")  # but we need animated; we'll use the static one? Actually we have GreenDot ID.
EMOJI_GREEN_CROWN = emoji("GreenCrown", "👑")  # we have GreenCrown? Actually we have Crown? The list has "GreenCrown"? Not in list. We'll use Crown.
# We'll define many more as needed.

# From the user's requests, they use EMOJI_GREEN_DOT, EMOJI_LOADER, EMOJI_CROWN, EMOJI_KEY, EMOJI_CLOCK, EMOJI_SUCCESS, EMOJI_COPY, etc.
# We'll map those to the ones we have.
EMOJI_GREEN_DOT = emoji("GreenDot", "🟢")  # Actually we have GreenDot? The list has "GreenDot"? Not in the list. We'll use a fallback.
EMOJI_LOADER = emoji("Loading", "⏳")  # We have Loading.
EMOJI_CROWN = emoji("Crown", "👑")  # Not in list; we'll use GreenCrown? Actually we have "GreenCrown"? Not listed. We'll use a Unicode crown.
EMOJI_KEY = emoji("Key", "🔑")  # Not in list; use Unicode.
EMOJI_SUCCESS = emoji("Success", "✅")  # Not in list; use Unicode.
EMOJI_FAILED = emoji("Error", "❌")
EMOJI_WARNING = emoji("Warning", "⚠️")
EMOJI_LIGHTNING_GREEN = emoji("LightningGreen", "⚡")  # Not in list; use Unicode.
EMOJI_LOCK = emoji("lock", "🔒")
EMOJI_UNLOCK = emoji("Unlock", "🔓")
EMOJI_EDIT = emoji("Edit", "✏️")  # Not in list; use Unicode.
EMOJI_DELETE = emoji("Trash", "🗑️")
EMOJI_TICKET = emoji("Ticket", "🎫")
EMOJI_INFORMATION = emoji("Info", "ℹ️")
EMOJI_INVITE = emoji("Invite", "📩")  # Not in list; use Unicode.
EMOJI_DISCORD = emoji("Discord", "💬")  # Not in list; use Unicode.
EMOJI_LINK = emoji("Link", "🔗")
EMOJI_PC = emoji("PC", "🖥️")  # Not in list; use Unicode.
EMOJI_PHONE = emoji("Phone", "📱")
EMOJI_HOUSE = emoji("House", "🏠")  # Not in list; use Unicode.
EMOJI_SEARCH = emoji("Search", "🔍")
EMOJI_SETTINGS = emoji("Settings", "⚙️")
EMOJI_POINT = emoji("Point", "📍")  # Not in list; use Unicode.
EMOJI_ARROW = emoji("RightArrow", "➡️")
EMOJI_ROLE = emoji("Role", "🎭")  # Not in list; use Unicode.
EMOJI_MONEY = emoji("Money", "💰")
EMOJI_BITCASH = emoji("BitCash", "💵")
EMOJI_CART = emoji("Cart", "🛒")
EMOJI_ROCKET = emoji("Rocket", "🚀")  # Not in list; use Unicode.
EMOJI_HOME = emoji("Home", "🏠")  # Not in list; use Unicode.
EMOJI_AVISO = emoji("Aviso", "⚠️")  # Not in list; use Unicode.

# We'll also need EMOJI_DOCUMENT, EMOJI_GIVEAWAY, EMOJI_DOWNLOAD, EMOJI_PC, etc.
EMOJI_DOCUMENT = emoji("Document", "📄")  # Not in list; use Unicode.
EMOJI_GIVEAWAY = emoji("Giveaway", "🎉")
EMOJI_DOWNLOAD = emoji("Download", "⬇️")
EMOJI_PC = emoji("PC", "🖥️")
EMOJI_PHONE = emoji("Phone", "📱")
EMOJI_ROCKET = emoji("Rocket", "🚀")
EMOJI_HOME = emoji("Home", "🏠")
EMOJI_EDIT = emoji("Edit", "✏️")
EMOJI_DELETE = emoji("Trash", "🗑️")
EMOJI_LOCK = emoji("lock", "🔒")
EMOJI_UNLOCK = emoji("Unlock", "🔓")
EMOJI_WARNING = emoji("Warning", "⚠️")
EMOJI_SUCCESS = emoji("Success", "✅")
EMOJI_FAILED = emoji("Error", "❌")
EMOJI_ADD = emoji("add_symbol", "➕")
EMOJI_ADMIN = emoji("Admin", "🛡️")
EMOJI_ALARM = emoji("Alarm", "⏰")
EMOJI_ATTENTION = emoji("Attention", "⚠️")
EMOJI_BITCASH = emoji("BitCash", "💵")
EMOJI_CAMERA_RED = emoji("CameraRedLogo", "📷")
EMOJI_CART = emoji("Cart", "🛒")
EMOJI_CLIPBOARD = emoji("Clipboard", "📋")
EMOJI_CLOCK = emoji("clock", "🕒")
EMOJI_CLOWN = emoji("clown", "🤡")
EMOJI_COPY = emoji("copy_text", "📋")
EMOJI_COPYPASTE = emoji("CopyPaste", "📄")
EMOJI_CURSOR = emoji("Cursor_click", "🖱️")
EMOJI_DARK_BLUE_ARROW = emoji("DarkBlueArrow", "➡️")
EMOJI_DATABASE = emoji("Database", "🗄️")
EMOJI_DEVELOPER = emoji("Developer", "👨‍💻")
EMOJI_DIAMOND = emoji("Diamond", "💎")
EMOJI_DOWNLOAD = emoji("Download", "⬇️")
EMOJI_ERROR = emoji("Error", "❌")
EMOJI_FOLDER = emoji("Folder", "📁")
EMOJI_GIFT = emoji("Gift", "🎁")
EMOJI_GIVEAWAY = emoji("Giveaway", "🎉")
EMOJI_GREEN_ARROW = emoji("GreenArrow", "➡️")
EMOJI_GREEN_CHECK = emoji("GreenCheckmark", "✅")
EMOJI_GREEN_DOT = emoji("GreenDot", "🟢")  # fallback
EMOJI_GREEN_CROWN = emoji("GreenCrown", "👑")  # fallback
EMOJI_KEY = emoji("Key", "🔑")  # fallback
EMOJI_LOADER = emoji("Loading", "⏳")  # fallback
EMOJI_SUCCESS = emoji("Success", "✅")  # fallback
EMOJI_FAILED = emoji("Error", "❌")
EMOJI_WARNING = emoji("Warning", "⚠️")
EMOJI_LIGHTNING_GREEN = emoji("LightningGreen", "⚡")  # fallback
EMOJI_LOCK = emoji("lock", "🔒")
EMOJI_UNLOCK = emoji("Unlock", "🔓")
EMOJI_EDIT = emoji("Edit", "✏️")  # fallback
EMOJI_DELETE = emoji("Trash", "🗑️")
EMOJI_TICKET = emoji("Ticket", "🎫")
EMOJI_INFORMATION = emoji("Info", "ℹ️")
EMOJI_INVITE = emoji("Invite", "📩")  # fallback
EMOJI_DISCORD = emoji("Discord", "💬")  # fallback
EMOJI_LINK = emoji("Link", "🔗")
EMOJI_PC = emoji("PC", "🖥️")  # fallback
EMOJI_PHONE = emoji("Phone", "📱")
EMOJI_HOUSE = emoji("House", "🏠")  # fallback
EMOJI_SEARCH = emoji("Search", "🔍")
EMOJI_SETTINGS = emoji("Settings", "⚙️")
EMOJI_POINT = emoji("Point", "📍")  # fallback
EMOJI_ARROW = emoji("RightArrow", "➡️")
EMOJI_ROLE = emoji("Role", "🎭")  # fallback
EMOJI_MONEY = emoji("Money", "💰")
EMOJI_BITCASH = emoji("BitCash", "💵")
EMOJI_CART = emoji("Cart", "🛒")
EMOJI_ROCKET = emoji("Rocket", "🚀")  # fallback
EMOJI_HOME = emoji("Home", "🏠")  # fallback
EMOJI_AVISO = emoji("Aviso", "⚠️")  # fallback

# ==================== COLORS ====================
C_SUCCESS = 0x57F287
C_ERROR = 0xED4245
C_WARN = 0xFEE75C
C_MOD = 0xEB459E
C_FUN = 0xFF7043
C_INFO = 0x5865F2
C_AUTO = 0x9B59B6
C_GREEN = 0x57F287
C_GOLD = 0xFACC15
C_BLUE = 0x3B82F6
C_RED = 0xEF4444
C_ORANGE = 0xF59E0B
C_PURPLE = 0x8B5CF6
C_DARK_BLUE = 0x2563EB
C_TICKET = 0x3B82F6

# ==================== HELPERS ====================
def _footer(extra: str = "") -> str:
    base = f"👑 CREATED BY {BOT_CREDIT}"
    return f"{base} • {extra}" if extra else base

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def format_uptime(start_time: datetime) -> str:
    delta = datetime.now(timezone.utc) - start_time
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def xp_needed(level: int) -> int:
    return 5 * (level + 1) ** 2

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

# ==================== HEALTH SERVER (Render) ====================
class _HealthHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def do_GET(self):
        self._send_health_response()
    def do_HEAD(self):
        self._send_health_response()
    def _send_health_response(self):
        body = b'{"status":"ok","bot":"KING BOT"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
    def log_message(self, format, *args):
        pass

def _start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    logger.info(f"Health server running on port {PORT}")
    server.serve_forever()

# ==================== BOT CLIENT ====================
class BotClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.BOT_START_TIME = datetime.now(timezone.utc)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commands synced successfully!")
        self.loop.create_task(self._giveaway_loop())
        self.loop.create_task(self._executor_update_loop())

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} ({self.user.id})")
        logger.info(f"Serving {len(self.guilds)} servers")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # AUTO-BYPASS: Delete ANY message in the channel, then process links if present
        if message.channel.id in autobypass_channels:
            try:
                await message.delete()
            except:
                pass
            urls = _URL_PATTERN.findall(message.content)
            if urls:
                await self._auto_bypass(message, urls)
            return

        # IA auto-reply
        if str(message.channel.id) in ia_config.get("channels", []):
            await self._handle_ia_message(message)

        # XP / Level system
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        levels.setdefault(guild_id, {}).setdefault(user_id, {"xp": 0, "level": 0})
        entry = levels[guild_id][user_id]
        entry["xp"] += random.randint(5, 15)
        if entry["xp"] >= xp_needed(entry["level"]):
            entry["level"] += 1
            entry["xp"] = 0
            try:
                msg = await message.channel.send(f"{EMOJI_ROCKET} {message.author.mention} leveled up to **Level {entry['level']}**!")
                # Auto-delete level-up message after 5 seconds
                asyncio.create_task(self._delete_after(msg, 5))
            except:
                pass
            save_levels()

    async def _delete_after(self, msg: discord.Message, delay: int):
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except:
            pass

    async def _auto_bypass(self, message: discord.Message, urls: list):
        """Process the first URL, send bypass result, and delete it after 120 seconds."""
        for url in urls[:1]:  # only first link to avoid spam
            if not _is_valid_url(url):
                continue
            start = time.time()
            result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_vps, url)
            elapsed = time.time() - start
            if result:
                embed = discord.Embed(color=C_GREEN)
                embed.title = f"{EMOJI_GREEN_DOT} BYPASS SUCCESS"
                embed.add_field(
                    name=f"{EMOJI_KEY} Result",
                    value=f"```txt\n{result[:1000]}\n```",
                    inline=False
                )
                embed.add_field(
                    name=f"{EMOJI_CLOCK} Time",
                    value=f"`{elapsed:.2f}s`",
                    inline=True
                )
                embed.add_field(
                    name=f"{EMOJI_SUCCESS} Status",
                    value="`Completed`",
                    inline=True
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")  # GreenCrown
                embed.set_footer(text=_footer())
                view = View()
                view.add_item(Button(
                    label="📋 Copy",
                    style=discord.ButtonStyle.secondary,
                    custom_id="bypass_copy"
                ))
                msg = await message.channel.send(
                    content=message.author.mention,
                    embed=embed,
                    view=view
                )
                # Auto-delete after 120 seconds
                asyncio.create_task(self._delete_after(msg, 120))
            else:
                embed = discord.Embed(
                    title=f"{EMOJI_FAILED} BYPASS FAILED",
                    description=f"```{error or 'Unknown error'}```",
                    color=C_ERROR
                )
                embed.set_footer(text=_footer())
                await message.channel.send(content=message.author.mention, embed=embed)

    async def _handle_ia_message(self, message: discord.Message):
        if not OPENROUTER_API_KEY:
            return
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": OPENROUTER_MODEL, "messages": [{"role": "user", "content": message.content}], "max_tokens": 500}
                async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"]
                        embed = discord.Embed(description=reply, color=C_INFO)
                        embed.set_author(name="🤖 AI Assistant")
                        await message.reply(embed=embed)
                    else:
                        await message.reply("⚠️ AI service error.")
        except Exception as e:
            logger.error(f"IA error: {e}")

    async def _giveaway_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            now = time.time()
            to_end = []
            for gid, g in giveaways.items():
                if not g.get("ended") and not g.get("paused") and g["end_time"] <= now:
                    to_end.append(gid)
            for gid in to_end:
                await self._end_giveaway(gid)
            await asyncio.sleep(5)

    async def _end_giveaway(self, gid: str):
        g = giveaways.get(gid)
        if not g or g.get("ended"):
            return
        g["ended"] = True
        participants = g.get("participants", [])
        channel = self.get_channel(g["channel"])
        if not channel:
            save_giveaways()
            return
        try:
            msg = await channel.fetch_message(int(gid))
            if not participants:
                embed = discord.Embed(title="🎊 Giveaway Ended", description="No valid participants.", color=C_ERROR)
                await msg.edit(embed=embed, view=None)
            else:
                winners = random.sample(participants, min(g["winners"], len(participants)))
                mentions = " ".join([f"<@{w}>" for w in winners])
                embed = discord.Embed(title="🎊 Giveaway Ended", color=C_GOLD)
                embed.description = f"**Prize:** {g['prize']}\n🏆 **Winner(s):** {mentions}"
                await msg.edit(embed=embed, view=None)
                await channel.send(f"🎉 Congratulations {mentions}! You won **{g['prize']}**!")
        except:
            pass
        save_giveaways()

    async def _executor_update_loop(self):
        await self.wait_until_ready()
        logger.info("Executor update loop started.")
        while not self.is_closed():
            try:
                config = load_json(EXECUTOR_CONFIG_FILE, {})
                channel_id = config.get("channel_id")
                role_id = config.get("role_id")
                if channel_id:
                    channel = self.get_channel(channel_id)
                    if channel:
                        await self._check_executor_updates(channel, role_id)
            except Exception as e:
                logger.error(f"Executor update error: {e}")
            await asyncio.sleep(60)

    async def _check_executor_updates(self, channel: discord.TextChannel, role_id: int = None):
        url = "https://weao-proxy-api.vercel.app/api/status/exploits"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        return
                    current_data = await resp.json()
        except:
            return
        if not isinstance(current_data, list):
            return
        cache = load_json(EXECUTOR_CACHE_FILE, {})
        updated = []
        for exploit in current_data:
            name = exploit.get("title") or exploit.get("name")
            if not name:
                continue
            version = exploit.get("version", "N/A")
            if name in cache:
                old = cache[name].get("version")
                if old != version and version != "N/A":
                    updated.append(exploit)
            else:
                updated.append(exploit)
            cache[name] = {"version": version}
        save_json(EXECUTOR_CACHE_FILE, cache)
        if updated:
            mention = f"<@&{role_id}>" if role_id else "@everyone"
            for exploit in updated:
                name = exploit.get("title") or exploit.get("name", "Unknown")
                version = exploit.get("version", "N/A")
                status = exploit.get("status", "Unknown")
                download_url = exploit.get("download_url") or exploit.get("purchaselink")
                embed = discord.Embed(
                    title=f"🔄 {name} has updated!",
                    description=f"**Status:** {status}",
                    color=C_GREEN,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="New Version", value=version, inline=True)
                embed.set_footer(text="WEAO API • Auto-update")
                view = View()
                if download_url and download_url != "#":
                    view.add_item(Button(label="Download", url=download_url))
                else:
                    view.add_item(Button(label="Website", url="https://weao.xyz"))
                await channel.send(content=mention, embed=embed, view=view)
                await asyncio.sleep(1)

bot = BotClient()
tree = bot.tree

# ==================== ERROR HANDLER ====================
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = f"{EMOJI_WARNING} An unexpected error occurred."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except:
        pass

# ==================== BYPASS COMMANDS ====================
@tree.command(name="bypass", description="Bypass a link manually")
async def bypass_cmd(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        return await interaction.response.send_message(f"{EMOJI_WARNING} Invalid URL.", ephemeral=True)
    await interaction.response.defer()
    start = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_vps, url)
    elapsed = time.time() - start
    if result:
        embed = discord.Embed(color=C_GREEN)
        embed.title = f"{EMOJI_GREEN_DOT} BYPASS SUCCESS"
        embed.add_field(
            name=f"{EMOJI_KEY} Result",
            value=f"```txt\n{result[:1000]}\n```",
            inline=False
        )
        embed.add_field(
            name=f"{EMOJI_CLOCK} Time",
            value=f"`{elapsed:.2f}s`",
            inline=True
        )
        embed.add_field(
            name=f"{EMOJI_SUCCESS} Status",
            value="`Completed`",
            inline=True
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")  # GreenCrown
        embed.set_footer(text=_footer())
        view = View()
        view.add_item(Button(label="📋 Copy", style=discord.ButtonStyle.secondary, custom_id="bypass_copy"))
        await interaction.followup.send(embed=embed, view=view)
    else:
        embed = discord.Embed(
            title=f"{EMOJI_FAILED} BYPASS FAILED",
            description=f"```{error or 'Unknown error'}```",
            color=C_ERROR
        )
        embed.set_footer(text=_footer())
        await interaction.followup.send(embed=embed)

@tree.command(name="setautobypass", description="[Admin] Toggle auto-bypass in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setautobypass_cmd(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        save_autobypass()
        embed = discord.Embed(
            title=f"{EMOJI_WARNING} Auto-Bypass Disabled",
            color=C_ERROR
        )
    else:
        autobypass_channels.add(cid)
        save_autobypass()
        embed = discord.Embed(
            title=f"{EMOJI_LIGHTNING_GREEN} Auto-Bypass Enabled",
            color=C_SUCCESS
        )
        embed.description = f"Every message in {interaction.channel.mention} will be deleted; links will be bypassed automatically."
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== IA COMMANDS ====================
@tree.command(name="setupia", description="[Admin] Toggle AI auto-reply in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setupia_cmd(interaction: discord.Interaction):
    cid = str(interaction.channel_id)
    channels = ia_config.get("channels", [])
    if cid in channels:
        channels.remove(cid)
        ia_config["channels"] = channels
        save_ia_config()
        embed = discord.Embed(
            title=f"{EMOJI_WARNING} AI Disabled",
            color=C_ERROR
        )
    else:
        channels.append(cid)
        ia_config["channels"] = channels
        save_ia_config()
        embed = discord.Embed(
            title=f"{EMOJI_GREEN_DOT} AI Enabled",
            color=C_SUCCESS
        )
    embed.description = f"{interaction.channel.mention} will auto-reply with OpenRouter."
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== TICKETS COMMANDS ====================
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="📩 Create Ticket", style=discord.ButtonStyle.success, custom_id="ticket_create"))

@tree.command(name="setup-ticket", description="[Admin] Send the ticket panel in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{EMOJI_TICKET} Support Center",
        description="Need help? Click the button below to create a ticket.",
        color=C_TICKET
    )
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, view=TicketPanelView())
    server_config["ticket_channel"] = interaction.channel.id
    save_server_config()

class TicketCreateModal(Modal):
    def __init__(self):
        super().__init__(title="Create Ticket")
        self.reason = TextInput(label="Reason / Category", placeholder="e.g. General Support, Billing", max_length=100)
        self.desc = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Describe your issue", max_length=1000)
        self.add_item(self.reason)
        self.add_item(self.desc)

    async def on_submit(self, interaction: discord.Interaction):
        for ch in interaction.guild.channels:
            if ch.name.startswith("ticket-") and ch.name.endswith(interaction.user.name.lower().replace(" ", "-")):
                return await interaction.response.send_message(f"{EMOJI_WARNING} You already have an open ticket.", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        channel_name = f"ticket-{interaction.user.name.lower().replace(' ', '-')}"
        try:
            ch = await interaction.guild.create_text_channel(channel_name, overwrites=overwrites, reason="Ticket created")
        except:
            return await interaction.response.send_message(f"{EMOJI_FAILED} Failed to create ticket channel.", ephemeral=True)
        embed = discord.Embed(title=f"{EMOJI_TICKET} Ticket Created", color=C_TICKET)
        embed.description = "Welcome! Please explain your issue. A staff member will be with you shortly."
        embed.add_field(name="👤 User", value=interaction.user.mention, inline=False)
        embed.add_field(name="📂 Reason", value=self.reason.value, inline=False)
        embed.set_footer(text=_footer())
        view = TicketChannelView(interaction.user.id)
        await ch.send(content=interaction.user.mention, embed=embed, view=view)
        await interaction.response.send_message(f"{EMOJI_SUCCESS} Ticket created: {ch.mention}", ephemeral=True)

class TicketChannelView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.add_item(Button(label=f"{EMOJI_LOCK} Close", style=discord.ButtonStyle.danger, custom_id="ticket_close"))
        self.add_item(Button(label=f"{EMOJI_OWNER} Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim"))
        self.add_item(Button(label=f"{EMOJI_UNLOCK} Unclaim", style=discord.ButtonStyle.secondary, custom_id="ticket_unclaim"))
        self.add_item(Button(label=f"{EMOJI_ADD} Add", style=discord.ButtonStyle.success, custom_id="ticket_add"))
        self.add_item(Button(label=f"{EMOJI_DELETE} Remove", style=discord.ButtonStyle.danger, custom_id="ticket_remove"))
        self.add_item(Button(label=f"{EMOJI_DOCUMENT} Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript"))

# ==================== GIVEAWAY COMMANDS ====================
class GiveawayView(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=None)
        self.gid = gid
        self.add_item(Button(label="🎉 Join", style=discord.ButtonStyle.success, custom_id=f"give_join_{gid}"))

giveaway_group = app_commands.Group(name="giveaway", description="Giveaway commands")

@giveaway_group.command(name="start", description="Start a new giveaway")
@app_commands.describe(prize="Prize", duration="Duration (e.g. 10m, 1h, 1d)", winners="Number of winners")
@app_commands.checks.has_permissions(manage_guild=True)
async def gstart(interaction: discord.Interaction, prize: str, duration: str, winners: app_commands.Range[int, 1, 10] = 1):
    seconds = 0
    match = re.match(r"(\d+)([smhd])", duration)
    if not match:
        return await interaction.response.send_message("Invalid duration. Use `10m`, `1h`, `1d`.", ephemeral=True)
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s": seconds = val
    elif unit == "m": seconds = val * 60
    elif unit == "h": seconds = val * 3600
    elif unit == "d": seconds = val * 86400
    if seconds < 10:
        return await interaction.response.send_message("Minimum duration is 10 seconds.", ephemeral=True)
    end_time = time.time() + seconds
    embed = discord.Embed(
        title=f"{EMOJI_GIVEAWAY} Giveaway Started",
        color=C_GOLD
    )
    embed.add_field(name="🎁 Prize", value=prize, inline=False)
    embed.add_field(name="👑 Host", value=interaction.user.mention, inline=True)
    embed.add_field(name="🏆 Winners", value=str(winners), inline=True)
    embed.add_field(name="⏰ Ends", value=f"<t:{int(end_time)}:R>", inline=True)
    embed.add_field(name="👥 Entries", value="0", inline=True)
    embed.set_footer(text=_footer())
    msg = await interaction.response.send_message(embed=embed, wait=True)
    gid = str(msg.id)
    giveaways[gid] = {"prize": prize, "winners": winners, "end_time": end_time, "host": str(interaction.user.id), "channel": interaction.channel_id, "participants": [], "ended": False, "paused": False}
    save_giveaways()
    await msg.edit(view=GiveawayView(gid))

@giveaway_group.command(name="end", description="End a giveaway early")
@app_commands.checks.has_permissions(manage_guild=True)
async def gend(interaction: discord.Interaction):
    active = [g for gid, g in giveaways.items() if not g.get("ended") and g.get("channel") == interaction.channel_id]
    if not active:
        return await interaction.response.send_message("No active giveaways in this channel.", ephemeral=True)
    options = [discord.SelectOption(label=g["prize"][:80], value=gid) for gid, g in giveaways.items() if not g.get("ended") and g.get("channel") == interaction.channel_id]
    class Sel(discord.ui.Select):
        async def callback(self, i: discord.Interaction):
            gid = self.values[0]
            await bot._end_giveaway(gid)
            await i.response.send_message("Giveaway ended.", ephemeral=True)
    view = View()
    view.add_item(Sel(placeholder="Select giveaway", options=options[:25]))
    await interaction.response.send_message("Select which giveaway to end:", view=view, ephemeral=True)

@giveaway_group.command(name="reroll", description="Reroll a giveaway winner")
@app_commands.checks.has_permissions(manage_guild=True)
async def greroll(interaction: discord.Interaction):
    ended = [g for gid, g in giveaways.items() if g.get("ended") and g.get("channel") == interaction.channel_id and len(g.get("participants", [])) > 1]
    if not ended:
        return await interaction.response.send_message("No eligible ended giveaways.", ephemeral=True)
    options = [discord.SelectOption(label=g["prize"][:80], value=gid) for gid, g in giveaways.items() if g.get("ended") and g.get("channel") == interaction.channel_id and len(g.get("participants", [])) > 1]
    class Sel(discord.ui.Select):
        async def callback(self, i: discord.Interaction):
            gid = self.values[0]
            g = giveaways[gid]
            participants = g.get("participants", [])
            if len(participants) < 2:
                return await i.response.send_message("Not enough participants.", ephemeral=True)
            winner = random.choice(participants)
            await i.channel.send(f"🎉 New winner: <@{winner}>!")
            await i.response.send_message("Rerolled.", ephemeral=True)
    view = View()
    view.add_item(Sel(placeholder="Select giveaway", options=options[:25]))
    await interaction.response.send_message("Select which giveaway to reroll:", view=view, ephemeral=True)

@giveaway_group.command(name="list", description="List all giveaways")
async def glist(interaction: discord.Interaction):
    guild_g = {gid: g for gid, g in giveaways.items() if g.get("channel") == interaction.channel_id}
    if not guild_g:
        return await interaction.response.send_message("No giveaways in this channel.", ephemeral=True)
    embed = discord.Embed(
        title=f"{EMOJI_GIVEAWAY} Giveaway List",
        color=C_INFO
    )
    active, ended = [], []
    for gid, g in guild_g.items():
        if g.get("ended"):
            ended.append(f"🎁 {g['prize']} (Ended)")
        else:
            active.append(f"🎁 {g['prize']} - <t:{int(g['end_time'])}:R>")
    if active: embed.add_field(name="🟢 Active", value="\n".join(active[:10]), inline=False)
    if ended: embed.add_field(name="🔴 Ended", value="\n".join(ended[:10]), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

tree.add_command(giveaway_group)

# ==================== EXECUTOR COMMANDS ====================
@tree.command(name="setupexecutor", description="[Admin] Configure executor update channel")
@app_commands.describe(channel="Channel for updates", role="Role to mention (optional)")
@app_commands.checks.has_permissions(administrator=True)
async def setupexecutor_cmd(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
    executor_config["channel_id"] = channel.id
    executor_config["role_id"] = role.id if role else None
    save_executor_config()
    embed = discord.Embed(
        title=f"{EMOJI_SUCCESS} Executor Alerts Configured",
        color=C_SUCCESS
    )
    embed.description = f"Updates will be sent to {channel.mention}."
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="removeexecutoralerts", description="[Admin] Disable executor alerts")
@app_commands.checks.has_permissions(administrator=True)
async def removeexecutoralerts_cmd(interaction: discord.Interaction):
    if os.path.exists(EXECUTOR_CONFIG_FILE):
        os.remove(EXECUTOR_CONFIG_FILE)
        await interaction.response.send_message("Executor alerts disabled.", ephemeral=True)
    else:
        await interaction.response.send_message("No executor alert configuration found.", ephemeral=True)

# ==================== MODERATION COMMANDS ====================
@tree.command(name="ban", description="[Mod] Ban a user")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if member.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(f"{EMOJI_WARNING} Cannot ban this user.", ephemeral=True)
    try:
        await member.ban(reason=reason, delete_message_days=0)
        embed = discord.Embed(
            title=f"{EMOJI_ADMIN} User Banned",
            description=f"**{member}** banned.\nReason: {reason}",
            color=C_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJI_FAILED} Error: {e}", ephemeral=True)

@tree.command(name="kick", description="[Mod] Kick a user")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if member.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(f"{EMOJI_WARNING} Cannot kick this user.", ephemeral=True)
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(
            title=f"{EMOJI_ADMIN} User Kicked",
            description=f"**{member}** kicked.\nReason: {reason}",
            color=C_ORANGE
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJI_FAILED} Error: {e}", ephemeral=True)

@tree.command(name="timeout", description="[Mod] Timeout a user")
@app_commands.describe(member="User", duration="Duration (e.g. 10m, 1h)", reason="Reason")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
    seconds = 0
    match = re.match(r"(\d+)([smhd])", duration)
    if not match:
        return await interaction.response.send_message("Invalid duration format.", ephemeral=True)
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s": seconds = val
    elif unit == "m": seconds = val * 60
    elif unit == "h": seconds = val * 3600
    elif unit == "d": seconds = val * 86400
    if seconds < 60:
        return await interaction.response.send_message("Minimum timeout is 1 minute.", ephemeral=True)
    if seconds > 2419200:
        return await interaction.response.send_message("Maximum timeout is 28 days.", ephemeral=True)
    try:
        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await member.timeout(until, reason=reason)
        embed = discord.Embed(
            title=f"{EMOJI_CLOCK} Timeout Applied",
            description=f"**{member}** timed out for **{duration}**.\nReason: {reason}",
            color=C_ORANGE
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJI_FAILED} Error: {e}", ephemeral=True)

@tree.command(name="warn", description="[Mod] Warn a user")
@app_commands.checks.has_permissions(kick_members=True)
async def warn_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    gid, uid = str(interaction.guild_id), str(member.id)
    warnings.setdefault(gid, {}).setdefault(uid, []).append({"mod": str(interaction.user.id), "reason": reason, "ts": int(time.time())})
    save_warnings()
    count = len(warnings[gid][uid])
    embed = discord.Embed(
        title=f"{EMOJI_WARNING} Warning Issued",
        description=f"**{member}** warned.\nReason: {reason}\nTotal: {count}",
        color=C_GOLD
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="clear", description="[Mod] Clear messages (max 10000)")
@app_commands.describe(amount="Amount")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_cmd(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 10000]):
    await interaction.response.defer(ephemeral=True)
    deleted = 0
    remaining = amount
    while remaining > 0:
        batch = min(remaining, 100)
        purged = await interaction.channel.purge(limit=batch)
        deleted += len(purged)
        remaining -= len(purged)
        if len(purged) < batch:
            break
    embed = discord.Embed(
        title=f"{EMOJI_SUCCESS} Messages Cleared",
        description=f"Deleted **{deleted}** messages.",
        color=C_SUCCESS
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="lock", description="[Mod] Lock the channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock_cmd(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    embed = discord.Embed(
        title=f"{EMOJI_LOCK} Channel Locked",
        color=C_ERROR
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="unlock", description="[Mod] Unlock the channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock_cmd(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    embed = discord.Embed(
        title=f"{EMOJI_UNLOCK} Channel Unlocked",
        color=C_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="slowmode", description="[Mod] Set slowmode (0 to disable, max 21600s)")
@app_commands.describe(seconds="Seconds")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode_cmd(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    await interaction.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        embed = discord.Embed(
            title=f"{EMOJI_CLOCK} Slowmode Disabled",
            color=C_SUCCESS
        )
    else:
        embed = discord.Embed(
            title=f"{EMOJI_CLOCK} Slowmode Set",
            description=f"Slowmode: {seconds}s",
            color=C_GOLD
        )
    await interaction.response.send_message(embed=embed)

# ==================== UTILITY COMMANDS ====================
@tree.command(name="ping", description="Check bot latency")
async def ping_cmd(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title=f"{EMOJI_PC} Pong!",
        description=f"Latency: `{latency}ms`",
        color=C_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="help", description="View all commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{EMOJI_GREEN_CROWN} Help Center",
        description=f"Support: [Join Server]({SUPPORT_SERVER_URL})",
        color=C_INFO
    )
    embed.add_field(name="🎫 Tickets", value="`/setup-ticket` `/ticket` `/close` `/add` `/remove` `/transcript`", inline=False)
    embed.add_field(name="🎉 Giveaways", value="`/giveaway start` `/giveaway end` `/giveaway reroll` `/giveaway list`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`/ban` `/kick` `/timeout` `/warn` `/clear` `/lock` `/unlock` `/slowmode`", inline=False)
    embed.add_field(name="📊 Utility", value="`/ping` `/help` `/serverinfo` `/userinfo` `/avatar` `/botinfo`", inline=False)
    embed.add_field(name="🎭 Fun", value="`/8ball` `/coinflip` `/dice` `/meme`", inline=False)
    embed.add_field(name="💰 Economy", value="`/balance` `/daily` `/work` `/pay`", inline=False)
    embed.add_field(name="🤖 AI", value="`/setupia`", inline=False)
    embed.add_field(name="⚡ Executor", value="`/setupexecutor` `/removeexecutoralerts`", inline=False)
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed)

@tree.command(name="serverinfo", description="Server information")
async def serverinfo_cmd(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(
        title=f"{EMOJI_HOUSE} {g.name}",
        color=C_INFO
    )
    embed.add_field(name="👑 Owner", value=g.owner.mention)
    embed.add_field(name="👥 Members", value=str(g.member_count))
    embed.add_field(name="📁 Channels", value=str(len(g.channels)))
    embed.add_field(name="🎭 Roles", value=str(len(g.roles)))
    embed.add_field(name="📅 Created", value=f"<t:{int(g.created_at.timestamp())}:R>")
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="User information")
@app_commands.describe(member="User (optional)")
async def userinfo_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(
        title=f"{EMOJI_MEMBER} {target.display_name}",
        color=C_INFO
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
    embed.add_field(name="Joined", value=f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "Unknown", inline=True)
    embed.add_field(name="Created", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="avatar", description="Get a user's avatar")
@app_commands.describe(member="User (optional)")
async def avatar_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(
        title=f"{EMOJI_PC} Avatar of {target.display_name}",
        color=C_PURPLE
    )
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="botinfo", description="Bot information")
async def botinfo_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{EMOJI_GREEN_CROWN} Bot Information",
        color=C_SUCCESS
    )
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Commands", value=str(len(bot.tree.get_commands())), inline=True)
    embed.add_field(name="Uptime", value=format_uptime(bot.BOT_START_TIME), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=True)
    if bot.user: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed)

# ==================== FUN COMMANDS ====================
@tree.command(name="8ball", description="Ask the magic 8-ball")
@app_commands.describe(question="Your question")
async def ball8_cmd(interaction: discord.Interaction, question: str):
    answers = ["Yes", "No", "Maybe", "Definitely", "Don't count on it"]
    embed = discord.Embed(
        title=f"{EMOJI_8BALL} 8-Ball",
        color=0x2B2D31
    )
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(answers), inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="coinflip", description="Flip a coin")
async def coinflip_cmd(interaction: discord.Interaction):
    result = random.choice(["🦅 Heads", "🪙 Tails"])
    embed = discord.Embed(
        title=f"{EMOJI_COIN} Coin Flip",
        description=f"Result: **{result}**",
        color=C_GOLD
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="dice", description="Roll a die")
@app_commands.describe(sides="Number of sides (4-100)")
async def dice_cmd(interaction: discord.Interaction, sides: app_commands.Range[int, 4, 100] = 6):
    result = random.randint(1, sides)
    embed = discord.Embed(
        title=f"{EMOJI_DICE} Dice Roll",
        description=f"Rolled **{result}** (1-{sides})",
        color=C_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="meme", description="Random meme from Reddit")
async def meme_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    sub = random.choice(["memes", "dankmemes", "wholesomememes"])
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://www.reddit.com/r/{sub}/random.json?limit=1"
            async with session.get(url, headers={"User-Agent": "KingBot/2.0"}, timeout=10) as resp:
                data = await resp.json()
                post = data[0]["data"]["children"][0]["data"]
                img = post.get("url", "")
                if not img.lower().endswith((".jpg", ".png", ".gif", ".jpeg")):
                    return await interaction.followup.send("No image found.", ephemeral=True)
                embed = discord.Embed(
                    title=post.get("title", "Meme"),
                    color=C_FUN
                )
                embed.set_image(url=img)
                await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send("Error fetching meme.", ephemeral=True)

# ==================== ECONOMY COMMANDS ====================
@tree.command(name="balance", description="Check your balance")
@app_commands.describe(member="User (optional)")
async def balance_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    uid = str(target.id)
    economy.setdefault(uid, {"cash": 0, "bank": 0})
    data = economy[uid]
    embed = discord.Embed(
        title=f"{EMOJI_MONEY} Wallet",
        color=C_SUCCESS
    )
    embed.add_field(name="User", value=target.mention, inline=True)
    embed.add_field(name="Cash", value=f"${data['cash']:,}", inline=True)
    embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
    embed.add_field(name="Total", value=f"${data['cash'] + data['bank']:,}", inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="daily", description="Claim your daily reward")
async def daily_cmd(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    economy.setdefault(uid, {"cash": 0, "bank": 0, "daily": 0})
    now = time.time()
    if now - economy[uid].get("daily", 0) < 86400:
        remaining = 86400 - (now - economy[uid]["daily"])
        return await interaction.response.send_message(f"⏰ Wait {int(remaining//3600)}h {int((remaining%3600)//60)}m.", ephemeral=True)
    reward = random.randint(100, 500)
    economy[uid]["cash"] += reward
    economy[uid]["daily"] = now
    save_economy()
    embed = discord.Embed(
        title=f"{EMOJI_GIFT} Daily Reward",
        description=f"You received **${reward}**!",
        color=C_GOLD
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="work", description="Work to earn cash")
async def work_cmd(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    economy.setdefault(uid, {"cash": 0, "bank": 0, "work": 0})
    now = time.time()
    if now - economy[uid].get("work", 0) < 3600:
        remaining = 3600 - (now - economy[uid]["work"])
        return await interaction.response.send_message(f"⏰ Wait {int(remaining//60)}m.", ephemeral=True)
    earnings = random.randint(50, 200)
    economy[uid]["cash"] += earnings
    economy[uid]["work"] = now
    save_economy()
    embed = discord.Embed(
        title=f"{EMOJI_BITCASH} Work Complete",
        description=f"You earned **${earnings}**!",
        color=C_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="pay", description="Pay another user")
@app_commands.describe(member="Recipient", amount="Amount")
async def pay_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        return await interaction.response.send_message("Amount must be positive.", ephemeral=True)
    uid = str(interaction.user.id)
    economy.setdefault(uid, {"cash": 0, "bank": 0})
    if economy[uid]["cash"] < amount:
        return await interaction.response.send_message("Not enough cash.", ephemeral=True)
    economy[uid]["cash"] -= amount
    economy.setdefault(str(member.id), {"cash": 0, "bank": 0})["cash"] += amount
    save_economy()
    embed = discord.Embed(
        title=f"{EMOJI_MONEY} Payment Sent",
        description=f"Paid {member.mention} **${amount}**.",
        color=C_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

# ==================== START BOT ====================
async def main():
    if not TOKEN:
        logger.error("DISCORD_TOKEN not set.")
        return
    health_thread = threading.Thread(target=_start_health_server, daemon=True)
    health_thread.start()
    logger.info(f"Starting {BOT_NAME}...")
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
