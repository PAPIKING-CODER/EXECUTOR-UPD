"""
KING BOT — Complete Premium Bot
All commands, features, and fixes integrated.
"""

import sys
import types
import os
import re
import json
import time
import asyncio
import logging
import threading
import random
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote
from collections import defaultdict

import discord
from discord import app_commands
from discord.ui import Button, View, Modal, Select
from discord.ext import tasks
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── LOGGING ──────────────────────────────────────────────────────
logger = logging.getLogger("KING")
logger.setLevel(logging.INFO)
for _h in (RotatingFileHandler("bot.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"),
           logging.StreamHandler()):
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(_h)

# ── CONFIGURATION ────────────────────────────────────────────────
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
PORT = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL = os.environ.get("BOT_INVITE_URL",
    "https://discord.com/oauth2/authorize?client_id=1525040833814855710")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

BOT_NAME = "KING BOT"
BOT_CREDIT = "BY KING"
BOT_VERSION = "2.0"
BOT_FOOTER = "MADE WITH 💚 • KING BYPASS"

BYPASS_API_URL = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT = 30
BYPASS_RETRIES = 3
BYPASS_DELAY = 3

# File paths for persistent storage
AUTOBYPASS_FILE = "autobypass_channels.json"
AI_CHANNELS_FILE = "ai_channels.json"
WARNINGS_FILE = "warnings.json"
LEVELS_FILE = "levels.json"
GIVEAWAYS_FILE = "giveaways.json"
TICKETS_FILE = "tickets.json"
AFK_FILE = "afk.json"
REMINDERS_FILE = "reminders.json"
REACTION_ROLES_FILE = "reaction_roles.json"
HISTORY_FILE = "history.json"
EXECUTOR_CHANNELS_FILE = "executor_channels.json"

BOT_START = datetime.now(timezone.utc)

# ── CUSTOM EMOJIS ──────────────────────────────────────────────
class Emojis:
    add_symbol = "<:add_symbol:1527235736116527179>"
    Admin = "<:Admin:1526850858271248384>"
    Alarm = "<:Alarm:1525787989354086411>"
    AnnouncementPingRoleIcon = "<:AnnouncementPingRoleIcon:1526855584807256124>"
    Attention = "<:Attention:1526850359958704138>"
    Awesomeface14 = "<:Awesomeface14:1526850663575982222>"
    BitCash = "<:BitCash:1526850558726508564>"
    CameraRedLogo = "<:CameraRedLogo:1526854158680981504>"
    Cart = "<:Cart:1526854833125195786>"
    Clipboard = "<:Clipboard:1527231830430842891>"
    clock = "<:clock:1525380296852377711>"
    clown = "<:clown:1526858087510835252>"
    clown2 = "<:clown:1526858673404510268>"
    copy_text = "<:copy_text:1526743644894138479>"
    CopyPaste = "<:CopyPaste:1525379105111932958>"
    Cursor_click = "<:Cursor_click:1526857184116477962>"
    DarkBlueArrow = "<:DarkBlueArrow:1526850610547396690>"
    Database = "<:Database:1527233297623679028>"
    Developer = "<:Developer:1527232205171068992>"
    Diamond = "<:Diamond:1526858613572894780>"
    DiamondHand = "<:DiamondHand:1527233825237745826>"
    Discount = "<:Discount:1527231806774847581>"
    DoubleRightArrow = "<:DoubleRightArrow:1527232622690033715>"
    Error = "<:Error:1526854353619656805>"
    Error2 = "<:Error2:1526855155797061754>"
    Folder = "<:Folder:1526854262280036372>"
    GreenArrow = "<:GreenArrow:1526857606084268095>"
    GreenCheckmark = "<:GreenCheckmark:1526855067586789386>"
    GreenTick = "<:GreenTick:1527233240899913748>"
    GreyArrow = "<:GreyArrow:1527233584492933130>"
    grey_line = "<:grey_line:1526859535623520276>"
    GreyQuestion = "<:GreyQuestion:1526859684391159808>"
    GreyQuestionMark = "<:GreyQuestionMark:1526857379436642394>"
    Heart = "<:Heart:1526856039885164554>"
    Image = "<:Image:1526858395913934858>"
    Info = "<:Info:1526855284914653205>"
    Join = "<:Join:1527232869524662392>"
    LeftArrow = "<:LeftArrow:1527235653216976906>"
    Link = "<:Link:1527233749370886296>"
    Loading = "<:Loading:1526850199107266693>"
    lock = "<:lock:1527235546362871838>"
    Mail = "<:Mail:1527235926974842930>"
    Members = "<:Members:1527233062529878076>"
    Message = "<:Message:1526859153673803786>"
    Moderator = "<:Moderator:1527232335102081116>"
    Money = "<:Money:1526857281906767944>"
    New = "<:New:1527233969806737458>"
    No = "<:No:1526854412717391955>"
    Nitro = "<:Nitro:1526853872159705138>"
    Notification = "<:Notification:1526857834816436264>"
    Online = "<:Online:1526854662970259556>"
    Owner = "<:Owner:1527232114523496540>"
    Partner = "<:Partner:1527232427577694329>"
    Pin = "<:Pin:1527231758586486846>"
    PinkArrow = "<:PinkArrow:1526857848309250108>"
    Plus = "<:Plus:1526858484363405412>"
    Question = "<:Question:1526854903945717761>"
    RedArrow = "<:RedArrow:1526856897289089064>"
    Reload = "<:Reload:1527232027449747547>"
    RightArrow = "<:RightArrow:1526856208559091772>"
    Robot = "<:Robot:1527233491450552391>"
    Rules = "<:Rules:1527235781577799740>"
    Search = "<:Search:1527232943235352687>"
    Settings = "<:Settings:1526854350797013013>"
    Shield = "<:Shield:1527235705413294160>"
    Star = "<:Star:1527231986333118464>"
    Support = "<:Support:1527232769209557042>"
    Ticket = "<:Ticket:1527232981135212545>"
    Time = "<:Time:1527233417597370409>"
    Trash = "<:Trash:1527231903986342020>"
    Unlock = "<:Unlock:1527235509477892206>"
    User = "<:User:1527232382631260190>"
    Verified = "<:Verified:1526857077157484606>"
    Warning = "<:Warning:1527233342573850744>"
    Welcome = "<:Welcome:1526859860837029919>"
    WhiteArrow = "<:WhiteArrow:1526856107421829120>"
    WhiteTick = "<:WhiteTick:1526854546389868677>"
    Wrench = "<:Wrench:1527231882477826168>"
    x = "<:x:1526854695354466445>"
    YellowArrow = "<:YellowArrow:1526857769141893130>"
    YellowQuestion = "<:YellowQuestion:1526857155486025760>"

    # Existing emojis (for compatibility)
    CHECK = "<a:_:1511381303872716820>"
    REDPT = "<a:_:1463164698353733725>"
    WARN = "<:_:1495901573476520106>"
    RDIAM = "<a:_:1469195655762153502>"
    ARROW = "<a:_:1401389285042684035>"
    CROWN = "<a:_:1461735621985833061>"
    NO = "<a:_:606562703917449226>"
    LOAD = "<a:_:1463540610379022429>"
    USER = "👤"

