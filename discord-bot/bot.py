import os
import re
import json
import time
import random
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
import requests
import aiohttp
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

# ── CONFIGURATION ────────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525629900038475969")

VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"

# Reaction-GIF endpoint (public, no API key) — used by /hug, /kiss, etc.
GIF_API_BASE = "https://nekos.best/api/v2"

# Keyword GIF search endpoint — used by /gif <query>
# NOTE: move KLIPY_API_KEY to an environment variable in production
# instead of leaving it hardcoded in the source.
KLIPY_SEARCH_URL = "https://api.klipy.com/v1/search"
KLIPY_API_KEY = os.environ.get("KLIPY_API_KEY", "XApPsk3XcfRBDT3wR6w8tlTekq0yOEGGcGXtGxeHS1y67owatVyhhUhiIosrHfxJ")

# ── CUSTOM EMOJIS (NO UNICODE, EXCEPT 📱) ──────────────────────
# Normal format: <:Name:ID>
# Animated format: <a:Name:ID>

EMOJI_GREEN_DOT = "<a:fmd_green_dot:1526742445323190272>"
EMOJI_LOADER    = "<a:fmd_loader:1526741970226253834>"
EMOJI_CROWN     = "<a:fmd_crown:1526742765311098980>"
EMOJI_KEY       = "<:fmd_key:1526743159038803978>"
EMOJI_CLOCK     = "<a:fmd_clock:1525380296852377711>"
EMOJI_SUCCESS   = "<:fmd_success:1526742163050991616>"

# Button emojis
EMOJI_COPY_OBJ    = discord.PartialEmoji(name="fmd_copy", id=1526743644894138479)
EMOJI_DISCORD_OBJ = discord.PartialEmoji(name="fmd_discord", id=1526743527642501273)
EMOJI_INVITE_OBJ  = discord.PartialEmoji(name="fmd_invite", id=1526743390488756236)
EMOJI_PC_OBJ      = discord.PartialEmoji(name="fmd_pc", id=1526858555544572035)

# ── COLORS ───────────────────────────────────────────────────────
C_GREEN  = 0x00FF66  # Neon Green Premium
C_WARN   = 0xFFA500  # Orange
C_ERROR  = 0xED4245  # Red

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
            return "📱"  # Explicitly allowed exception for mobile
        else:
            return "PC"
    except Exception:
        return "PC"

def _e(title: str, description: str = "", color: int = C_GREEN) -> discord.Embed:
    """Reusable base embed for every new command."""
    e = discord.Embed(
        title=f"{EMOJI_GREEN_DOT} {title}",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text=_footer())
    return e

async def _send_error(interaction: discord.Interaction, description: str, ephemeral: bool = True):
    e = _e("Error", description, C_ERROR)
    if interaction.response.is_done():
        await interaction.followup.send(embed=e, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=e, ephemeral=ephemeral)

# ── BYPASS ENGINE (Robust) ──────────────────────────────────────
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
    last_error = "Unknown error"
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
                last_error = "Invalid API response"
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
                last_error = str(err_msg or "The API reported an error.")
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            return None, "No result found in the API."

        except requests.exceptions.Timeout:
            last_error = f"Request timed out ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
        except Exception as e:
            last_error = str(e)[:100]
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)

    return None, last_error

# ── JSON FILES (Auto-Bypass: stores a set of IDs) ────────────────
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

# ── JSON FILES (General data: economy, levels, etc.) ─────────────
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_data(name: str, default=None):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}

