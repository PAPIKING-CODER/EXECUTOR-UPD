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

import discord
from discord import app_commands
from discord.ui import Button, View
import requests
from dotenv import load_dotenv

load_dotenv()

# ── LOGGING ──────────────────────────────────────────────────────
LOG_FILE = "bot_logs.txt"
logger = logging.getLogger("KING_BOT")
logger.setLevel(logging.INFO)
_file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
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
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525040833814855710")

# 🔗 NUEVO ENDPOINT DE BYPASS
# NOTA: Rate limit de 4 peticiones cada 10 segundos. 
# Si spammeas más de 4 veces en 10 segundos, te banearán permanentemente.
BYPASS_API_ENDPOINT = "http://fi8.bot-hosting.net:21163/freeapibypass?url="
AUTOBYPASS_FILE = "autobypass_channels.json"

# ── EMOJIS AND IMAGES ────────────────────────────────────────────
URL_CHECK  = "https://cdn.discordapp.com/emojis/1511381303872716820.webp?size=100&animated=true"
URL_REDPT  = "https://cdn.discordapp.com/emojis/1463164698353733725.webp?size=100&animated=true"
URL_WARN   = "https://cdn.discordapp.com/emojis/1495901573476520106.webp?size=100"
URL_RDIAM  = "https://cdn.discordapp.com/emojis/1469195655762153502.webp?size=100&animated=true"
URL_CROWN  = "https://cdn.discordapp.com/emojis/1461735621985833061.webp?size=100&animated=true"
URL_NO     = "https://cdn.discordapp.com/emojis/606562703917449226.webp?size=100&animated=true"
URL_LOAD   = "https://cdn.discordapp.com/emojis/1463540610379022429.webp?size=100&animated=true"

# Main banner GIF
BYPASS_BANNER_URL = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a5485bb&is=6a53343b&hm=f6df69c459c7bad9ed031d12eee35f42ab4adbb7290fe08a3707046eb3bf7200&"

# Emoji IDs for inline text
E_CHECK   = "<a:_:1511381303872716820>"   # ✅
E_REDPT   = "<a:_:1463164698353733725>"   # 🔴
E_WARN    = "<:_:1495901573476520106>"    # ⚠️
E_RDIAM   = "<a:_:1469195655762153502>"   # 💎
E_ARROW   = "<a:_:1401389285042684035>"   # ➡️
E_CROWN   = "<a:_:1461735621985833061>"   # 👑
E_NO      = "<a:_:606562703917449226>"    # ❌
E_LOAD    = "<a:_:1463540610379022429>"   # ⏳

# ── COLORS ──────────────────────────────────────────────────────
C_LOADING = 0xFFA500  # orange
C_SUCCESS = 0x00FF00   # green
C_ERROR   = 0xFF0000   # red

# ── HELPERS ──────────────────────────────────────────────────────
BOT_START_TIME = datetime.now(timezone.utc)
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def _footer() -> str:
    return "MADE WITH💚•KING BYPASS"

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START_TIME
    t = int(d.total_seconds())
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

async def _delete_after(msg: discord.Message, delay: int = 120):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass

# ── JSON HELPERS ─────────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(data), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not save {path}: {e}")

autobypass_channels = load_json(AUTOBYPASS_FILE, set())

# ── BYPASS ENGINE ────────────────────────────────────────────────
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "KingBot/1.0"})

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
    # NOTE: Respeta el rate limit de la API (4 requests cada 10 segundos)
    for attempt in range(1, 4):
        try:
            resp = _http_session.get(BYPASS_API_ENDPOINT + quote(url, safe=""), timeout=45)
            if resp.status_code != 200:
                if attempt < 3:
                    time.sleep(2)
                    continue
                return None, f"HTTP {resp.status_code}"
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"):
                    return txt, None
                if attempt < 3:
                    time.sleep(2)
                    continue
                return None, "Invalid API response"

            api_says_error = False
            if isinstance(data, dict):
                if data.get("success") is False or data.get("error") or str(data.get("status", "")).lower() == "error":
                    api_says_error = True

            result = _extract_bypass_result(data)
            if result and not api_says_error:
                return str(result), None

            if api_says_error:
                err_msg = data.get("message") or data.get("error") if isinstance(data, dict) else None
                last_error = str(err_msg or "API reported an error.")
                if attempt < 3:
                    time.sleep(2)
                    continue
                return None, last_error
            return None, "No result found in API."
        except requests.exceptions.Timeout:
            if attempt < 3:
                time.sleep(2)
        except Exception as e:
            if attempt < 3:
                time.sleep(2)
    return None, "Request timed out after retries."