# URLs for emoji images (for thumbnail/author icons)
URL_CHECK = "https://cdn.discordapp.com/emojis/1511381303872716820.webp?size=100&animated=true"
URL_REDPT = "https://cdn.discordapp.com/emojis/1463164698353733725.webp?size=100&animated=true"
URL_WARN = "https://cdn.discordapp.com/emojis/1495901573476520106.webp?size=100"
URL_RDIAM = "https://cdn.discordapp.com/emojis/1469195655762153502.webp?size=100&animated=true"
URL_CROWN = "https://cdn.discordapp.com/emojis/1461735621985833061.webp?size=100&animated=true"
URL_NO = "https://cdn.discordapp.com/emojis/606562703917449226.webp?size=100&animated=true"
URL_LOAD = "https://cdn.discordapp.com/emojis/1463540610379022429.webp?size=100&animated=true"
IMG_MAIN = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a5485bb&is=6a53343b&hm=f6df69c459c7bad9ed031d12eee35f42ab4adbb7290fe08a3707046eb3bf7200&"

# ── COLORS ──────────────────────────────────────────────────────
class Colors:
    RED = 0xC80000
    DARK = 0x1A0000
    WARN = 0xFF4500
    INFO = 0x8B0000
    GREEN = 0x00FF00
    BLUE = 0x0000FF
    GOLD = 0xFFD700
    PURPLE = 0x800080
    ORANGE = 0xFFA500

# ── JSON HELPERS ────────────────────────────────────────────────
def load_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"load_json {path}: {e}")
    return default

def save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"save_json {path}: {e}")

# ── DATA STORAGE ─────────────────────────────────────────────────
autobypass_channels: Dict[int, Dict[str, Any]] = load_json(AUTOBYPASS_FILE, {})
ai_channels: set = set(load_json(AI_CHANNELS_FILE, []))
warnings: Dict[int, List[Dict]] = load_json(WARNINGS_FILE, {})
levels: Dict[int, Dict[int, int]] = load_json(LEVELS_FILE, {})  # guild_id -> user_id -> xp
giveaways: Dict[str, Any] = load_json(GIVEAWAYS_FILE, {})
tickets: Dict[int, Dict] = load_json(TICKETS_FILE, {})
afk_status: Dict[int, Dict[int, str]] = load_json(AFK_FILE, {})
reminders: List[Dict] = load_json(REMINDERS_FILE, [])
reaction_roles: Dict[str, Dict] = load_json(REACTION_ROLES_FILE, {})
history: List[Dict] = load_json(HISTORY_FILE, [])
executor_channels: set = set(load_json(EXECUTOR_CHANNELS_FILE, []))

def save_all():
    save_json(AUTOBYPASS_FILE, autobypass_channels)
    save_json(AI_CHANNELS_FILE, list(ai_channels))
    save_json(WARNINGS_FILE, warnings)
    save_json(LEVELS_FILE, levels)
    save_json(GIVEAWAYS_FILE, giveaways)
    save_json(TICKETS_FILE, tickets)
    save_json(AFK_FILE, afk_status)
    save_json(REMINDERS_FILE, reminders)
    save_json(REACTION_ROLES_FILE, reaction_roles)
    save_json(HISTORY_FILE, history)
    save_json(EXECUTOR_CHANNELS_FILE, list(executor_channels))

# ── HELPERS ──────────────────────────────────────────────────────
_URL_RE = re.compile(r"https?://[^\s<>\"']{6,}")

def _is_url(u: str) -> bool:
    return bool(re.match(r"^https?://\S{6,}", u))

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START
    t = int(d.total_seconds())
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _footer() -> str:
    return f"{BOT_NAME} • {BOT_CREDIT} • {BOT_FOOTER}"