def save_data(name: str, data):
    path = os.path.join(DATA_DIR, f"{name}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"save_data: {e}")

economy_data   = load_data("economy", {})
levels_data    = load_data("levels", {})
warnings_data  = load_data("warnings", {})
giveaways_data = load_data("giveaways", {})
configs_data   = load_data("configs", {})


def get_eco(uid) -> dict:
    uid = str(uid)
    if uid not in economy_data:
        economy_data[uid] = {"bal": 100, "daily": 0, "work": 0, "rob": 0}
    return economy_data[uid]


def get_level(gid, uid) -> dict:
    gid, uid = str(gid), str(uid)
    levels_data.setdefault(gid, {})
    if uid not in levels_data[gid]:
        levels_data[gid][uid] = {"xp": 0, "level": 0}
    return levels_data[gid][uid]


def get_config(gid) -> dict:
    gid = str(gid)
    if gid not in configs_data:
        configs_data[gid] = {"welcome_channel": None, "log_channel": None, "autorole": None, "prefix": "!"}
    return configs_data[gid]


def xp_needed(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100

# ── EMBEDS (Premium Green Design) ────────────────────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS")
    e.title = f"{EMOJI_LOADER} Generating Bypass..."
    e.description = "Processing your link...\nPlease wait..."
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif")  # Loader
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.description = "Generated successfully.\n\n🕒 Auto delete in 120s"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")  # Required crown

    e.add_field(name=f"{EMOJI_KEY} Result", value=f"```txt\n{result[:900]}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name=f"{EMOJI_SUCCESS} Status", value="`Successfully Generated`", inline=True)
    e.add_field(name="Platform", value=f"`{platform}`", inline=True)

    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Failed"
    e.description = "Something went wrong!"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")

    e.add_field(name="Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name="Platform", value=f"`{platform}`", inline=True)

    e.set_footer(text=_footer())
    return e

# ── VIEW (ONLY 3 BUTTONS) ────────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result

        self.add_item(Button(label="Discord", emoji=EMOJI_DISCORD_OBJ, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Invite", emoji=EMOJI_INVITE_OBJ, url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(emoji=EMOJI_COPY_OBJ, label="Copy", style=discord.ButtonStyle.success, row=0)
    async def copy_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"{EMOJI_SUCCESS} Copied Successfully!\n```txt\n{self._result[:1900]}\n```",
            ephemeral=True
        )

# ── LIVE COUNTDOWN AND AUTO-DELETE ───────────────────────────────
async def start_countdown(message: discord.Message, base_embed: discord.Embed, view: View, seconds: int = 120):
    clock_emoji = EMOJI_CLOCK
    while seconds > 0:
        try:
            new_embed = base_embed.copy()

            field_updated = False
            for i, field in enumerate(new_embed.fields):
                if field.name == f"{clock_emoji} Auto Delete":
                    new_embed.set_field_at(i, name=field.name, value=f"`{seconds}s` remaining", inline=field.inline)
                    field_updated = True
                    break

            if not field_updated:
                new_embed.add_field(name=f"{clock_emoji} Auto Delete", value=f"`{seconds}s` remaining", inline=False)

            await message.edit(embed=new_embed, view=view)
            await asyncio.sleep(1)
            seconds -= 1
        except (discord.NotFound, discord.HTTPException):
            break

    try:
        await message.delete()
    except Exception:
        pass

# ── BOT CLIENT ────────────────────────────────────────────────────
class FmdBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Global commands synced.")

    async def on_ready(self):
        logger.info("=========================================")
        logger.info(f"✅ {self.user.name} Online!")
        logger.info(f"📡 Servers: {len(self.guilds)}")
        logger.info(f"⚙️ Registered commands: {len(self.tree.get_commands())}")
        logger.info("=========================================")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # XP per message
        lvl = get_level(message.guild.id, message.author.id)
        lvl["xp"] += random.randint(5, 15)
        needed = xp_needed(lvl["level"])
        if lvl["xp"] >= needed:
            lvl["xp"] -= needed
            lvl["level"] += 1
            try:
                await message.channel.send(embed=_e("Level Up!", f"{message.author.mention} is now level **{lvl['level']}**"))
            except Exception:
                pass
        save_data("levels", levels_data)

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

# ══════════════════════════════════════════════════════════════
#  SLASH COMMANDS — BYPASS SYSTEM (DO NOT TOUCH)
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="bypass", description="🔓 Bypass a link and get the real destination")
@app_commands.describe(url="The link to bypass")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        e = discord.Embed(description="⚠️ Invalid URL. Make sure to include `http://` or `https://`.", color=C_WARN)
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
        logger.error(f"Error editing response: {e}")

@bot.tree.command(name="setautobypass", description="⚙️ [Admin] Enable/disable auto-bypass in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, autobypass_channels)
        e = discord.Embed(title="Auto-Bypass DISABLED", description=f"{interaction.channel.mention} will no longer auto-bypass links.", color=C_ERROR)
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, autobypass_channels)
        e = discord.Embed(title="Auto-Bypass ENABLED", description=f"Every link in {interaction.channel.mention} will be automatically bypassed.", color=C_GREEN)
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 You need Administrator permission!", ephemeral=True)

@bot.tree.command(name="ping", description="🏓 Check the bot's latency")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.add_field(name="Latency", value=f"`{ms}ms`", inline=True)
    e.add_field(name="Uptime", value=f"`{_uptime()}`", inline=True)
    e.add_field(name="Servers", value=f"`{len(bot.guilds)}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


def _perm_error_handler(cmd):
    @cmd.error
    async def _handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("🚫 You need Administrator permission!", ephemeral=True)
        else:
            await _send_error(interaction, f"```\n{str(error)[:200]}\n```")
    return _handler


# ══════════════════════════════════════════════════════════════
#  MODERATION
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="kick", description="👢 [Admin] Kick a member from the server")
@app_commands.describe(user="User to kick", reason="Reason for the kick")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if user.id == interaction.user.id:
        return await _send_error(interaction, "You can't kick yourself.")
    try:
        await user.kick(reason=reason)
        e = _e("Member Kicked")
        e.add_field(name="User", value=f"`{user}`", inline=True)
        e.add_field(name="Moderator", value=f"`{interaction.user}`", inline=True)
        e.add_field(name="Reason", value=f"`{reason}`", inline=False)
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await _send_error(interaction, "I don't have enough permissions to kick this user.")
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_kick)

@bot.tree.command(name="ban", description="🔨 [Admin] Ban a member from the server")
@app_commands.describe(user="User to ban", reason="Reason for the ban")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if user.id == interaction.user.id:
        return await _send_error(interaction, "You can't ban yourself.")
    try:
        await user.ban(reason=reason)
        e = _e("Member Banned")
        e.add_field(name="User", value=f"`{user}`", inline=True)
        e.add_field(name="Moderator", value=f"`{interaction.user}`", inline=True)
        e.add_field(name="Reason", value=f"`{reason}`", inline=False)
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await _send_error(interaction, "I don't have enough permissions to ban this user.")
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_ban)

@bot.tree.command(name="unban", description="🔓 [Admin] Unban a user by their ID")
@app_commands.describe(user_id="ID of the user to unban")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=_e("User Unbanned", f"`{user}` was unbanned."))
    except ValueError:
        await _send_error(interaction, "The provided ID is not valid.")
    except discord.NotFound:
        await _send_error(interaction, "That user is not banned.")
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_unban)

@bot.tree.command(name="softban", description="🔨 [Admin] Ban and unban to clean up a user's messages")
@app_commands.describe(user="User to softban", reason="Reason")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_softban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    try:
        await user.ban(reason=reason, delete_message_days=1)
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=_e("Softban Applied", f"`{user}` was softbanned (their recent messages were deleted)."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_softban)