# ── EMBED BUILDERS ──────────────────────────────────────────────
def embed_loading(url: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_LOADING, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{E_LOAD} Processing Bypass...", icon_url=URL_LOAD)
    e.description = "Please wait while we bypass the link."
    e.add_field(name="🔗 URL", value=f"```\n{url[:200]}\n```", inline=False)
    e.set_thumbnail(url=URL_LOAD)
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, url: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_SUCCESS, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{E_CHECK} Bypassed Successfully", icon_url=URL_CHECK)
    e.add_field(name="🔗 Result", value=f"```\n{result[:1000]}\n```", inline=False)
    e.add_field(name="👤 Requested By", value=user.mention, inline=False)
    e.add_field(name="➡️ Original URL", value=f"```\n{url[:200]}\n```", inline=False)
    e.set_thumbnail(url=URL_CROWN)
    e.set_image(url=BYPASS_BANNER_URL)
    e.set_footer(text=f"{_footer()} • {elapsed:.2f}s")
    return e

def embed_fail(error: str, elapsed: float, url: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{E_NO} Bypass Failed", icon_url=URL_NO)
    e.add_field(name="➡️ Original URL", value=f"```\n{url[:200]}\n```", inline=False)
    e.add_field(name="⚠️ Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name="👤 Requested By", value=user.mention, inline=False)
    e.set_thumbnail(url=URL_WARN)
    e.set_image(url=BYPASS_BANNER_URL)
    e.set_footer(text=f"{_footer()} • {elapsed:.2f}s")
    return e

# ── VIEWS ──────────────────────────────────────────────────────
class BypassViewSuccess(View):
    def __init__(self, result: str, elapsed: float):
        super().__init__(timeout=None)
        self._result = result
        self.add_item(Button(
            label=f"⏱ {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=0
        ))
        self.add_item(Button(
            label="💬 Support Server",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link,
            row=0
        ))
        self.add_item(Button(
            label="🤖 Invite Me",
            url=BOT_INVITE_URL,
            style=discord.ButtonStyle.link,
            row=0
        ))

    @discord.ui.button(label="📋 Copy Result", style=discord.ButtonStyle.success, row=1)
    async def copy_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"```txt\n{self._result[:1900]}\n```",
            ephemeral=True
        )

class BypassViewFail(View):
    def __init__(self, elapsed: float):
        super().__init__(timeout=None)
        self.add_item(Button(
            label=f"⏱ {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=0
        ))
        self.add_item(Button(
            label="💬 Support Server",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link,
            row=0
        ))

# ── HEALTH SERVER (For Render) ───────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'{{"status":"online","bot":"KING BOT","uptime":"{_uptime()}"}}'.encode()
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
    logger.info(f"Health server running on port {PORT}")

# ── BOT CLIENT ────────────────────────────────────────────────────
class KingBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commands synced successfully!")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} ({self.user.id})")
        logger.info(f"Serving {len(self.guilds)} servers")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id in autobypass_channels:
            # Delete the original message immediately
            try:
                await message.delete()
            except Exception:
                pass
            urls = _URL_PATTERN.findall(message.content)
            if urls:
                await self._auto_bypass(message, urls)

    async def _auto_bypass(self, message: discord.Message, urls: list):
        loop = asyncio.get_running_loop()
        for url in urls[:1]:  # only first link to avoid spam
            if not _is_valid_url(url):
                continue
            try:
                status_msg = await message.channel.send(
                    content=message.author.mention,
                    embed=embed_loading(url, message.author)
                )
            except Exception:
                continue
            t0 = time.time()
            result, error = await loop.run_in_executor(None, bypass_url_vps, url)
            elapsed = time.time() - t0

            try:
                if result:
                    embed = embed_success(result, elapsed, url, message.author)
                    view = BypassViewSuccess(result, elapsed)
                    msg = await status_msg.edit(content=message.author.mention, embed=embed, view=view)
                    asyncio.create_task(_delete_after(msg))
                else:
                    embed = embed_fail(error, elapsed, url, message.author)
                    view = BypassViewFail(elapsed)
                    msg = await status_msg.edit(content=message.author.mention, embed=embed, view=view)
                    asyncio.create_task(_delete_after(msg))
            except Exception:
                pass

bot = KingBot()
tree = bot.tree

# ── SLASH COMMANDS ───────────────────────────────────────────────
@tree.command(name="bypass", description="Bypass a link manually")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        e = discord.Embed(description=f"{E_WARN} Invalid URL.", color=C_LOADING)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)

    # Send loading embed
    await interaction.response.send_message(embed=embed_loading(url, interaction.user))

    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_vps, url)
    elapsed = time.time() - t0

    try:
        if result:
            embed = embed_success(result, elapsed, url, interaction.user)
            view = BypassViewSuccess(result, elapsed)
            msg = await interaction.edit_original_response(embed=embed, view=view)
            asyncio.create_task(_delete_after(msg))
        else:
            embed = embed_fail(error, elapsed, url, interaction.user)
            view = BypassViewFail(elapsed)
            msg = await interaction.edit_original_response(embed=embed, view=view)
            asyncio.create_task(_delete_after(msg))
    except Exception as e:
        logger.error(f"Error editing response: {e}")

@tree.command(name="setautobypass", description="[Admin] Toggle auto-bypass in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        save_json(AUTOBYPASS_FILE, autobypass_channels)
        embed = discord.Embed(
            title=f"{E_NO} Auto-Bypass Disabled",
            color=C_ERROR
        )
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_FILE, autobypass_channels)
        embed = discord.Embed(
            title=f"{E_CHECK} Auto-Bypass Enabled",
            color=C_SUCCESS
        )
        embed.description = f"Every message in {interaction.channel.mention} will be deleted; links will be auto-bypassed."
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── ENTRY POINT ───────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set!")
        return
    start_web()
    logger.info("Starting KING BOT...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