def _format_time(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

# ── BYPASS ENGINE (improved with aiohttp) ──────────────────────
_KEYS = ("content", "result", "loadstring", "bypassed", "bypassed_link",
         "bypassed_url", "final_url", "destination", "url", "link", "key", "output")

def _extract(data):
    if isinstance(data, dict):
        for k in _KEYS:
            if k in data:
                v = data[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (dict, list)):
                    r = _extract(v)
                    if r:
                        return r
        for v in data.values():
            if isinstance(v, (dict, list)):
                r = _extract(v)
                if r:
                    return r
    elif isinstance(data, list):
        for item in data:
            r = _extract(item)
            if r:
                return r
    return None

async def bypass_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Asynchronous bypass using aiohttp with retries and timeout."""
    last_err = "Unknown error"
    for attempt in range(1, BYPASS_RETRIES + 1):
        try:
            async with aiohttp.ClientSession() as session:
                full_url = BYPASS_API_URL + quote(url, safe="")
                async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=BYPASS_TIMEOUT)) as resp:
                    if resp.status != 200:
                        last_err = f"HTTP {resp.status}"
                        if attempt < BYPASS_RETRIES:
                            await asyncio.sleep(BYPASS_DELAY)
                        continue
                    try:
                        data = await resp.json()
                    except:
                        text = await resp.text()
                        if text.strip().startswith("http"):
                            return text.strip(), None
                        last_err = "Invalid response"
                        if attempt < BYPASS_RETRIES:
                            await asyncio.sleep(BYPASS_DELAY)
                        continue
                    api_err = isinstance(data, dict) and (
                        data.get("success") is False or data.get("error")
                        or str(data.get("status", "")).lower() == "error")
                    result = _extract(data)
                    if result and not api_err:
                        return result, None
                    if api_err:
                        msg = (data.get("message") or data.get("error")) if isinstance(data, dict) else None
                        last_err = str(msg or "No result")
                        if attempt < BYPASS_RETRIES:
                            await asyncio.sleep(BYPASS_DELAY)
                        continue
                    return None, "No result"
        except asyncio.TimeoutError:
            last_err = f"Timeout ({BYPASS_TIMEOUT}s)"
            if attempt < BYPASS_RETRIES:
                await asyncio.sleep(BYPASS_DELAY)
        except Exception as ex:
            last_err = str(ex)[:100]
            if attempt < BYPASS_RETRIES:
                await asyncio.sleep(BYPASS_DELAY)
    return None, last_err

# ── BYPASS EMBEDS ────────────────────────────────────────────────
def embed_bypass_success(result: str, elapsed: float, url: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=Colors.GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.GreenCheckmark} KING BOT • BYPASS Success", icon_url=URL_CHECK)
    e.set_thumbnail(url=URL_CHECK)
    e.add_field(
        name=f"{Emojis.Link} Result",
        value=f"```\n{result[:900]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{Emojis.Time} Response Time",
        value=f"```\n{elapsed:.2f} Seconds\n```",
        inline=False
    )
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"{_footer()} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return e

def embed_bypass_fail(error: str, url: str, elapsed: float, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=Colors.RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.No} KING BOT • BYPASS Failed", icon_url=URL_NO)
    e.set_thumbnail(url=URL_NO)
    e.add_field(
        name=f"{Emojis.Link} URL",
        value=f"```\n{url[:200]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{Emojis.Warning} Error",
        value=f"```\n{error or '?'}\n```",
        inline=False
    )
    e.add_field(
        name=f"{Emojis.Time} Response Time",
        value=f"```\n{elapsed:.2f} Seconds\n```",
        inline=False
    )
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"{_footer()} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return e

def embed_bypass_loading() -> discord.Embed:
    e = discord.Embed(color=Colors.WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.Loading} KING BOT • Processing Bypass...", icon_url=URL_LOAD)
    e.set_thumbnail(url=URL_LOAD)
    e.description = f"{Emojis.Loading} Bypass in progress, please wait..."
    e.set_footer(text=_footer())
    return e

# ── VIEWS ──────────────────────────────────────────────────────
class BypassView(View):
    def __init__(self, result: str, elapsed: float):
        super().__init__(timeout=None)
        self._result = result
        self.add_item(Button(
            label=f"⏰ {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True, row=0))
        self.add_item(Button(
            label="SUPPORT SERVER", emoji="💬",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(
            label="INVITE ME", emoji="🤖",
            url=BOT_INVITE_URL,
            style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="📋 Copy Result", style=discord.ButtonStyle.danger, row=1)
    async def copy_btn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            content=f"```\n{self._result[:1800]}\n```", ephemeral=True)

class FailView(View):
    def __init__(self, elapsed: float):
        super().__init__(timeout=None)
        self.add_item(Button(
            label=f"⏰ {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True, row=0))
        self.add_item(Button(
            label="SUPPORT SERVER", emoji="💬",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link, row=0))

# ── AI ENGINE (OpenRouter) ─────────────────────────────────────
async def ai_generate_response(prompt: str) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://openrouter.ai/api/v1/chat/completions",
                                    headers=headers, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"OpenRouter API error: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return None

def embed_ai_response(content: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=Colors.BLUE, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.Robot} KING BOT • AI Response", icon_url=URL_CROWN)
    e.set_thumbnail(url=URL_CROWN)
    e.add_field(
        name=f"{Emojis.User} From",
        value=user.mention,
        inline=True
    )
    e.add_field(
        name=f"{Emojis.Message} Response",
        value=content[:2000],
        inline=False
    )
    e.set_footer(text=_footer())
    return e

# ── EXECUTOR STATUS FETCH ──────────────────────────────────────
async def fetch_executor_status() -> Dict[str, Any]:
    """Fetch executor status from multiple APIs."""
    results = {}
    apis = {
        "Executors Online": "https://www.executors.online/api/status",
        "What Execs Are": "https://whatexpsare.online/api/status"
    }
    async with aiohttp.ClientSession() as session:
        for name, url in apis.items():
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results[name] = data
                    else:
                        results[name] = {"error": f"HTTP {resp.status}"}
            except Exception as e:
                results[name] = {"error": str(e)}
    return results

def embed_executor_status(data: Dict[str, Any]) -> discord.Embed:
    e = discord.Embed(color=Colors.PURPLE, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.Settings} KING BOT • Executor Status", icon_url=URL_CROWN)
    for name, info in data.items():
        status = info.get("status", "Unknown")
        version = info.get("version", "N/A")
        e.add_field(
            name=f"{Emojis.Database} {name}",
            value=f"**Status:** {status}\n**Version:** {version}",
            inline=False
        )
    e.set_footer(text=_footer())
    return e

# ── GIVEAWAY TASKS ──────────────────────────────────────────────
class GiveawayManager:
    def __init__(self, bot):
        self.bot = bot
        self.giveaways = giveaways

    async def end_giveaway(self, giveaway_id: str):
        gw = self.giveaways.get(giveaway_id)
        if not gw:
            return
        channel = self.bot.get_channel(gw["channel_id"])
        if not channel:
            return
        # Pick winners
        entrants = gw.get("entrants", [])
        winners_count = gw.get("winners", 1)
        if not entrants:
            await channel.send(f"Giveaway ended, but no one entered!")
            del self.giveaways[giveaway_id]
            save_json(GIVEAWAYS_FILE, self.giveaways)
            return
        winners = random.sample(entrants, min(winners_count, len(entrants)))
        winner_mentions = ", ".join(f"<@{w}>" for w in winners)
        await channel.send(
            f"🎉 **Giveaway Ended!**\n"
            f"Prize: **{gw['prize']}**\n"
            f"Winners: {winner_mentions}"
        )
        del self.giveaways[giveaway_id]
        save_json(GIVEAWAYS_FILE, self.giveaways)

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = datetime.now(timezone.utc)
        for gid, gw in list(self.giveaways.items()):
            end_time = datetime.fromisoformat(gw["end_time"])
            if now >= end_time:
                await self.end_giveaway(gid)

# ── TICKET SYSTEM ──────────────────────────────────────────────
class TicketView(View):
    def __init__(self, ticket_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.owner_id = owner_id

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_btn(self, interaction: discord.Interaction, _):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        channel = interaction.channel
        # Archive and delete later
        await asyncio.sleep(2)
        await channel.delete()

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, emoji="👋")
    async def claim_btn(self, interaction: discord.Interaction, _):
        if interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}", ephemeral=False)
        else:
            await interaction.response.send_message("You don't have permission to claim tickets.", ephemeral=True)

async def create_ticket(guild: discord.Guild, user: discord.User, reason: str = None) -> Optional[discord.TextChannel]:
    category = discord.utils.get(guild.categories, name="Tickets")
    if not category:
        category = await guild.create_category("Tickets")
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    ticket_name = f"ticket-{user.name}"
    channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
    await channel.send(
        f"Welcome {user.mention}! A support team member will be with you shortly.\n"
        f"Reason: {reason or 'No reason provided'}",
        view=TicketView(ticket_id=channel.id, owner_id=user.id)
    )
    return channel

# ── LEVEL SYSTEM ──────────────────────────────────────────────
def get_level(xp: int) -> int:
    return int((xp / 100) ** 0.5)  # simple formula

def get_xp_for_level(level: int) -> int:
    return int((level) ** 2 * 100)

async def add_xp(guild_id: int, user_id: int, amount: int):
    if guild_id not in levels:
        levels[guild_id] = {}
    if user_id not in levels[guild_id]:
        levels[guild_id][user_id] = 0
    levels[guild_id][user_id] += amount
    save_json(LEVELS_FILE, levels)

# ── REACTION ROLE ──────────────────────────────────────────────
class ReactionRoleView(View):
    def __init__(self, message_id: int, roles: Dict[str, int]):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.roles = roles
        for emoji, role_id in roles.items():
            self.add_item(Button(label=emoji, custom_id=f"rr_{emoji}_{role_id}", style=discord.ButtonStyle.secondary))

    @discord.ui.button(label="Remove all", style=discord.ButtonStyle.danger, custom_id="rr_remove_all")
    async def remove_all(self, interaction: discord.Interaction, _):
        # Remove all reaction roles from user
        await interaction.response.send_message("Not implemented yet.", ephemeral=True)

# ── POLL VIEW ──────────────────────────────────────────────────
class PollView(View):
    def __init__(self, options: List[str]):
        super().__init__(timeout=None)
        self.options = options
        self.votes = defaultdict(int)
        for i, opt in enumerate(options):
            emoji = chr(0x1F1E6 + i) if i < 26 else "🔢"
            self.add_item(Button(label=f"{emoji} {opt}", custom_id=f"poll_{i}", style=discord.ButtonStyle.primary))

    @discord.ui.button(label="📊 Results", style=discord.ButtonStyle.secondary)
    async def results(self, interaction: discord.Interaction, _):
        total = sum(self.votes.values())
        if total == 0:
            await interaction.response.send_message("No votes yet.", ephemeral=True)
            return
        lines = []
        for i, opt in enumerate(self.options):
            count = self.votes[i]
            percent = (count / total) * 100
            bar = "█" * int(percent / 10) + "░" * (10 - int(percent / 10))
            lines.append(f"{chr(0x1F1E6 + i)} {opt}: {count} votes ({percent:.1f}%) {bar}")
        await interaction.response.send_message("```\n" + "\n".join(lines) + "\n```", ephemeral=True)

# ── BOT CLASS ──────────────────────────────────────────────────
class KingBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.messages = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.giveaway_manager = GiveawayManager(self)

    async def setup_hook(self):
        await self.tree.sync()
        self.giveaway_manager.check_giveaways.start()

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online as {self.user} | {len(self.guilds)} servers")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"/help • {BOT_NAME}"))

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Auto-bypass
        if message.channel.id in autobypass_channels:
            # Delete any message in the channel (regardless of content)
            try:
                await message.delete()
            except Exception:
                pass

            urls = _URL_RE.findall(message.content)
            if urls:
                # Process first URL only
                asyncio.create_task(self._auto_bypass(message, urls[0]))

        # AI auto-response
        if message.channel.id in ai_channels:
            asyncio.create_task(self._ai_response(message))

    async def _auto_bypass(self, original_message: discord.Message, url: str):
        if not _is_url(url):
            return
        # Send loading message
        try:
            loading_msg = await original_message.channel.send(
                content=original_message.author.mention, embed=embed_bypass_loading())
        except Exception:
            return

        t0 = time.time()
        result, error = await bypass_url(url)
        elapsed = time.time() - t0

        # Delete loading message after 120 seconds (configurable via autobypass_channels settings)
        auto_delete_time = autobypass_channels.get(original_message.channel.id, {}).get("auto_delete_time", 120)
        if result:
            embed = embed_bypass_success(result, elapsed, url, original_message.author)
            view = BypassView(result, elapsed)
        else:
            embed = embed_bypass_fail(error, url, elapsed, original_message.author)
            view = FailView(elapsed)

        try:
            msg = await loading_msg.edit(content=original_message.author.mention, embed=embed, view=view)
        except Exception:
            return

        # Schedule deletion after auto_delete_time
        async def delete_later():
            await asyncio.sleep(auto_delete_time)
            try:
                await msg.delete()
            except Exception:
                pass
        asyncio.create_task(delete_later())

        # Add to history
        history.append({
            "url": url,
            "result": result or error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": original_message.author.id
        })
        if len(history) > 100:
            history.pop(0)
        save_json(HISTORY_FILE, history)

    async def _ai_response(self, message: discord.Message):
        # Generate response via OpenRouter
        response = await ai_generate_response(message.content)
        if response:
            embed = embed_ai_response(response, message.author)
            await message.channel.send(embed=embed)

bot = KingBot()

# ── SLASH COMMANDS ─────────────────────────────────────────────

# ── BYPASS COMMANDS ────────────────────────────────────────────
@bot.tree.command(name="bypass", description="Bypass a URL")
@app_commands.describe(url="The URL to bypass")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_url(url):
        e = discord.Embed(description=f"{Emojis.Warning} Invalid URL.", color=Colors.RED)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)
    await interaction.response.send_message(embed=embed_bypass_loading())
    t0 = time.time()
    result, error = await bypass_url(url)
    elapsed = time.time() - t0
    if result:
        await interaction.edit_original_response(
            embed=embed_bypass_success(result, elapsed, url, interaction.user),
            view=BypassView(result, elapsed))
        # Add to history
        history.append({
            "url": url,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": interaction.user.id
        })
        if len(history) > 100:
            history.pop(0)
        save_json(HISTORY_FILE, history)
    else:
        await interaction.edit_original_response(
            embed=embed_bypass_fail(error, url, elapsed, interaction.user),
            view=FailView(elapsed))

@bot.tree.command(name="setautobypass", description="Enable/disable auto-bypass in this channel")
@app_commands.describe(time="Auto-delete time in seconds (default 120)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction, time: int = 120):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        del autobypass_channels[cid]
        save_json(AUTOBYPASS_FILE, autobypass_channels)
        e = discord.Embed(
            description=f"{Emojis.No} Auto-bypass **disabled** in {interaction.channel.mention}.",
            color=Colors.RED)
    else:
        autobypass_channels[cid] = {"auto_delete_time": time}
        save_json(AUTOBYPASS_FILE, autobypass_channels)
        e = discord.Embed(
            description=(f"{Emojis.GreenCheckmark} Auto-bypass **enabled** in {interaction.channel.mention}.\n"
                         f"{Emojis.Time} Auto-delete bot messages after {time} seconds."),
            color=Colors.GREEN)
    e.set_author(name=BOT_NAME, icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ae(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{Emojis.Warning} You need **Administrator** permission.", ephemeral=True)

@bot.tree.command(name="setupbypass", description="Configure auto-bypass channel with deletion settings")
@app_commands.describe(channel="Channel to enable auto-bypass", time="Auto-delete time in seconds (default 120)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setupbypass(interaction: discord.Interaction, channel: discord.TextChannel, time: int = 120):
    if channel.id in autobypass_channels:
        # Update settings
        autobypass_channels[channel.id]["auto_delete_time"] = time
        save_json(AUTOBYPASS_FILE, autobypass_channels)
        e = discord.Embed(
            description=f"{Emojis.Settings} Auto-bypass settings updated for {channel.mention}.",
            color=Colors.BLUE)
    else:
        autobypass_channels[channel.id] = {"auto_delete_time": time}
        save_json(AUTOBYPASS_FILE, autobypass_channels)
        e = discord.Embed(
            description=(f"{Emojis.GreenCheckmark} Auto-bypass **enabled** in {channel.mention}.\n"
                         f"{Emojis.Time} Auto-delete bot messages after {time} seconds.\n"
                         f"{Emojis.Warning} All messages in this channel will be deleted."),
            color=Colors.GREEN)
    e.set_author(name=BOT_NAME, icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setupbypass.error
async def _sbe(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{Emojis.Warning} You need **Administrator** permission.", ephemeral=True)

@bot.tree.command(name="supported", description="Show support server and invite links")
async def cmd_supported(interaction: discord.Interaction):
    e = discord.Embed(color=Colors.GOLD, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.Support} KING BOT • Support", icon_url=URL_CROWN)
    e.add_field(name="Support Server", value=f"[Click here]({SUPPORT_SERVER_URL})", inline=False)
    e.add_field(name="Invite Me", value=f"[Click here]({BOT_INVITE_URL})", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="status", description="Show bot status and statistics")
async def cmd_status(interaction: discord.Interaction):
    e = discord.Embed(color=Colors.INFO, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.Online} KING BOT • Status", icon_url=URL_CROWN)
    e.add_field(name="Uptime", value=f"```{_uptime()}```", inline=True)
    e.add_field(name="Ping", value=f"```{round(bot.latency*1000)}ms```", inline=True)
    e.add_field(name="Servers", value=f"```{len(bot.guilds)}```", inline=True)
    e.add_field(name="Users", value=f"```{sum(g.member_count for g in bot.guilds)}```", inline=True)
    e.add_field(name="Version", value=f"```{BOT_VERSION}```", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="history", description="Show last 5 bypass results")
async def cmd_history(interaction: discord.Interaction):
    if not history:
        e = discord.Embed(description="No bypass history yet.", color=Colors.WARN)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e, ephemeral=True)
        return
    e = discord.Embed(color=Colors.INFO, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{Emojis.Clipboard} KING BOT • History", icon_url=URL_CROWN)
    for i, entry in enumerate(reversed(history[-5:])):
        e.add_field(
            name=f"#{i+1}",
            value=f"URL: `{entry['url'][:50]}...`\nResult: `{entry['result'][:80]}...`",
            inline=False
        )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── MODERATION COMMANDS ────────────────────────────────────────
@bot.tree.command(name="ban", description="Ban a user")
@app_commands.describe(user="User to ban", reason="Reason")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    await user.ban(reason=reason)
    e = discord.Embed(
        description=f"{Emojis.No} {user.mention} has been banned.\nReason: {reason}",
        color=Colors.RED
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="unban", description="Unban a user")
@app_commands.describe(user_id="User ID to unban")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await interaction.guild.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        e = discord.Embed(
            description=f"{Emojis.GreenCheckmark} {user.mention} has been unbanned.",
            color=Colors.GREEN
        )
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except:
        e = discord.Embed(
            description=f"{Emojis.Error} User not found or not banned.",
            color=Colors.RED
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="kick", description="Kick a user")
@app_commands.describe(user="User to kick", reason="Reason")
@app_commands.checks.has_permissions(kick_members=True)
async def cmd_kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    await user.kick(reason=reason)
    e = discord.Embed(
        description=f"{Emojis.No} {user.mention} has been kicked.\nReason: {reason}",
        color=Colors.RED
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="timeout", description="Timeout a user")
@app_commands.describe(user="User to timeout", duration="Duration in minutes", reason="Reason")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_timeout(interaction: discord.Interaction, user: discord.Member, duration: int, reason: str = "No reason"):
    if duration < 1 or duration > 40320:
        await interaction.response.send_message("Duration must be between 1 and 40320 minutes.", ephemeral=True)
        return
    await user.timeout(timedelta(minutes=duration), reason=reason)
    e = discord.Embed(
        description=f"{Emojis.Warning} {user.mention} has been timed out for {duration} minutes.\nReason: {reason}",
        color=Colors.WARN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="untimeout", description="Remove timeout from a user")
@app_commands.describe(user="User to remove timeout")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_untimeout(interaction: discord.Interaction, user: discord.Member):
    await user.timeout(None)
    e = discord.Embed(
        description=f"{Emojis.GreenCheckmark} Timeout removed from {user.mention}.",
        color=Colors.GREEN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.describe(user="User to warn", reason="Reason")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    guild_id = interaction.guild.id
    if guild_id not in warnings:
        warnings[guild_id] = []
    warnings[guild_id].append({
        "user_id": user.id,
        "reason": reason,
        "moderator": interaction.user.id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    save_json(WARNINGS_FILE, warnings)
    e = discord.Embed(
        description=f"{Emojis.Warning} {user.mention} has been warned.\nReason: {reason}",
        color=Colors.WARN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="clear", description="Clear messages in the channel")
@app_commands.describe(amount="Number of messages to clear (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("Amount must be between 1 and 100.", ephemeral=True)
        return
    await interaction.channel.purge(limit=amount)
    e = discord.Embed(
        description=f"{Emojis.Trash} Cleared {amount} messages.",
        color=Colors.GREEN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="lock", description="Lock a channel (disable sending messages)")
@app_commands.describe(channel="Channel to lock (default current)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role, send_messages=False)
    e = discord.Embed(
        description=f"{Emojis.lock} Channel {channel.mention} has been locked.",
        color=Colors.RED
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="unlock", description="Unlock a channel")
@app_commands.describe(channel="Channel to unlock (default current)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role, send_messages=None)
    e = discord.Embed(
        description=f"{Emojis.Unlock} Channel {channel.mention} has been unlocked.",
        color=Colors.GREEN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── TICKETS ──────────────────────────────────────────────────────
@bot.tree.command(name="ticket", description="Create a new ticket")
@app_commands.describe(reason="Reason for the ticket")
async def cmd_ticket(interaction: discord.Interaction, reason: str = None):
    channel = await create_ticket(interaction.guild, interaction.user, reason)
    if channel:
        e = discord.Embed(
            description=f"{Emojis.Ticket} Ticket created: {channel.mention}",
            color=Colors.GREEN
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="close", description="Close the current ticket")
async def cmd_close(interaction: discord.Interaction):
    if "ticket" not in interaction.channel.name:
        await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        return
    await interaction.response.send_message("Closing ticket...", ephemeral=True)
    await asyncio.sleep(2)
    await interaction.channel.delete()

@bot.tree.command(name="claim", description="Claim the current ticket")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_claim(interaction: discord.Interaction):
    if "ticket" not in interaction.channel.name:
        await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        return
    await interaction.response.send_message(f"{Emojis.Admin} Ticket claimed by {interaction.user.mention}")

@bot.tree.command(name="transcript", description="Generate a transcript of the ticket")
async def cmd_transcript(interaction: discord.Interaction):
    if "ticket" not in interaction.channel.name:
        await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        return
    # Simple transcript: get last 100 messages
    messages = []
    async for msg in interaction.channel.history(limit=100):
        messages.append(f"{msg.author}: {msg.content}")
    transcript = "\n".join(reversed(messages))
    await interaction.response.send_message(f"```\n{transcript[:1900]}\n```", ephemeral=True)

@bot.tree.command(name="panel", description="Show ticket panel (for admins)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_panel(interaction: discord.Interaction):
    e = discord.Embed(
        title="🎫 Ticket Panel",
        description="Click the button below to open a ticket.",
        color=Colors.BLUE
    )
    view = View()
    view.add_item(Button(label="Open Ticket", style=discord.ButtonStyle.success, custom_id="open_ticket"))
    await interaction.response.send_message(embed=e, view=view)

# ── GIVEAWAYS ────────────────────────────────────────────────────
@bot.tree.command(name="gstart", description="Start a giveaway")
@app_commands.describe(duration="Duration (e.g., 1h, 2d, 30m)", prize="Prize to win", winners="Number of winners")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_gstart(interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
    # Parse duration
    time_map = {"d": 86400, "h": 3600, "m": 60}
    total_seconds = 0
    for unit, seconds in time_map.items():
        if unit in duration:
            parts = duration.split(unit)
            if parts[0].isdigit():
                total_seconds += int(parts[0]) * seconds
    if total_seconds == 0:
        await interaction.response.send_message("Invalid duration format. Use e.g., 1h, 2d, 30m.", ephemeral=True)
        return
    end_time = datetime.now(timezone.utc) + timedelta(seconds=total_seconds)
    giveaway_id = f"{interaction.guild.id}-{interaction.id}"
    giveaways[giveaway_id] = {
        "channel_id": interaction.channel.id,
        "prize": prize,
        "winners": winners,
        "entrants": [],
        "end_time": end_time.isoformat()
    }
    save_json(GIVEAWAYS_FILE, giveaways)
    e = discord.Embed(
        title="🎉 Giveaway Started!",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=Colors.GOLD
    )
    e.set_footer(text=f"React with 🎉 to enter! • {_footer()}")
    msg = await interaction.response.send_message(embed=e)
    await msg.add_reaction("🎉")
    # Schedule end
    asyncio.create_task(bot.giveaway_manager.end_giveaway(giveaway_id))

@bot.tree.command(name="gend", description="End a giveaway early")
@app_commands.describe(giveaway_id="ID of the giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_gend(interaction: discord.Interaction, giveaway_id: str):
    if giveaway_id not in giveaways:
        await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        return
    await bot.giveaway_manager.end_giveaway(giveaway_id)
    await interaction.response.send_message("Giveaway ended.", ephemeral=True)

@bot.tree.command(name="greroll", description="Reroll winners of a giveaway")
@app_commands.describe(giveaway_id="ID of the giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_greroll(interaction: discord.Interaction, giveaway_id: str):
    if giveaway_id not in giveaways:
        await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        return
    gw = giveaways[giveaway_id]
    entrants = gw.get("entrants", [])
    if not entrants:
        await interaction.response.send_message("No entrants.", ephemeral=True)
        return
    new_winners = random.sample(entrants, min(gw["winners"], len(entrants)))
    winner_mentions = ", ".join(f"<@{w}>" for w in new_winners)
    await interaction.response.send_message(f"New winners: {winner_mentions}")
    # Optionally update entrants? Not needed.

# ── LEVELS ──────────────────────────────────────────────────────
@bot.tree.command(name="rank", description="Show your rank")
@app_commands.describe(user="User to check (default you)")
async def cmd_rank(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    guild_id = interaction.guild.id
    if guild_id not in levels or user.id not in levels[guild_id]:
        xp = 0
    else:
        xp = levels[guild_id][user.id]
    level = get_level(xp)
    next_xp = get_xp_for_level(level + 1)
    e = discord.Embed(
        title=f"{Emojis.Star} Rank of {user.display_name}",
        color=Colors.BLUE
    )
    e.add_field(name="Level", value=str(level), inline=True)
    e.add_field(name="XP", value=f"{xp}/{next_xp}", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="leaderboard", description="Show server leaderboard")
async def cmd_leaderboard(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id not in levels:
        await interaction.response.send_message("No levels yet.", ephemeral=True)
        return
    sorted_users = sorted(levels[guild_id].items(), key=lambda x: x[1], reverse=True)[:10]
    lines = []
    for i, (user_id, xp) in enumerate(sorted_users, start=1):
        user = interaction.guild.get_member(user_id)
        name = user.display_name if user else f"Unknown ({user_id})"
        lines.append(f"{i}. {name} — Level {get_level(xp)} ({xp} XP)")
    e = discord.Embed(
        title=f"{Emojis.Crown} Server Leaderboard",
        description="\n".join(lines),
        color=Colors.GOLD
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="level", description="Show level of a user")
@app_commands.describe(user="User to check (default you)")
async def cmd_level(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    guild_id = interaction.guild.id
    if guild_id not in levels or user.id not in levels[guild_id]:
        xp = 0
    else:
        xp = levels[guild_id][user.id]
    level = get_level(xp)
    e = discord.Embed(
        description=f"{Emojis.Star} {user.mention} is level **{level}** with **{xp}** XP.",
        color=Colors.BLUE
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="addxp", description="Add XP to a user (Admin)")
@app_commands.describe(user="User to add XP", amount="Amount of XP to add")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_addxp(interaction: discord.Interaction, user: discord.Member, amount: int):
    await add_xp(interaction.guild.id, user.id, amount)
    e = discord.Embed(
        description=f"{Emojis.Plus} Added **{amount}** XP to {user.mention}.",
        color=Colors.GREEN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="addlevel", description="Add a level to a user (Admin)")
@app_commands.describe(user="User to add level", amount="Number of levels to add")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_addlevel(interaction: discord.Interaction, user: discord.Member, amount: int):
    guild_id = interaction.guild.id
    if guild_id not in levels or user.id not in levels[guild_id]:
        current_xp = 0
    else:
        current_xp = levels[guild_id][user.id]
    current_level = get_level(current_xp)
    new_level = current_level + amount
    new_xp = get_xp_for_level(new_level)
    await add_xp(guild_id, user.id, new_xp - current_xp)  # add enough XP to reach new level
    e = discord.Embed(
        description=f"{Emojis.Plus} Added **{amount}** levels to {user.mention} (now level {new_level}).",
        color=Colors.GREEN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── UTILITY COMMANDS ────────────────────────────────────────────
@bot.tree.command(name="uptime", description="Show bot uptime")
async def cmd_uptime(interaction: discord.Interaction):
    e = discord.Embed(
        description=f"Bot has been online for: **{_uptime()}**",
        color=Colors.INFO
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ping", description="Check bot latency")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(
        description=f"{Emojis.RedArrow} Ping: **{ms}ms**\nUptime: **{_uptime()}**",
        color=Colors.RED
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="help", description="Show all commands")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(
        title=f"{Emojis.Crown} KING BOT Help",
        color=Colors.GOLD,
        timestamp=datetime.now(timezone.utc)
    )
    e.set_thumbnail(url=URL_CROWN)
    e.add_field(
        name="🔗 Bypass",
        value="`/bypass` – Bypass a URL\n`/setautobypass` – Auto-bypass in channel\n`/setupbypass` – Detailed setup\n`/supported` – Support links\n`/status` – Bot status\n`/history` – Bypass history",
        inline=False
    )
    e.add_field(
        name="🛡️ Moderation",
        value="`/ban` `/unban` `/kick` `/timeout` `/untimeout` `/warn` `/clear` `/lock` `/unlock`",
        inline=False
    )
    e.add_field(
        name="🎫 Tickets",
        value="`/ticket` `/close` `/claim` `/transcript` `/panel`",
        inline=False
    )
    e.add_field(
        name="🎉 Giveaways",
        value="`/gstart` `/gend` `/greroll`",
        inline=False
    )
    e.add_field(
        name="📊 Levels",
        value="`/rank` `/leaderboard` `/level` `/addxp` `/addlevel`",
        inline=False
    )
    e.add_field(
        name="🤖 Utility",
        value="`/uptime` `/ping` `/help` `/banner` `/avatar` `/userinfo` `/serverinfo`",
        inline=False
    )
    e.add_field(
        name="⚙️ Config",
        value="`/backup` (coming soon)",
        inline=False
    )
    e.add_field(
        name="😂 Fun",
        value="`/coinflip` `/8ball` `/meme` `/hack` `/say` `/poll` `/rate` `/dice`",
        inline=False
    )
    e.add_field(
        name="📌 Extras",
        value="`/afk` `/remind` `/embed` `/reactionrole` `/boostinfo` `/report` `/suggest` `/announce` `/setupexecutor` `/executorstatus`",
        inline=False
    )
    e.set_footer(text=_footer())
    view = View()
    view.add_item(Button(label="Support Server", emoji="💬", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
    view.add_item(Button(label="Invite Me", emoji="🤖", url=BOT_INVITE_URL, style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=e, view=view)

@bot.tree.command(name="banner", description="Show user's banner")
@app_commands.describe(user="User to check (default you)")
async def cmd_banner(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    banner = user.banner
    if banner:
        e = discord.Embed(title=f"{user.display_name}'s Banner", color=Colors.INFO)
        e.set_image(url=banner.url)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    else:
        await interaction.response.send_message("User has no banner.", ephemeral=True)

@bot.tree.command(name="avatar", description="Show user's avatar")
@app_commands.describe(user="User to check (default you)")
async def cmd_avatar(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    e = discord.Embed(title=f"{user.display_name}'s Avatar", color=Colors.INFO)
    e.set_image(url=user.display_avatar.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="userinfo", description="Show user information")
@app_commands.describe(user="User to check (default you)")
async def cmd_userinfo(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    e = discord.Embed(color=Colors.INFO, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
    e.add_field(name="ID", value=user.id, inline=True)
    e.add_field(name="Joined Server", value=user.joined_at.strftime("%Y-%m-%d %H:%M:%S") if user.joined_at else "Unknown", inline=True)
    e.add_field(name="Joined Discord", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    e.add_field(name="Roles", value=", ".join([r.mention for r in user.roles if r != interaction.guild.default_role])[:100] or "None", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverinfo", description="Show server information")
async def cmd_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    e = discord.Embed(title=f"{Emojis.Members} {guild.name}", color=Colors.INFO, timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=guild.icon.url if guild.icon else None)
    e.add_field(name="Owner", value=guild.owner.mention, inline=True)
    e.add_field(name="Members", value=guild.member_count, inline=True)
    e.add_field(name="Channels", value=len(guild.channels), inline=True)
    e.add_field(name="Roles", value=len(guild.roles), inline=True)
    e.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
    e.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── CONFIGURATION ───────────────────────────────────────────────
@bot.tree.command(name="backup", description="Backup server settings (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_backup(interaction: discord.Interaction):
    # Placeholder - could export roles, channels, etc.
    await interaction.response.send_message("Backup feature coming soon.", ephemeral=True)

# ── FUN COMMANDS ────────────────────────────────────────────────
@bot.tree.command(name="coinflip", description="Flip a coin")
async def cmd_coinflip(interaction: discord.Interaction):
    result = random.choice(["🦅 Heads", "🔵 Tails"])
    e = discord.Embed(
        description=f"{Emojis.Coin} You got **{result}**!",
        color=Colors.GOLD
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="8ball", description="Ask the magic 8-ball")
@app_commands.describe(question="Your question")
async def cmd_8ball(interaction: discord.Interaction, question: str):
    responses = [
        "Yes, definitely.", "Without a doubt.", "You can count on it.",
        "As I see it, yes.", "Most likely.", "Outlook good.",
        "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
        "Better not tell you now.", "Cannot predict now.", "Don't count on it.",
        "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."
    ]
    answer = random.choice(responses)
    e = discord.Embed(
        title=f"{Emojis.Diamond} Magic 8-Ball",
        description=f"**Question:** {question}\n**Answer:** {answer}",
        color=Colors.PURPLE
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="meme", description="Get a random meme")
async def cmd_meme(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as resp:
            if resp.status == 200:
                data = await resp.json()
                e = discord.Embed(title=data["title"], color=Colors.INFO)
                e.set_image(url=data["url"])
                e.set_footer(text=f"From r/{data['subreddit']} • {_footer()}")
                await interaction.response.send_message(embed=e)
            else:
                await interaction.response.send_message("Failed to fetch meme.", ephemeral=True)

@bot.tree.command(name="hack", description="Fake hack a user (fun)")
@app_commands.describe(user="User to hack")
async def cmd_hack(interaction: discord.Interaction, user: discord.Member):
    fake_hack = [
        f"Accessing {user.name}'s data...",
        f"Bypassing firewall...",
        f"Extracting Discord token...",
        f"Reading DMs...",
        f"Downloading profile picture...",
        f"Deleting system32... (just kidding)",
        f"Hack complete! {user.name} has been pwned!"
    ]
    msg = await interaction.response.send_message("```\n" + "\n".join(fake_hack) + "\n```")
    for line in fake_hack:
        await asyncio.sleep(1)
        # Could edit message but we'll just send as separate messages
    await interaction.followup.send("✅ Hack finished!")

@bot.tree.command(name="say", description="Make the bot say something")
@app_commands.describe(message="Message to say")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("✅ Sent.", ephemeral=True)
    await interaction.channel.send(message[:2000])

@bot.tree.command(name="poll", description="Create a poll")
@app_commands.describe(question="Poll question", options="Comma-separated options (max 10)")
async def cmd_poll(interaction: discord.Interaction, question: str, options: str):
    opts = [opt.strip() for opt in options.split(",") if opt.strip()]
    if len(opts) < 2 or len(opts) > 10:
        await interaction.response.send_message("Please provide 2-10 options.", ephemeral=True)
        return
    e = discord.Embed(title=f"📊 {question}", color=Colors.BLUE)
    for i, opt in enumerate(opts):
        emoji = chr(0x1F1E6 + i) if i < 26 else "🔢"
        e.add_field(name=f"{emoji} {opt}", value="", inline=False)
    e.set_footer(text="React with the corresponding emoji to vote!")
    view = PollView(opts)
    await interaction.response.send_message(embed=e, view=view)

@bot.tree.command(name="rate", description="Rate something")
@app_commands.describe(thing="What to rate")
async def cmd_rate(interaction: discord.Interaction, thing: str):
    rating = random.randint(1, 10)
    stars = "⭐" * rating
    e = discord.Embed(
        description=f"I rate **{thing}** {rating}/10\n{stars}",
        color=Colors.GOLD
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="dice", description="Roll a dice")
@app_commands.describe(sides="Number of sides (default 6)")
async def cmd_dice(interaction: discord.Interaction, sides: int = 6):
    if sides < 1 or sides > 100:
        await interaction.response.send_message("Sides must be between 1 and 100.", ephemeral=True)
        return
    result = random.randint(1, sides)
    e = discord.Embed(
        description=f"🎲 You rolled **{result}** (1-{sides})",
        color=Colors.INFO
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── EXTRAS ──────────────────────────────────────────────────────
@bot.tree.command(name="afk", description="Set AFK status")
@app_commands.describe(reason="Reason for being AFK")
async def cmd_afk(interaction: discord.Interaction, reason: str = "AFK"):
    afk_status[interaction.guild.id] = {interaction.user.id: reason}
    save_json(AFK_FILE, afk_status)
    e = discord.Embed(
        description=f"{Emojis.Alarm} {interaction.user.mention} is now AFK: {reason}",
        color=Colors.WARN
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="remind", description="Set a reminder")
@app_commands.describe(time="Time (e.g., 5m, 1h)", reminder="Reminder message")
async def cmd_remind(interaction: discord.Interaction, time: str, reminder: str):
    # Parse time
    time_map = {"d": 86400, "h": 3600, "m": 60}
    total_seconds = 0
    for unit, seconds in time_map.items():
        if unit in time:
            parts = time.split(unit)
            if parts[0].isdigit():
                total_seconds += int(parts[0]) * seconds
    if total_seconds == 0:
        await interaction.response.send_message("Invalid time format. Use e.g., 5m, 1h.", ephemeral=True)
        return
    remind_time = datetime.now(timezone.utc) + timedelta(seconds=total_seconds)
    reminders.append({
        "user_id": interaction.user.id,
        "channel_id": interaction.channel.id,
        "remind_time": remind_time.isoformat(),
        "message": reminder
    })
    save_json(REMINDERS_FILE, reminders)
    e = discord.Embed(
        description=f"{Emojis.clock} Reminder set for {time} from now.\n{reminder}",
        color=Colors.INFO
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="embed", description="Create a custom embed (Admin)")
@app_commands.describe(title="Embed title", description="Embed description", color="Hex color (e.g., FF0000)", footer="Footer text")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_embed(interaction: discord.Interaction, title: str, description: str, color: str = "FF0000", footer: str = None):
    try:
        color_int = int(color.lstrip("#"), 16)
    except:
        color_int = Colors.RED
    e = discord.Embed(title=title, description=description, color=color_int)
    if footer:
        e.set_footer(text=footer)
    else:
        e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="reactionrole", description="Setup reaction roles (Admin)")
@app_commands.describe(message_id="Message ID to attach", roles="Comma-separated role IDs and emojis (e.g., :emoji: role_id)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reactionrole(interaction: discord.Interaction, message_id: str, roles: str):
    # Parse roles: format "emoji1 role_id1, emoji2 role_id2"
    pairs = roles.split(",")
    role_map = {}
    for pair in pairs:
        parts = pair.strip().split(" ")
        if len(parts) == 2:
            emoji = parts[0]
            role_id = int(parts[1])
            role_map[emoji] = role_id
    # We'll store in reaction_roles
    reaction_roles[message_id] = role_map
    save_json(REACTION_ROLES_FILE, reaction_roles)
    e = discord.Embed(
        description=f"{Emojis.GreenCheckmark} Reaction roles set for message {message_id}.",
        color=Colors.GREEN
    )
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="boostinfo", description="Show server boost info")
async def cmd_boostinfo(interaction: discord.Interaction):
    guild = interaction.guild
    boosts = guild.premium_subscription_count
    tier = guild.premium_tier
    e = discord.Embed(
        title=f"{Emojis.Nitro} Boost Info",
        description=f"**Boost Count:** {boosts}\n**Boost Tier:** {tier}",
        color=Colors.GOLD
    )
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="report", description="Report a user")
@app_commands.describe(user="User to report", reason="Reason")
async def cmd_report(interaction: discord.Interaction, user: discord.Member, reason: str):
    # Send to a report channel (if exists)
    report_channel = discord.utils.get(interaction.guild.text_channels, name="reports")
    if report_channel:
        e = discord.Embed(
            title="Report",
            description=f"**Reported:** {user.mention}\n**Reporter:** {interaction.user.mention}\n**Reason:** {reason}",
            color=Colors.RED
        )
        await report_channel.send(embed=e)
        await interaction.response.send_message("Report sent.", ephemeral=True)
    else:
        await interaction.response.send_message("No reports channel found.", ephemeral=True)

@bot.tree.command(name="suggest", description="Make a suggestion")
@app_commands.describe(suggestion="Your suggestion")
async def cmd_suggest(interaction: discord.Interaction, suggestion: str):
    suggestions_channel = discord.utils.get(interaction.guild.text_channels, name="suggestions")
    if suggestions_channel:
        e = discord.Embed(
            title="Suggestion",
            description=f"{suggestion}",
            color=Colors.BLUE
        )
        e.set_footer(text=f"From {interaction.user.display_name}")
        msg = await suggestions_channel.send(embed=e)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await interaction.response.send_message("Suggestion submitted.", ephemeral=True)
    else:
        await interaction.response.send_message("No suggestions channel found.", ephemeral=True)

@bot.tree.command(name="announce", description="Make an announcement (Admin)")
@app_commands.describe(channel="Channel to announce", message="Announcement message", ping="@everyone?")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str, ping: bool = False):
    e = discord.Embed(
        title="📢 Announcement",
        description=message,
        color=Colors.GOLD,
        timestamp=datetime.now(timezone.utc)
    )
    e.set_footer(text=_footer())
    content = "@everyone" if ping else ""
    await channel.send(content=content, embed=e)
    await interaction.response.send_message(f"Announcement sent to {channel.mention}.", ephemeral=True)

# ── EXECUTOR COMMANDS ──────────────────────────────────────────
@bot.tree.command(name="setupexecutor", description="Set a channel for executor status updates")
@app_commands.describe(channel="Channel to send updates")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setupexecutor(interaction: discord.Interaction, channel: discord.TextChannel):
    if channel.id in executor_channels:
        executor_channels.remove(channel.id)
        save_json(EXECUTOR_CHANNELS_FILE, list(executor_channels))
        e = discord.Embed(
            description=f"{Emojis.No} Executor updates disabled in {channel.mention}.",
            color=Colors.RED
        )
    else:
        executor_channels.add(channel.id)
        save_json(EXECUTOR_CHANNELS_FILE, list(executor_channels))
        e = discord.Embed(
            description=f"{Emojis.GreenCheckmark} Executor updates enabled in {channel.mention}.",
            color=Colors.GREEN
        )
    e.set_author(name=BOT_NAME, icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="executorstatus", description="Check executor status")
async def cmd_executorstatus(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await fetch_executor_status()
    embed = embed_executor_status(data)
    await interaction.followup.send(embed=embed)

# ── SETUP IA ─────────────────────────────────────────────────────
@bot.tree.command(name="setupia", description="Enable/disable AI auto-response in a channel")
@app_commands.describe(channel="Channel to enable AI responses")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setupia(interaction: discord.Interaction, channel: discord.TextChannel):
    if channel.id in ai_channels:
        ai_channels.remove(channel.id)
        save_json(AI_CHANNELS_FILE, list(ai_channels))
        e = discord.Embed(
            description=f"{Emojis.No} AI auto-response disabled in {channel.mention}.",
            color=Colors.RED
        )
    else:
        ai_channels.add(channel.id)
        save_json(AI_CHANNELS_FILE, list(ai_channels))
        e = discord.Embed(
            description=f"{Emojis.Robot} AI auto-response **enabled** in {channel.mention}.\nThe bot will reply with AI-generated responses.",
            color=Colors.GREEN
        )
    e.set_author(name=BOT_NAME, icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

# ── HEALTH SERVER ──────────────────────────────────────────────
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
    logger.info(f"🌐 Health server on :{PORT}")

# ── REMINDER TASK ─────────────────────────────────────────────
@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.now(timezone.utc)
    for rem in reminders[:]:
        remind_time = datetime.fromisoformat(rem["remind_time"])
        if now >= remind_time:
            channel = bot.get_channel(rem["channel_id"])
            if channel:
                await channel.send(f"<@{rem['user_id']}> Reminder: {rem['message']}")
            reminders.remove(rem)
            save_json(REMINDERS_FILE, reminders)

# ── MAIN ──────────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN not found.")
        return
    start_web()
    check_reminders.start()
    logger.info(f"🚀 Starting {BOT_NAME}...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