@bot.tree.command(name="mute", description="🔇 [Admin] Mute a user (timeout)")
@app_commands.describe(user="User to mute", minutes="Duration in minutes")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_mute(interaction: discord.Interaction, user: discord.Member, minutes: int = 10):
    if minutes < 1 or minutes > 40320:
        return await _send_error(interaction, "Duration must be between `1` and `40320` minutes (28 days).")
    try:
        await user.timeout(discord.utils.utcnow() + timedelta(minutes=minutes), reason=f"Muted by {interaction.user}")
        await interaction.response.send_message(embed=_e("User Muted", f"{user.mention} was muted for `{minutes}` min."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_mute)

@bot.tree.command(name="unmute", description="🔊 [Admin] Remove a user's mute")
@app_commands.describe(user="User to unmute")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unmute(interaction: discord.Interaction, user: discord.Member):
    try:
        await user.timeout(None, reason=f"Unmuted by {interaction.user}")
        await interaction.response.send_message(embed=_e("Mute Removed", f"{user.mention} is no longer muted."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_unmute)

@bot.tree.command(name="warn", description="⚠️ [Admin] Warn a user")
@app_commands.describe(user="User to warn", reason="Reason for the warning")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_warn(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    gid, uid = str(interaction.guild_id), str(user.id)
    warnings_data.setdefault(gid, {}).setdefault(uid, [])
    warnings_data[gid][uid].append({"mod": str(interaction.user.id), "reason": reason, "ts": int(time.time())})
    save_data("warnings", warnings_data)
    await interaction.response.send_message(embed=_e("Warning Added", f"{user.mention} was warned.\nTotal: `{len(warnings_data[gid][uid])}`"))
_perm_error_handler(cmd_warn)

@bot.tree.command(name="unwarn", description="✅ [Admin] Remove a warning from a user")
@app_commands.describe(user="User", index="Warning number to remove (starts at 1)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unwarn(interaction: discord.Interaction, user: discord.Member, index: int = 1):
    gid, uid = str(interaction.guild_id), str(user.id)
    warns = warnings_data.get(gid, {}).get(uid, [])
    if not warns or len(warns) < index or index < 1:
        return await _send_error(interaction, "There's no warning at that index.")
    warns.pop(index - 1)
    save_data("warnings", warnings_data)
    await interaction.response.send_message(embed=_e("Warning Removed", f"Warning #{index} removed from {user.mention}."))
_perm_error_handler(cmd_unwarn)

@bot.tree.command(name="warnings", description="📋 View a user's warnings")
@app_commands.describe(user="User to check")
async def cmd_warnings(interaction: discord.Interaction, user: discord.Member):
    gid, uid = str(interaction.guild_id), str(user.id)
    warns = warnings_data.get(gid, {}).get(uid, [])
    if not warns:
        return await interaction.response.send_message(embed=_e("Warnings", f"{user.mention} has no warnings."))
    desc = "\n".join(f"`{i+1}.` {w['reason']} — <t:{w['ts']}:R>" for i, w in enumerate(warns))
    await interaction.response.send_message(embed=_e(f"Warnings for {user.display_name}", desc))

@bot.tree.command(name="clear", description="🧹 [Admin] Bulk delete messages")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_clear(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        return await interaction.response.send_message(embed=_e("Invalid Amount", "The amount must be between `1` and `100`.", C_WARN), ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=_e("Messages Deleted", f"`{len(deleted)}` messages were deleted from {interaction.channel.mention}."), ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(embed=_e("Permission Error", "I don't have enough permissions to delete messages.", C_ERROR), ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(embed=_e("Error", f"```\n{str(ex)[:200]}\n```", C_ERROR), ephemeral=True)
_perm_error_handler(cmd_clear)

@bot.tree.command(name="purgeuser", description="🧹 [Admin] Delete messages from a specific user")
@app_commands.describe(user="User whose messages will be deleted", amount="Number of messages to scan (max 200)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_purgeuser(interaction: discord.Interaction, user: discord.Member, amount: int = 50):
    amount = max(1, min(amount, 200))
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=amount, check=lambda m: m.author.id == user.id)
        await interaction.followup.send(embed=_e("Messages Deleted", f"`{len(deleted)}` messages were deleted from {user.mention}."), ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(embed=_e("Error", f"```\n{str(ex)[:200]}\n```", C_ERROR), ephemeral=True)
_perm_error_handler(cmd_purgeuser)

@bot.tree.command(name="lock", description="🔒 [Admin] Lock the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(embed=_e("Channel Locked", f"{interaction.channel.mention} was locked."))
_perm_error_handler(cmd_lock)

@bot.tree.command(name="unlock", description="🔓 [Admin] Unlock the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
    await interaction.response.send_message(embed=_e("Channel Unlocked", f"{interaction.channel.mention} was unlocked."))
_perm_error_handler(cmd_unlock)

@bot.tree.command(name="slowmode", description="🐌 [Admin] Set the channel's slowmode")
@app_commands.describe(seconds="Seconds between messages (0 to disable, max 21600)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_slowmode(interaction: discord.Interaction, seconds: int):
    seconds = max(0, min(seconds, 21600))
    await interaction.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await interaction.response.send_message(embed=_e("Slowmode Disabled", f"{interaction.channel.mention} no longer has slowmode."))
    else:
        await interaction.response.send_message(embed=_e("Slowmode Enabled", f"{interaction.channel.mention} now has a `{seconds}s` delay between messages."))
_perm_error_handler(cmd_slowmode)

@bot.tree.command(name="nickname", description="✏️ [Admin] Change a user's nickname")
@app_commands.describe(user="User", nickname="New nickname (leave empty to remove it)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_nickname(interaction: discord.Interaction, user: discord.Member, nickname: str = None):
    try:
        await user.edit(nick=nickname)
        desc = f"{user.mention}'s nickname was changed to `{nickname}`." if nickname else f"{user.mention}'s nickname was removed."
        await interaction.response.send_message(embed=_e("Nickname Updated", desc))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_nickname)


# ══════════════════════════════════════════════════════════════
#  FUN
# ══════════════════════════════════════════════════════════════

_8BALL_RESPONSES = [
    "Yes, definitely.", "It is certain.", "Without a doubt.", "Yes, you can rely on it.",
    "Most likely.", "Signs point to yes.", "Reply hazy, try again.",
    "Ask again later.", "Better not tell you now.", "Cannot predict now.",
    "Concentrate and ask again.", "Don't count on it.", "My reply is no.",
    "My sources say no.", "Very doubtful.",
]

@bot.tree.command(name="8ball", description="🎱 Ask the magic 8-ball a question")
@app_commands.describe(question="Your question for the magic 8-ball")
async def cmd_8ball(interaction: discord.Interaction, question: str):
    answer = random.choice(_8BALL_RESPONSES)
    e = _e("Magic 8-Ball")
    e.add_field(name="Question", value=f"`{question}`", inline=False)
    e.add_field(name="Answer", value=f"`{answer}`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="coinflip", description="🪙 Flip a coin")
async def cmd_coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])
    await interaction.response.send_message(embed=_e("Coin Flip", f"The coin landed on: `{result}`"))

@bot.tree.command(name="dice", description="🎲 Roll a die")
@app_commands.describe(sides="Number of sides on the die (default 6, max 100)")
async def cmd_dice(interaction: discord.Interaction, sides: int = 6):
    if sides < 2 or sides > 100:
        return await interaction.response.send_message(embed=_e("Invalid Value", "The die must have between `2` and `100` sides.", C_WARN), ephemeral=True)
    result = random.randint(1, sides)
    await interaction.response.send_message(embed=_e("Dice Roll", f"`{sides}`-sided die — Result: `{result}`"))

@bot.tree.command(name="rps", description="✊ Rock, paper or scissors against the bot")
@app_commands.describe(choice="Your choice")
@app_commands.choices(choice=[
    app_commands.Choice(name="Rock", value="rock"),
    app_commands.Choice(name="Paper", value="paper"),
    app_commands.Choice(name="Scissors", value="scissors"),
])
async def cmd_rps(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    options = ["rock", "paper", "scissors"]
    bot_choice = random.choice(options)
    user_choice = choice.value
    if user_choice == bot_choice:
        result, color = "Tie", C_WARN
    elif (user_choice, bot_choice) in [("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")]:
        result, color = "You won!", C_GREEN
    else:
        result, color = "You lost.", C_ERROR
    e = _e("Rock, Paper, Scissors", color=color)
    e.add_field(name="Your choice", value=f"`{user_choice}`", inline=True)
    e.add_field(name="Bot", value=f"`{bot_choice}`", inline=True)
    e.add_field(name="Result", value=f"`{result}`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ship", description="❤️ Calculate the compatibility between two people")
@app_commands.describe(user1="First person", user2="Second person")
async def cmd_ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    love = random.randint(0, 100)
    bar = "🟩" * (love // 10) + "⬛" * (10 - love // 10)
    e = _e("Love Calculator", f"{user1.mention} + {user2.mention}\n\n{bar}\n`{love}%`")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="choose", description="🎯 Randomly choose one option among several")
@app_commands.describe(options="Options separated by commas")
async def cmd_choose(interaction: discord.Interaction, options: str):
    options_list = [o.strip() for o in options.split(",") if o.strip()]
    if len(options_list) < 2:
        return await _send_error(interaction, "You need at least 2 options separated by commas.")
    chosen = random.choice(options_list)
    await interaction.response.send_message(embed=_e("Random Choice", f"Among: `{', '.join(options_list)}`\n\nI chose: **{chosen}**"))

@bot.tree.command(name="reverse", description="🔁 Reverse a text")
@app_commands.describe(text="Text to reverse")
async def cmd_reverse(interaction: discord.Interaction, text: str):
    await interaction.response.send_message(embed=_e("Reversed Text", f"`{text[::-1]}`"))

@bot.tree.command(name="say", description="📢 [Admin] Make the bot repeat a message")
@app_commands.describe(message="Message to send")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(embed=_e("Message Sent", "Done."), ephemeral=True)
    await interaction.channel.send(message)
_perm_error_handler(cmd_say)

@bot.tree.command(name="meme", description="😂 Random meme from Reddit")
async def cmd_meme(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        e = discord.Embed(title=f"{EMOJI_GREEN_DOT} {r['title'][:250]}", color=C_GREEN, timestamp=datetime.now(timezone.utc))
        e.set_image(url=r["url"])
        e.set_footer(text=f"r/{r['subreddit']} • {_footer()}")
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Couldn't fetch a meme right now.", C_ERROR))

@bot.tree.command(name="joke", description="😄 Random joke")
async def cmd_joke(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://v2.jokeapi.dev/joke/Any?safe-mode", timeout=10).json()
        txt = r["joke"] if r["type"] == "single" else f"{r['setup']}\n\n{r['delivery']}"
        await interaction.followup.send(embed=_e("Random Joke", txt))
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Couldn't fetch a joke right now.", C_ERROR))

@bot.tree.command(name="fact", description="🧠 Random fun fact")
async def cmd_fact(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=10).json()
        await interaction.followup.send(embed=_e("Fun Fact", r.get("text", "N/A")))
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Couldn't fetch a fun fact.", C_ERROR))


# ── REACTION-GIF COMMANDS (nekos.best — public, no API key) ─────
async def _send_gif_action(interaction: discord.Interaction, action: str, title: str, verb: str, user: discord.Member = None):
    await interaction.response.defer()
    gif_url = None
    try:
        r = requests.get(f"{GIF_API_BASE}/{action}", timeout=10).json()
        gif_url = r["results"][0]["url"]
    except Exception:
        pass
    desc = f"{interaction.user.mention} {verb} {user.mention}" if user else f"{interaction.user.mention} {verb}"
    e = _e(title, desc)
    if gif_url:
        e.set_image(url=gif_url)
    else:
        e.description += "\n\n⚠️ Couldn't load the GIF right now."
    await interaction.followup.send(embed=e)

@bot.tree.command(name="hug", description="🤗 Hug someone")
@app_commands.describe(user="Who to hug")
async def cmd_hug(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "hug", "Hug", "hugs", user)

@bot.tree.command(name="kiss", description="😘 Kiss someone")
@app_commands.describe(user="Who to kiss")
async def cmd_kiss(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "kiss", "Kiss", "kisses", user)

@bot.tree.command(name="pat", description="🖐️ Pat someone's head")
@app_commands.describe(user="Who to pat")
async def cmd_pat(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "pat", "Pat", "pats", user)

@bot.tree.command(name="slap", description="👋 Slap someone")
@app_commands.describe(user="Who to slap")
async def cmd_slap(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "slap", "Slap", "slaps", user)

@bot.tree.command(name="cry", description="😢 Cry")
async def cmd_cry(interaction: discord.Interaction):
    await _send_gif_action(interaction, "cry", "Cry", "cries")

@bot.tree.command(name="dance", description="💃 Dance")
async def cmd_dance(interaction: discord.Interaction):
    await _send_gif_action(interaction, "dance", "Dance", "dances")

@bot.tree.command(name="poke", description="👉 Poke someone")
@app_commands.describe(user="Who to poke")
async def cmd_poke(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "poke", "Poke", "pokes", user)

@bot.tree.command(name="tickle", description="🤣 Tickle someone")
@app_commands.describe(user="Who to tickle")
async def cmd_tickle(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "tickle", "Tickle", "tickles", user)

@bot.tree.command(name="blush", description="😳 Blush")
async def cmd_blush(interaction: discord.Interaction):
    await _send_gif_action(interaction, "blush", "Blush", "blushes")

@bot.tree.command(name="highfive", description="🙏 High-five someone")
@app_commands.describe(user="Who to high-five")
async def cmd_highfive(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "highfive", "High Five", "high-fives", user)

@bot.tree.command(name="bite", description="😬 Bite someone")
@app_commands.describe(user="Who to bite")
async def cmd_bite(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "bite", "Bite", "bites", user)

@bot.tree.command(name="cuddle", description="🥰 Cuddle someone")
@app_commands.describe(user="Who to cuddle")
async def cmd_cuddle(interaction: discord.Interaction, user: discord.Member = None):
    await _send_gif_action(interaction, "cuddle", "Cuddle", "cuddles", user)

@bot.tree.command(name="wave", description="👋 Wave")
async def cmd_wave(interaction: discord.Interaction):
    await _send_gif_action(interaction, "wave", "Wave", "waves")

@bot.tree.command(name="smile", description="😄 Smile")
async def cmd_smile(interaction: discord.Interaction):
    await _send_gif_action(interaction, "smile", "Smile", "smiles")


# ── KEYWORD GIF SEARCH (Klipy API) ───────────────────────────────
async def fetch_klipy_gif(query: str):
    """Search a GIF on Klipy by keyword. Returns the URL, or None on failure."""
    try:
        params = {"q": query, "key": KLIPY_API_KEY, "limit": 1}
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(KLIPY_SEARCH_URL, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                results = data.get("results")
                if not results:
                    return None
                return results[0]["media"]["gif"]["url"]
    except Exception as ex:
        logger.warning(f"fetch_klipy_gif: {ex}")
        return None

@bot.tree.command(name="gif", description="🎞️ Search for a GIF by keyword")
@app_commands.describe(query="Keyword to search the GIF for (e.g. cat, laugh, anime)")
async def cmd_gif(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    gif_url = await fetch_klipy_gif(query)
    if not gif_url:
        return await interaction.followup.send(embed=_e("No Results", f"I couldn't find any GIF for `{query}`.", C_WARN))
    e = _e("GIF Result", f"Search: `{query}`")
    e.set_image(url=gif_url)
    await interaction.followup.send(embed=e)


# ══════════════════════════════════════════════════════════════
#  UTILITY
# ══════════════════════════════════════════════════════════════

class AvatarView(View):
    def __init__(self, avatar_url: str):
        super().__init__(timeout=None)
        self.add_item(Button(label="Open in browser", url=avatar_url, style=discord.ButtonStyle.link))

@bot.tree.command(name="avatar", description="🖼️ Show a user's avatar")
@app_commands.describe(user="User whose avatar you want to see")
async def cmd_avatar(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    avatar_url = user.display_avatar.url
    e = _e(f"{user.display_name}'s Avatar")
    e.set_image(url=avatar_url)
    await interaction.response.send_message(embed=e, view=AvatarView(avatar_url))

@bot.tree.command(name="banner", description="🎴 Show a user's banner")
@app_commands.describe(user="User whose banner you want to see")
async def cmd_banner(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    try:
        full_user = await bot.fetch_user(user.id)
        if not full_user.banner:
            return await interaction.response.send_message(embed=_e("No Banner", f"{user.mention} doesn't have a banner set.", C_WARN))
        e = _e(f"{user.display_name}'s Banner")
        e.set_image(url=full_user.banner.url)
        await interaction.response.send_message(embed=e)
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")

@bot.tree.command(name="userinfo", description="👤 Show detailed information about a user")
@app_commands.describe(user="User to look up")
async def cmd_userinfo(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    roles = [r.mention for r in reversed(user.roles) if r.name != "@everyone"]
    e = _e(f"{user.display_name}'s Information")
    e.set_thumbnail(url=user.display_avatar.url)
    e.add_field(name="User", value=f"`{user}`", inline=True)
    e.add_field(name="ID", value=f"`{user.id}`", inline=True)
    e.add_field(name="Bot", value=f"`{'Yes' if user.bot else 'No'}`", inline=True)
    e.add_field(name="Account Created", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
    e.add_field(name="Joined", value=f"<t:{int(user.joined_at.timestamp())}:R>" if user.joined_at else "`N/A`", inline=True)
    e.add_field(name="Highest Role", value=user.top_role.mention if user.top_role else "`N/A`", inline=True)
    e.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles[:15]) if roles else "`None`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverinfo", description="📋 Show server information")
async def cmd_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    if g is None:
        return await _send_error(interaction, "This command only works inside a server.")
    e = _e(g.name)
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="ID", value=f"`{g.id}`", inline=True)
    e.add_field(name="Owner", value=g.owner.mention if g.owner else "`Unknown`", inline=True)
    e.add_field(name="Members", value=f"`{g.member_count}`", inline=True)
    e.add_field(name="Channels", value=f"`{len(g.channels)}`", inline=True)
    e.add_field(name="Roles", value=f"`{len(g.roles)}`", inline=True)
    e.add_field(name="Boosts", value=f"`{g.premium_subscription_count}`", inline=True)
    e.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:R>", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="servericon", description="🖼️ Show the server's icon")
async def cmd_servericon(interaction: discord.Interaction):
    g = interaction.guild
    if not g.icon:
        return await interaction.response.send_message(embed=_e("No Icon", "This server doesn't have an icon set.", C_WARN))
    e = _e(f"{g.name}'s Icon")
    e.set_image(url=g.icon.url)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverbanner", description="🎴 Show the server's banner")
async def cmd_serverbanner(interaction: discord.Interaction):
    g = interaction.guild
    if not g.banner:
        return await interaction.response.send_message(embed=_e("No Banner", "This server doesn't have a banner set.", C_WARN))
    e = _e(f"{g.name}'s Banner")
    e.set_image(url=g.banner.url)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="roleinfo", description="🎭 Show information about a specific role")
@app_commands.describe(role="Role to look up")
async def cmd_roleinfo(interaction: discord.Interaction, role: discord.Role):
    e = discord.Embed(title=f"{EMOJI_GREEN_DOT} Role Information", color=role.color if role.color.value else C_GREEN, timestamp=datetime.now(timezone.utc))
    e.add_field(name="Name", value=f"`{role.name}`", inline=True)
    e.add_field(name="ID", value=f"`{role.id}`", inline=True)
    e.add_field(name="Color", value=f"`{str(role.color)}`", inline=True)
    e.add_field(name="Members with this role", value=f"`{len(role.members)}`", inline=True)
    e.add_field(name="Position", value=f"`{role.position}`", inline=True)
    e.add_field(name="Mentionable", value=f"`{'Yes' if role.mentionable else 'No'}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="channelinfo", description="📂 Show information about the current channel")
async def cmd_channelinfo(interaction: discord.Interaction):
    ch = interaction.channel
    e = _e(f"#{ch.name} Information")
    e.add_field(name="ID", value=f"`{ch.id}`", inline=True)
    e.add_field(name="Type", value=f"`{ch.type}`", inline=True)
    e.add_field(name="Created", value=f"<t:{int(ch.created_at.timestamp())}:R>", inline=True)
    if isinstance(ch, discord.TextChannel):
        e.add_field(name="Category", value=f"`{ch.category.name if ch.category else 'None'}`", inline=True)
        e.add_field(name="Slowmode", value=f"`{ch.slowmode_delay}s`", inline=True)
        e.add_field(name="NSFW", value=f"`{'Yes' if ch.is_nsfw() else 'No'}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="membercount", description="👥 Show the server's member count")
async def cmd_membercount(interaction: discord.Interaction):
    g = interaction.guild
    humans = sum(1 for m in g.members if not m.bot)
    bots = sum(1 for m in g.members if m.bot)
    e = _e("Server Members")
    e.add_field(name="Humans", value=f"`{humans}`", inline=True)
    e.add_field(name="Bots", value=f"`{bots}`", inline=True)
    e.add_field(name="Total", value=f"`{g.member_count}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="emojicount", description="😃 Show the server's emoji count")
async def cmd_emojicount(interaction: discord.Interaction):
    g = interaction.guild
    static_count = sum(1 for em in g.emojis if not em.animated)
    animated_count = sum(1 for em in g.emojis if em.animated)
    e = _e("Server Emojis")
    e.add_field(name="Static", value=f"`{static_count}`", inline=True)
    e.add_field(name="Animated", value=f"`{animated_count}`", inline=True)
    e.add_field(name="Total", value=f"`{len(g.emojis)}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="botpermissions", description="🔐 Show the bot's permissions in this channel")
async def cmd_botpermissions(interaction: discord.Interaction):
    perms = interaction.channel.permissions_for(interaction.guild.me)
    active = [p.replace("_", " ").title() for p, v in perms if v]
    desc = ", ".join(f"`{p}`" for p in active[:25])
    await interaction.response.send_message(embed=_e("Bot Permissions", desc or "None"))

@bot.tree.command(name="poll", description="📊 Create a quick poll")
@app_commands.describe(question="Poll question")
async def cmd_poll(interaction: discord.Interaction, question: str):
    e = _e("New Poll", question)
    e.set_footer(text=f"Poll by {interaction.user.display_name} • {_footer()}")
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")

@bot.tree.command(name="calc", description="🧮 Simple calculator")
@app_commands.describe(expression="Math expression, e.g. (5+3)*2")
async def cmd_calc(interaction: discord.Interaction, expression: str):
    if not re.match(r"^[0-9+\-*/().\s%]+$", expression):
        return await _send_error(interaction, "Only numbers and math operators are allowed (+ - * / % ( )).")
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await interaction.response.send_message(embed=_e("Calculator", f"`{expression}` = `{result}`"))
    except Exception:
        await _send_error(interaction, "Couldn't calculate that expression.")

@bot.tree.command(name="timestamp", description="🕒 Convert a date to a Discord timestamp")
@app_commands.describe(date="Format: YYYY-MM-DD HH:MM (24h)")
async def cmd_timestamp(interaction: discord.Interaction, date: str):
    try:
        dt = datetime.strptime(date, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        ts = int(dt.timestamp())
        desc = f"`<t:{ts}:F>` → <t:{ts}:F>\n`<t:{ts}:R>` → <t:{ts}:R>"
        await interaction.response.send_message(embed=_e("Timestamp Generated", desc))
    except ValueError:
        await _send_error(interaction, "Invalid format. Use: `YYYY-MM-DD HH:MM` (e.g. `2026-12-25 18:00`).")

@bot.tree.command(name="remindme", description="⏰ Create a personal reminder")
@app_commands.describe(minutes="In how many minutes to remind you", message="What you want to be reminded of")
async def cmd_remindme(interaction: discord.Interaction, minutes: int, message: str):
    if minutes < 1 or minutes > 10080:
        return await _send_error(interaction, "Minutes must be between `1` and `10080` (7 days).")
    await interaction.response.send_message(embed=_e("Reminder Created", f"I'll remind you in `{minutes}` min: {message}"))

    async def remind_later():
        await asyncio.sleep(minutes * 60)
        try:
            await interaction.user.send(embed=_e("⏰ Reminder", message))
        except Exception:
            try:
                await interaction.channel.send(f"{interaction.user.mention} ⏰ Reminder: {message}")
            except Exception:
                pass

    asyncio.create_task(remind_later())


# ══════════════════════════════════════════════════════════════
#  SEARCH
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="wikipedia", description="📚 Search Wikipedia")
@app_commands.describe(query="What you want to search for")
async def cmd_wikipedia(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query)}", timeout=10)
        if r.status_code != 200:
            return await interaction.followup.send(embed=_e("No Results", "Article not found.", C_WARN))
        data = r.json()
        e = _e(data.get("title", query), data.get("extract", "")[:1500])
        if data.get("thumbnail"):
            e.set_thumbnail(url=data["thumbnail"]["source"])
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Error searching Wikipedia.", C_ERROR))

@bot.tree.command(name="youtube", description="▶️ Search YouTube")
@app_commands.describe(query="What you want to search for")
async def cmd_youtube(interaction: discord.Interaction, query: str):
    url = f"https://www.youtube.com/results?search_query={quote(query)}"
    await interaction.response.send_message(embed=_e("YouTube Result", f"[Search: {query}]({url})"))

@bot.tree.command(name="google", description="🔍 Search Google")
@app_commands.describe(query="What you want to search for")
async def cmd_google(interaction: discord.Interaction, query: str):
    url = f"https://www.google.com/search?q={quote(query)}"
    await interaction.response.send_message(embed=_e("Google Result", f"[Search: {query}]({url})"))

@bot.tree.command(name="translate", description="🌐 Translate a text")
@app_commands.describe(text="Text to translate", language="Target language code (e.g. en, es, fr)")
async def cmd_translate(interaction: discord.Interaction, text: str, language: str = "en"):
    await interaction.response.defer()
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": text, "langpair": f"auto|{language}"}, timeout=10).json()
        translation = r["responseData"]["translatedText"]
        await interaction.followup.send(embed=_e("Translation", f"**Original:** {text}\n**Translated ({language}):** {translation}"))
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Error translating the text.", C_ERROR))

@bot.tree.command(name="weather", description="⛅ Check the weather in a city")
@app_commands.describe(city="City name")
async def cmd_weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    try:
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}, timeout=10).json()
        if not geo.get("results"):
            return await interaction.followup.send(embed=_e("City Not Found", "Check the name and try again.", C_WARN))
        loc = geo["results"][0]
        w = requests.get("https://api.open-meteo.com/v1/forecast", params={"latitude": loc["latitude"], "longitude": loc["longitude"], "current_weather": True}, timeout=10).json()
        cw = w.get("current_weather", {})
        e = _e(f"Weather in {loc['name']}", f"🌡️ Temperature: `{cw.get('temperature')}°C`\n💨 Wind: `{cw.get('windspeed')} km/h`")
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Error fetching the weather.", C_ERROR))


# ══════════════════════════════════════════════════════════════
#  ECONOMY
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="balance", description="💰 Check your balance or another user's")
@app_commands.describe(user="User to check")
async def cmd_balance(interaction: discord.Interaction, user: discord.Member = None):
    u = user or interaction.user
    data = get_eco(u.id)
    await interaction.response.send_message(embed=_e(f"{u.display_name}'s Balance", f"`{data['bal']}` coins."))

@bot.tree.command(name="daily", description="🎁 Claim your daily reward")
async def cmd_daily(interaction: discord.Interaction):
    data = get_eco(interaction.user.id)
    now = int(time.time())
    if now - data["daily"] < 86400:
        remaining = 86400 - (now - data["daily"])
        return await interaction.response.send_message(embed=_e("Wait a Bit", f"You already claimed your daily. Come back in `{remaining // 3600}h {(remaining % 3600) // 60}m`.", C_WARN), ephemeral=True)
    data["bal"] += 100
    data["daily"] = now
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Daily Reward", f"You received `100` coins. Balance: `{data['bal']}`"))

@bot.tree.command(name="work", description="💼 Work and earn coins")
async def cmd_work(interaction: discord.Interaction):
    data = get_eco(interaction.user.id)
    now = int(time.time())
    if now - data.get("work", 0) < 3600:
        remaining = 3600 - (now - data.get("work", 0))
        return await interaction.response.send_message(embed=_e("Still Tired", f"You must wait `{remaining // 60}m` before working again.", C_WARN), ephemeral=True)
    earned = random.randint(20, 50)
    data["bal"] += earned
    data["work"] = now
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Work Completed", f"You earned `{earned}` coins."))

@bot.tree.command(name="beg", description="🙏 Beg for coins (sometimes works)")
async def cmd_beg(interaction: discord.Interaction):
    data = get_eco(interaction.user.id)
    if random.random() < 0.5:
        earned = random.randint(1, 30)
        data["bal"] += earned
        save_data("economy", economy_data)
        await interaction.response.send_message(embed=_e("Someone helped you!", f"You received `{earned}` coins."))
    else:
        await interaction.response.send_message(embed=_e("No one helped you", "Try again later.", C_WARN))

@bot.tree.command(name="pay", description="💸 Pay another user")
@app_commands.describe(user="Who to pay", amount="Amount of coins")
async def cmd_pay(interaction: discord.Interaction, user: discord.Member, amount: int):
    if amount <= 0:
        return await _send_error(interaction, "The amount must be greater than 0.")
    if user.id == interaction.user.id:
        return await _send_error(interaction, "You can't pay yourself.")
    d1 = get_eco(interaction.user.id)
    d2 = get_eco(user.id)
    if d1["bal"] < amount:
        return await _send_error(interaction, "Insufficient balance.")
    d1["bal"] -= amount
    d2["bal"] += amount
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Payment Sent", f"{interaction.user.mention} paid `{amount}` coins to {user.mention}."))

@bot.tree.command(name="rob", description="🥷 Try to steal coins from another user")
@app_commands.describe(user="Who to rob")
async def cmd_rob(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        return await _send_error(interaction, "You can't rob yourself.")
    robber = get_eco(interaction.user.id)
    victim = get_eco(user.id)
    now = int(time.time())
    if now - robber.get("rob", 0) < 1800:
        remaining = 1800 - (now - robber.get("rob", 0))
        return await interaction.response.send_message(embed=_e("Careful", f"You must wait `{remaining // 60}m` before robbing again.", C_WARN), ephemeral=True)
    robber["rob"] = now
    if victim["bal"] < 20:
        save_data("economy", economy_data)
        return await interaction.response.send_message(embed=_e("Robbery Failed", f"{user.mention} doesn't have enough coins to rob."))
    if random.random() < 0.5:
        amount = random.randint(10, min(100, victim["bal"]))
        victim["bal"] -= amount
        robber["bal"] += amount
        save_data("economy", economy_data)
        await interaction.response.send_message(embed=_e("Robbery Successful!", f"You stole `{amount}` coins from {user.mention}."))
    else:
        fine = min(30, robber["bal"])
        robber["bal"] -= fine
        save_data("economy", economy_data)
        await interaction.response.send_message(embed=_e("Robbery Failed", f"You got caught and lost `{fine}` coins.", C_ERROR))

@bot.tree.command(name="slots", description="🎰 Play the slot machine")
@app_commands.describe(bet="Amount of coins to bet")
async def cmd_slots(interaction: discord.Interaction, bet: int):
    data = get_eco(interaction.user.id)
    if bet <= 0:
        return await _send_error(interaction, "The bet must be greater than 0.")
    if data["bal"] < bet:
        return await _send_error(interaction, "Insufficient balance.")
    symbols = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]
    result = [random.choice(symbols) for _ in range(3)]
    line = " | ".join(result)
    if result[0] == result[1] == result[2]:
        winnings = bet * 5
        data["bal"] += winnings
        desc = f"{line}\n\nJackpot! You won `{winnings}` coins."
        color = C_GREEN
    elif len(set(result)) == 2:
        winnings = bet * 2
        data["bal"] += winnings
        desc = f"{line}\n\nYou won `{winnings}` coins."
        color = C_GREEN
    else:
        data["bal"] -= bet
        desc = f"{line}\n\nYou lost `{bet}` coins."
        color = C_ERROR
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Slot Machine", desc, color))

@bot.tree.command(name="baltop", description="🏆 Top richest users in the server")
async def cmd_baltop(interaction: discord.Interaction):
    ranked = sorted(economy_data.items(), key=lambda x: x[1]["bal"], reverse=True)[:10]
    if not ranked:
        return await interaction.response.send_message(embed=_e("Wealth Leaderboard", "No data yet."))
    desc = ""
    for i, (uid, info) in enumerate(ranked, start=1):
        member = interaction.guild.get_member(int(uid)) if interaction.guild else None
        name = member.display_name if member else f"User {uid}"
        desc += f"**{i}.** {name} — `{info['bal']}` coins\n"
    await interaction.response.send_message(embed=_e("Wealth Leaderboard", desc))


# ══════════════════════════════════════════════════════════════
#  LEVELS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="rank", description="📈 Check your level rank")
@app_commands.describe(user="User to check")
async def cmd_rank(interaction: discord.Interaction, user: discord.Member = None):
    u = user or interaction.user
    lvl = get_level(interaction.guild_id, u.id)
    needed = xp_needed(lvl["level"])
    await interaction.response.send_message(embed=_e(f"{u.display_name}'s Rank", f"Level: `{lvl['level']}`\nXP: `{lvl['xp']}/{needed}`"))

@bot.tree.command(name="level", description="📊 Check your current level")
@app_commands.describe(user="User to check")
async def cmd_level(interaction: discord.Interaction, user: discord.Member = None):
    u = user or interaction.user
    lvl = get_level(interaction.guild_id, u.id)
    await interaction.response.send_message(embed=_e(f"{u.display_name}'s Level", f"Level: `{lvl['level']}`"))

@bot.tree.command(name="xptop", description="🏆 Server XP leaderboard")
async def cmd_xptop(interaction: discord.Interaction):
    gid = str(interaction.guild_id)
    data = levels_data.get(gid, {})
    ranked = sorted(data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    if not ranked:
        return await interaction.response.send_message(embed=_e("Leaderboard", "No level data yet."))
    desc = ""
    for i, (uid, info) in enumerate(ranked, start=1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        desc += f"**{i}.** {name} — Level `{info['level']}` (`{info['xp']}` XP)\n"
    await interaction.response.send_message(embed=_e("Leaderboard", desc))

@bot.tree.command(name="setlevel", description="🔧 [Admin] Set a user's level")
@app_commands.describe(user="User", level="New level")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlevel(interaction: discord.Interaction, user: discord.Member, level: int):
    lvl = get_level(interaction.guild_id, user.id)
    lvl["level"] = max(0, level)
    lvl["xp"] = 0
    save_data("levels", levels_data)
    await interaction.response.send_message(embed=_e("Level Set", f"{user.mention} is now level `{level}`."))
_perm_error_handler(cmd_setlevel)


# ══════════════════════════════════════════════════════════════
#  GIVEAWAYS
# ══════════════════════════════════════════════════════════════

class GiveawayView(View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        btn = Button(label="Enter", emoji="🎉", style=discord.ButtonStyle.success, custom_id=f"ga_join_{giveaway_id}")
        btn.callback = self.join_callback
        self.add_item(btn)

    async def join_callback(self, interaction: discord.Interaction):
        ga = giveaways_data.get(self.giveaway_id)
        if not ga or ga.get("ended"):
            return await interaction.response.send_message("❌ This giveaway has already ended.", ephemeral=True)
        uid = str(interaction.user.id)
        if uid in ga["participants"]:
            ga["participants"].remove(uid)
            msg = "❌ You left the giveaway."
        else:
            ga["participants"].append(uid)
            msg = "🎉 You're now entered in the giveaway!"
        save_data("giveaways", giveaways_data)
        await interaction.response.send_message(msg, ephemeral=True)

async def _end_giveaway(giveaway_id: str, channel: discord.abc.Messageable):
    ga = giveaways_data.get(giveaway_id)
    if not ga or ga.get("ended"):
        return
    ga["ended"] = True
    participants = ga["participants"]
    winners = random.sample(participants, min(ga["winners"], len(participants))) if participants else []
    save_data("giveaways", giveaways_data)
    desc = f"Prize: **{ga['prize']}**\n"
    desc += f"Winners: {', '.join(f'<@{w}>' for w in winners)}" if winners else "No one participated."
    await channel.send(embed=_e("Giveaway Ended", desc))

@bot.tree.command(name="giveawaystart", description="🎉 [Admin] Start a giveaway")
@app_commands.describe(prize="Giveaway prize", minutes="Duration in minutes", winners="Number of winners")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_giveawaystart(interaction: discord.Interaction, prize: str, minutes: int, winners: int = 1):
    giveaway_id = str(int(time.time() * 1000))
    end_ts = int(time.time()) + minutes * 60
    e = _e("Giveaway Active!", f"Prize: **{prize}**\nWinners: `{winners}`\nEnds: <t:{end_ts}:R>")
    view = GiveawayView(giveaway_id)
    await interaction.response.send_message(embed=e, view=view)
    giveaways_data[giveaway_id] = {
        "guild_id": interaction.guild_id, "prize": prize, "winners": winners,
        "participants": [], "end_ts": end_ts, "ended": False, "host": str(interaction.user.id),
    }
    save_data("giveaways", giveaways_data)

    async def auto_end():
        await asyncio.sleep(minutes * 60)
        await _end_giveaway(giveaway_id, interaction.channel)

    asyncio.create_task(auto_end())
_perm_error_handler(cmd_giveawaystart)

@bot.tree.command(name="giveawayend", description="🏁 [Admin] End a giveaway manually")
@app_commands.describe(giveaway_id="Giveaway ID")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_giveawayend(interaction: discord.Interaction, giveaway_id: str):
    if giveaway_id not in giveaways_data:
        return await _send_error(interaction, "Giveaway not found.")
    await interaction.response.send_message(embed=_e("Ending", "Processing giveaway..."), ephemeral=True)
    await _end_giveaway(giveaway_id, interaction.channel)
_perm_error_handler(cmd_giveawayend)

@bot.tree.command(name="giveawayreroll", description="🔁 [Admin] Pick a new winner")
@app_commands.describe(giveaway_id="Giveaway ID")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_giveawayreroll(interaction: discord.Interaction, giveaway_id: str):
    ga = giveaways_data.get(giveaway_id)
    if not ga:
        return await _send_error(interaction, "Giveaway not found.")
    if not ga["participants"]:
        return await _send_error(interaction, "There are no participants for the reroll.")
    winner = random.choice(ga["participants"])
    await interaction.response.send_message(embed=_e("New Winner", f"🎉 The new winner is <@{winner}>!"))
_perm_error_handler(cmd_giveawayreroll)


# ══════════════════════════════════════════════════════════════
#  TICKETS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="ticketopen", description="🎫 Open a support ticket")
async def cmd_ticketopen(interaction: discord.Interaction):
    guild = interaction.guild
    name = f"ticket-{interaction.user.name}".lower()[:90]
    if discord.utils.get(guild.text_channels, name=name):
        return await _send_error(interaction, "You already have an open ticket.")
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    ch = await guild.create_text_channel(name, overwrites=overwrites)
    await interaction.response.send_message(embed=_e("Ticket Created", f"Your ticket: {ch.mention}"), ephemeral=True)
    await ch.send(f"{interaction.user.mention}", embed=_e("Support Ticket", "Describe your issue. A staff member will assist you shortly."))

@bot.tree.command(name="ticketclose", description="🔒 Close the current ticket")
async def cmd_ticketclose(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await _send_error(interaction, "This channel is not a ticket.")
    await interaction.response.send_message(embed=_e("Closing Ticket", "This ticket will close in 5 seconds..."))
    await asyncio.sleep(5)
    await interaction.channel.delete()


# ══════════════════════════════════════════════════════════════
#  ROLES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="addrole", description="➕ [Admin] Add a role to a user")
@app_commands.describe(user="User", role="Role to add")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_addrole(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    try:
        await user.add_roles(role)
        await interaction.response.send_message(embed=_e("Role Added", f"{role.mention} was added to {user.mention}."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_addrole)

@bot.tree.command(name="removerole", description="➖ [Admin] Remove a role from a user")
@app_commands.describe(user="User", role="Role to remove")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_removerole(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    try:
        await user.remove_roles(role)
        await interaction.response.send_message(embed=_e("Role Removed", f"{role.mention} was removed from {user.mention}."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_removerole)

@bot.tree.command(name="autorole", description="🎭 [Admin] Set the automatic role for new members")
@app_commands.describe(role="Role to assign automatically")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_autorole(interaction: discord.Interaction, role: discord.Role):
    cfg = get_config(interaction.guild_id)
    cfg["autorole"] = role.id
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Autorole Set", f"New members will receive: {role.mention}"))
_perm_error_handler(cmd_autorole)


# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="setwelcome", description="👋 [Admin] Set the welcome channel")
@app_commands.describe(channel="Welcome channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg = get_config(interaction.guild_id)
    cfg["welcome_channel"] = channel.id
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Welcome Channel Set", f"Channel set to: {channel.mention}"))
_perm_error_handler(cmd_setwelcome)

@bot.tree.command(name="setlogs", description="📜 [Admin] Set the logs channel")
@app_commands.describe(channel="Logs channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg = get_config(interaction.guild_id)
    cfg["log_channel"] = channel.id
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Logs Channel Set", f"Channel set to: {channel.mention}"))
_perm_error_handler(cmd_setlogs)

@bot.tree.command(name="setprefix", description="🔤 [Admin] Set the bot's prefix")
@app_commands.describe(prefix="New prefix")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setprefix(interaction: discord.Interaction, prefix: str):
    cfg = get_config(interaction.guild_id)
    cfg["prefix"] = prefix
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Prefix Set", f"New prefix: `{prefix}`"))
_perm_error_handler(cmd_setprefix)

@bot.tree.command(name="settings", description="⚙️ View the server's current configuration")
async def cmd_settings(interaction: discord.Interaction):
    cfg = get_config(interaction.guild_id)
    e = _e("Server Configuration")
    e.add_field(name="Welcome Channel", value=f"<#{cfg['welcome_channel']}>" if cfg.get("welcome_channel") else "`Not set`", inline=False)
    e.add_field(name="Logs Channel", value=f"<#{cfg['log_channel']}>" if cfg.get("log_channel") else "`Not set`", inline=False)
    e.add_field(name="Autorole", value=f"<@&{cfg['autorole']}>" if cfg.get("autorole") else "`Not set`", inline=False)
    e.add_field(name="Prefix", value=f"`{cfg.get('prefix', '!')}`", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)


# ══════════════════════════════════════════════════════════════
#  BOT INFORMATION
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="botinfo", description="🤖 General bot information")
async def cmd_botinfo(interaction: discord.Interaction):
    e = _e("FMD BOT", "Multi-purpose bot with a premium bypass system.")
    e.add_field(name="Servers", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="Latency", value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.add_field(name="Uptime", value=f"`{_uptime()}`", inline=True)
    e.add_field(name="Commands", value=f"`{len(bot.tree.get_commands())}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="invite", description="🔗 Invite the bot to your server")
async def cmd_invite(interaction: discord.Interaction):
    await interaction.response.send_message(embed=_e("Invite the Bot", f"[Click here to invite me]({BOT_INVITE_URL})"))

@bot.tree.command(name="uptime", description="⏱️ Check the bot's uptime")
async def cmd_uptime(interaction: discord.Interaction):
    await interaction.response.send_message(embed=_e("Uptime", f"`{_uptime()}`"))

@bot.tree.command(name="support", description="🆘 Support server link")
async def cmd_support(interaction: discord.Interaction):
    await interaction.response.send_message(embed=_e("Support Server", f"[Join here]({SUPPORT_SERVER_URL})"))


# ── HEALTH SERVER (For Render) ────────────────────────────────
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
    logger.info(f"🌐 Health server running on port :{PORT}")

# ── MAIN ─────────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN not found in environment variables.")
        return
    start_web()
    logger.info("🚀 Starting FMD BOT...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
