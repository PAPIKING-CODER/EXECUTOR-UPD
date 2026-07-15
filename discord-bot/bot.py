import os
import re
import json
import time
import asyncio
import logging
import threading
import random
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

# ── NUEVOS EMOJIS PERSONALIZADOS ──────────────────────────────
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
            return "📱"
        else:
            return "PC"
    except Exception:
        return "PC"

# ── MOTOR DE BYPASS (NO TOCADO) ────────────────────────────────
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
                if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY); continue
                return None, last_error
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"): return txt, None
                last_error = "Respuesta inválida"
                if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY); continue
                return None, last_error
            api_says_error = False
            if isinstance(data, dict):
                status_val = str(data.get("status", "")).lower()
                if data.get("success") is False or data.get("error") or status_val == "error":
                    api_says_error = True
            result = _extract_bypass_result(data)
            if result and not api_says_error: return str(result), None
            if api_says_error:
                err_msg = (data.get("message") or data.get("error")) if isinstance(data, dict) else None
                last_error = str(err_msg or "La API reportó un error.")
                if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY); continue
                return None, last_error
            return None, "Sin resultado"
        except requests.exceptions.Timeout:
            last_error = f"Timeout ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY)
        except Exception as e:
            last_error = str(e)[:100]
            if attempt < VPS_BYPASS_MAX_RETRIES: time.sleep(VPS_BYPASS_RETRY_DELAY)
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
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif")
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.description = "Generated successfully"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
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

def create_cmd_embed(title: str, fields: list, color=C_GREEN) -> discord.Embed:
    e = discord.Embed(color=color, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} {title}"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    for f in fields: e.add_field(name=f[0], value=f[1], inline=f[2] if len(f) >= 3 else True)
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
        await interaction.response.send_message(f"{EMOJI_SUCCESS} Copied Successfully!", ephemeral=True)

# ── CUENTA REGRESIVA ────────────────────────────────────────────
async def start_countdown(message: discord.Message, base_embed: discord.Embed, view: View, seconds: int = 120):
    clock_emoji = EMOJI_CLOCK
    while seconds > 0:
        try:
            new_embed = base_embed.copy()
            field_updated = False
            for i, field in enumerate(new_embed.fields):
                if field.name == f"{clock_emoji} Auto Delete":
                    new_embed.set_field_at(i, name=field.name, value=f"Message expires in: `{seconds}s`", inline=field.inline)
                    field_updated = True
                    break
            if not field_updated:
                new_embed.add_field(name=f"{clock_emoji} Auto Delete", value=f"Message expires in: `{seconds}s`", inline=False)
            await message.edit(embed=new_embed, view=view)
            await asyncio.sleep(1)
            seconds -= 1
        except (discord.NotFound, discord.HTTPException): break
    try: await message.delete()
    except Exception: pass

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
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"/help • {len(self.tree.get_commands())} Cmds"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(self._auto_bypass(message, urls))

    async def _auto_bypass(self, message: discord.Message, urls: list):
        try: await message.delete()
        except Exception: pass
        loop = asyncio.get_running_loop()
        for url in urls[:3]:
            if not _is_valid_url(url): continue
            try: status_msg = await message.channel.send(content=message.author.mention, embed=embed_loading())
            except Exception: continue
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
            except Exception: pass

bot = FmdBot()

# ══════════════════════════════════════════════════════════════════
#  🛠️ UTILIDAD (20 Comandos)
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="ping", description="🏓 Ver la latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    await interaction.response.send_message(embed=create_cmd_embed("Pong!", [
        ("Latency", f"`{ms}ms`", True),
        ("Uptime", f"`{_uptime()}`", True),
        ("Servers", f"`{len(bot.guilds)}`", True)
    ]))

@bot.tree.command(name="uptime", description="⏱️ Ver el tiempo activo del bot")
async def cmd_uptime(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_cmd_embed("Bot Uptime", [
        ("Uptime", f"```\n{_uptime()}\n```", False)
    ]))

@bot.tree.command(name="serverinfo", description="🌐 Información del servidor actual")
async def cmd_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    e = create_cmd_embed(f"Server: {g.name}", [
        ("ID", f"`{g.id}`", True), ("Owner", g.owner.mention if g.owner else "None", True),
        ("Members", f"`{g.member_count}`", True), ("Roles", f"`{len(g.roles)}`", True),
        ("Channels", f"`{len(g.channels)}`", True), ("Boosts", f"`{g.premium_subscription_count}`", True),
        ("Created", f"<t:{int(g.created_at.timestamp())}:R>", False)
    ])
    if g.icon: e.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="userinfo", description="👤 Información de un usuario")
async def cmd_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    e = create_cmd_embed(f"User: {target.display_name}", [
        ("ID", f"`{target.id}`", True), ("Bot", "Yes" if target.bot else "No", True),
        ("Joined", f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "Unknown", True),
        ("Created", f"<t:{int(target.created_at.timestamp())}:R>", True)
    ])
    e.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="avatar", description="🖼️ Muestra el avatar de un usuario")
async def cmd_avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} Avatar of {target.display_name}"
    e.set_image(url=target.display_avatar.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="banner", description="🖼️ Muestra el banner de un usuario")
async def cmd_banner(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    await interaction.response.defer()
    try:
        user = await bot.fetch_user(target.id)
        if not user.banner:
            return await interaction.followup.send(embed=create_cmd_embed("Banner", [("Result", f"**{target.display_name}** does not have a banner.", False)], color=C_ERROR))
        e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
        e.set_author(name="FMD BOT • BYPASS", icon_url="")
        e.title = f"{EMOJI_GREEN_DOT} Banner of {target.display_name}"
        e.set_image(url=user.banner.url)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "Could not fetch banner.", False)], color=C_ERROR))

@bot.tree.command(name="roleinfo", description="🎭 Información de un rol")
async def cmd_roleinfo(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.send_message(embed=create_cmd_embed(f"Role: {role.name}", [
        ("ID", f"`{role.id}`", True), ("Color", f"`{role.color}`", True),
        ("Members", f"`{len(role.members)}`", True), ("Hoist", "Yes" if role.hoist else "No", True),
        ("Mentionable", "Yes" if role.mentionable else "No", True)
    ]))

@bot.tree.command(name="channelinfo", description="📌 Información del canal")
async def cmd_channelinfo(interaction: discord.Interaction, channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    await interaction.response.send_message(embed=create_cmd_embed(f"#{ch.name}", [
        ("ID", f"`{ch.id}`", True), ("Topic", ch.topic or "None", True),
        ("Slowmode", f"`{ch.slowmode_delay}s`", True), ("NSFW", "Yes" if ch.is_nsfw() else "No", True)
    ]))

@bot.tree.command(name="emojiinfo", description="🎴 Información de un emoji")
async def cmd_emojiinfo(interaction: discord.Interaction, emoji: str):
    await interaction.response.defer()
    try:
        partial = discord.PartialEmoji.from_str(emoji)
        e = create_cmd_embed(f"Emoji Info", [
            ("Name", f"`{partial.name or 'N/A'}`", True),
            ("ID", f"`{partial.id}`" if partial.id else "`None`", True),
            ("Animated", "Yes" if partial.animated else "No", True)
        ])
        if partial.id:
            e.set_thumbnail(url=partial.url)
        await interaction.followup.send(embed=e)
    except Exception:
        e = create_cmd_embed("Emoji Info", [
            ("Name", "Unicode Emoji", True),
            ("Raw", emoji, False),
            ("Note", "Discord API does not return metadata for Unicode emojis.", False)
        ])
        await interaction.followup.send(embed=e)

@bot.tree.command(name="servericon", description="🏰 Muestra el icono del servidor")
async def cmd_servericon(interaction: discord.Interaction):
    if not interaction.guild.icon:
        return await interaction.response.send_message(embed=create_cmd_embed("Server Icon", [("Result", "This server has no icon.", False)], color=C_ERROR))
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} Server Icon"
    e.set_image(url=interaction.guild.icon.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="weather", description="🌦️ Obtén el clima de una ciudad")
async def cmd_weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://wttr.in/{quote(city)}?format=%C+%t+%w+%h&lang=en"
            async with s.get(url) as r:
                weather = (await r.text()).strip()
                e = create_cmd_embed(f"Weather in {city.title()}", [
                    ("Current", f"```\n{weather}\n```", False)
                ])
                e.set_thumbnail(url="https://cdn.iconscout.com/icon/free/png-256/free-weather-icon-download-in-svg-png-gif-file-formats--cloud-sun-umbrella-symbols-pack-weather-icons-1992996.png")
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "City not found or API down.", False)], color=C_ERROR))

@bot.tree.command(name="math", description="🧮 Calculadora simple")
async def cmd_math(interaction: discord.Interaction, expression: str):
    try:
        expression = expression.replace("x", "*").replace("÷", "/").replace("^", "**")
        result = eval(expression, {"__builtins__": None}, {})
        await interaction.response.send_message(embed=create_cmd_embed("Calculator", [
            ("Expression", f"`{expression}`", True), ("Result", f"`{result}`", True)
        ]))
    except Exception:
        await interaction.response.send_message(embed=create_cmd_embed("Error", [("Result", "Invalid expression.", False)], color=C_ERROR))

@bot.tree.command(name="crypto", description="💰 Precio de criptomonedas (CoinGecko)")
async def cmd_crypto(interaction: discord.Interaction, coin: str, vs_currency: str = "usd"):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin.lower()}&vs_currencies={vs_currency.lower()}"
            async with s.get(url) as r:
                data = await r.json()
                if coin.lower() not in data:
                    return await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "Coin not found.", False)], color=C_ERROR))
                price = data[coin.lower()][vs_currency.lower()]
                await interaction.followup.send(embed=create_cmd_embed(f"{coin.upper()} Price", [
                    ("Price", f"`{price} {vs_currency.upper()}`", False)
                ]))
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "API Error.", False)], color=C_ERROR))

@bot.tree.command(name="github", description="🐙 Busca un usuario de GitHub")
async def cmd_github(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/users/{username}") as r:
                if r.status != 200:
                    return await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "User not found.", False)], color=C_ERROR))
                d = await r.json()
                e = create_cmd_embed(f"GitHub: {d['login']}", [
                    ("Name", d['name'] or "N/A", True), ("Repos", f"`{d['public_repos']}`", True),
                    ("Followers", f"`{d['followers']}`", True), ("Following", f"`{d['following']}`", True)
                ])
                if d['avatar_url']: e.set_thumbnail(url=d['avatar_url'])
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "API Error.", False)], color=C_ERROR))

@bot.tree.command(name="urban", description="📖 Busca una palabra en Urban Dictionary")
async def cmd_urban(interaction: discord.Interaction, term: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.urbandictionary.com/v0/define?term={quote(term)}") as r:
                d = await r.json()
                if not d['list']:
                    return await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "No results found.", False)], color=C_ERROR))
                w = d['list'][0]
                await interaction.followup.send(embed=create_cmd_embed(f"Urban: {term}", [
                    ("Definition", w['definition'][:900], False)
                ]))
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "API Error.", False)], color=C_ERROR))

@bot.tree.command(name="wikipedia", description="📚 Busca un artículo en Wikipedia")
async def cmd_wikipedia(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query)}"
            async with s.get(url) as r:
                d = await r.json()
                if d.get('title') == "Not found.":
                    return await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "Page not found.", False)], color=C_ERROR))
                e = create_cmd_embed(f"Wikipedia: {d['title']}", [
                    ("Summary", f"```\n{d['extract'][:900]}\n```", False)
                ])
                if 'thumbnail' in d and 'source' in d['thumbnail']: e.set_thumbnail(url=d['thumbnail']['source'])
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "API Error.", False)], color=C_ERROR))

@bot.tree.command(name="random", description="🎲 Genera un número aleatorio")
async def cmd_random(interaction: discord.Interaction, min: int = 1, max: int = 100):
    if min >= max: return await interaction.response.send_message(embed=create_cmd_embed("Error", [("Result", "Min must be less than Max.", False)], color=C_ERROR))
    await interaction.response.send_message(embed=create_cmd_embed("Random Number", [
        ("Range", f"`{min}` to `{max}`", True), ("Result", f"`{random.randint(min, max)}`", True)
    ]))

@bot.tree.command(name="color", description="🎨 Genera un color hexadecimal aleatorio")
async def cmd_color(interaction: discord.Interaction):
    color_hex = f"#{random.randint(0, 0xFFFFFF):06X}"
    e = discord.Embed(color=discord.Color.from_rgb(*(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} Random Color"
    e.add_field(name="Hex", value=f"`{color_hex}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="say", description="📢 Repite un mensaje en el chat")
@app_commands.checks.has_permissions(send_messages=True)
async def cmd_say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("✅ Message sent.", ephemeral=True)
    await interaction.channel.send(message)

@bot.tree.command(name="embed", description="📦 Envía un embed personalizado")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_embed(interaction: discord.Interaction, title: str, description: str, color_hex: str = "#00FF66"):
    try: c = int(color_hex.lstrip("#"), 16)
    except: c = C_GREEN
    e = discord.Embed(title=title, description=description, color=c, timestamp=datetime.now(timezone.utc))
    e.set_footer(text=f"Requested by {interaction.user.name}")
    await interaction.response.send_message("✅ Embed sent.", ephemeral=True)
    await interaction.channel.send(embed=e)

# ══════════════════════════════════════════════════════════════════
#  🛡️ MODERACIÓN (12 Comandos)
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="clear", description="🗑️ Elimina mensajes (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear(interaction: discord.Interaction, amount: int = 10):
    if amount <= 0 or amount > 100: return await interaction.response.send_message("Use 1-100.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(embed=create_cmd_embed("Messages Cleared", [
        ("Deleted", f"`{len(deleted)}` messages", True), ("Channel", interaction.channel.mention, True)
    ]), ephemeral=True)

@bot.tree.command(name="kick", description="👢 Expulsa a un miembro")
@app_commands.checks.has_permissions(kick_members=True)
async def cmd_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message("You cannot kick this user.", ephemeral=True)
    await member.kick(reason=f"{reason} | Mod: {interaction.user}")
    await interaction.response.send_message(embed=create_cmd_embed("User Kicked", [
        ("User", member.mention, True), ("Reason", reason, True)
    ]))

@bot.tree.command(name="ban", description="🔨 Banea a un miembro")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message("You cannot ban this user.", ephemeral=True)
    await member.ban(reason=f"{reason} | Mod: {interaction.user}")
    await interaction.response.send_message(embed=create_cmd_embed("User Banned", [
        ("User", member.mention, True), ("Reason", reason, True)
    ]))

@bot.tree.command(name="unban", description="✅ Desbanea a un usuario")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=create_cmd_embed("User Unbanned", [
            ("User", f"`{user}`", True)
        ]))
    except Exception:
        await interaction.response.send_message("Invalid ID or user not banned.", ephemeral=True)

@bot.tree.command(name="timeout", description="⏱️ Aisla a un miembro (minutos)")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason"):
    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(until, reason=reason)
    await interaction.response.send_message(embed=create_cmd_embed("Timeout Applied", [
        ("User", member.mention, True), ("Duration", f"`{minutes}m`", True)
    ]))

@bot.tree.command(name="remove-timeout", description="✅ Quita el timeout a un miembro")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_remove_timeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(embed=create_cmd_embed("Timeout Removed", [("User", member.mention, True)]))

@bot.tree.command(name="slowmode", description="🐢 Cambia el modo lento (segundos)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_slowmode(interaction: discord.Interaction, seconds: int = 0):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=create_cmd_embed("Slowmode Updated", [
        ("Status", f"`{seconds}s`", True)
    ]))

@bot.tree.command(name="lock", description="🔒 Cierra el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_lock(interaction: discord.Interaction):
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
    await interaction.response.send_message(embed=create_cmd_embed("Channel Locked", [("Channel", interaction.channel.mention, True)], color=C_ERROR))

@bot.tree.command(name="unlock", description="🔓 Abre el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_unlock(interaction: discord.Interaction):
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
    await interaction.response.send_message(embed=create_cmd_embed("Channel Unlocked", [("Channel", interaction.channel.mention, True)]))

@bot.tree.command(name="warn", description="⚠️ Advierte a un miembro")
@app_commands.checks.has_permissions(kick_members=True)
async def cmd_warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.send_message(embed=create_cmd_embed("User Warned", [
        ("User", member.mention, True), ("Reason", reason, True)
    ]))

@bot.tree.command(name="nickname", description="✏️ Cambia el apodo de un miembro")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def cmd_nickname(interaction: discord.Interaction, member: discord.Member, nickname: str = ""):
    await member.edit(nick=nickname or None)
    await interaction.response.send_message(embed=create_cmd_embed("Nickname Changed", [
        ("User", member.mention, True), ("New", nickname or "Reset", True)
    ]))

# ══════════════════════════════════════════════════════════════════
#  🎲 DIVERSIÓN (12 Comandos)
# ══════════════════════════════════════════════════════════════════

_BALL_RESPONSES = [
    "Yes", "No", "Maybe", "Definitely", "Try again", "Ask later",
    "Very likely", "My sources say no", "You wish!", "Certainly"
]

@bot.tree.command(name="8ball", description="🎱 Pregunta a la bola mágica")
async def cmd_8ball(interaction: discord.Interaction, question: str):
    await interaction.response.send_message(embed=create_cmd_embed("🎱 Magic 8-Ball", [
        ("Question", f"`{question}`", False), ("Answer", f"**{random.choice(_BALL_RESPONSES)}**", False)
    ]))

@bot.tree.command(name="coinflip", description="🪙 Lanza una moneda")
async def cmd_coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_cmd_embed("🪙 Coin Flip", [
        ("Result", f"**{random.choice(['Heads', 'Tails'])}**", False)
    ]))

@bot.tree.command(name="dice", description="🎲 Lanza un dado")
async def cmd_dice(interaction: discord.Interaction, sides: int = 6):
    if sides < 2 or sides > 100: return await interaction.response.send_message("2-100 sides.", ephemeral=True)
    await interaction.response.send_message(embed=create_cmd_embed(f"🎲 D{sides} Roll", [
        ("Result", f"`{random.randint(1, sides)}`", False)
    ]))

@bot.tree.command(name="rps", description="✊ Piedra, Papel o Tijeras")
async def cmd_rps(interaction: discord.Interaction, choice: str):
    valid = ["rock", "paper", "scissors"]
    if choice.lower() not in valid: return await interaction.response.send_message("Use `rock`, `paper`, `scissors`.", ephemeral=True)
    bot_pick = random.choice(valid)
    winner = "Tie"
    if (choice.lower() == "rock" and bot_pick == "scissors") or (choice.lower() == "paper" and bot_pick == "rock") or (choice.lower() == "scissors" and bot_pick == "paper"):
        winner = "You won!"
    elif choice.lower() != bot_pick: winner = "You lost!"
    await interaction.response.send_message(embed=create_cmd_embed("✊ RPS", [
        ("You", choice.capitalize(), True), ("Bot", bot_pick.capitalize(), True), ("Result", winner, False)
    ]))

@bot.tree.command(name="meme", description="😂 Meme aleatorio de Reddit")
async def cmd_meme(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://meme-api.com/gimme") as r:
                data = await r.json()
                e = discord.Embed(color=C_GREEN, title=data['title'], url=data['postLink'], timestamp=datetime.now(timezone.utc))
                e.set_author(name="FMD BOT • BYPASS", icon_url="")
                e.set_image(url=data['url'])
                e.set_footer(text=_footer())
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("Meme API error.", ephemeral=True)

@bot.tree.command(name="cat", description="🐱 Foto aleatoria de un gato")
async def cmd_cat(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.thecatapi.com/v1/images/search") as r:
                data = await r.json()
                e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
                e.set_author(name="FMD BOT • BYPASS", icon_url="")
                e.title = f"{EMOJI_GREEN_DOT} Cute Cat"
                e.set_image(url=data[0]['url'])
                e.set_footer(text=_footer())
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="dog", description="🐶 Foto aleatoria de un perro")
async def cmd_dog(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://dog.ceo/api/breeds/image/random") as r:
                data = await r.json()
                e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
                e.set_author(name="FMD BOT • BYPASS", icon_url="")
                e.title = f"{EMOJI_GREEN_DOT} Cute Dog"
                e.set_image(url=data['message'])
                e.set_footer(text=_footer())
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="joke", description="😂 Chiste aleatorio")
async def cmd_joke(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://official-joke-api.appspot.com/random_joke") as r:
                data = await r.json()
                await interaction.followup.send(embed=create_cmd_embed("😂 Joke", [
                    ("Setup", data['setup'], False), ("Punchline", f"**{data['punchline']}**", False)
                ]))
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="trivia", description="🧠 Pregunta de cultura general")
async def cmd_trivia(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://opentdb.com/api.php?amount=1&type=multiple") as r:
                data = await r.json()
                if data['response_code'] != 0:
                    return await interaction.followup.send("No trivia found.", ephemeral=True)
                q = data['results'][0]
                options = q['incorrect_answers'] + [q['correct_answer']]
                random.shuffle(options)
                opts = "\n".join(f"`{i+1}`. {opt}" for i, opt in enumerate(options))
                await interaction.followup.send(embed=create_cmd_embed("🧠 Trivia", [
                    ("Category", q['category'], True), ("Difficulty", q['difficulty'].upper(), True),
                    ("Question", q['question'], False), ("Options", opts, False)
                ]))
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="roast", description="🔥 Quema a un usuario")
async def cmd_roast(interaction: discord.Interaction, member: discord.Member):
    roasts = [
        "You're like a cloud. When you disappear, it's a beautiful day.",
        "Your brain is like a browser. 19 tabs open and all frozen.",
        "I'd agree with you, but then we'd both be wrong."
    ]
    await interaction.response.send_message(embed=create_cmd_embed(f"🔥 Roasting {member.display_name}", [
        ("Roast", f"> {random.choice(roasts)}", False)
    ]))

@bot.tree.command(name="compliment", description="💖 Halaga a un usuario")
async def cmd_compliment(interaction: discord.Interaction, member: discord.Member):
    comps = ["You're amazing!", "You're a ray of sunshine.", "You're doing great!"]
    await interaction.response.send_message(embed=create_cmd_embed(f"💖 Compliment for {member.display_name}", [
        ("Message", f"> {random.choice(comps)}", False)
    ]))

# ══════════════════════════════════════════════════════════════════
#  ❤️ INTERACCIONES DE ANIME (12 Comandos)
# ══════════════════════════════════════════════════════════════════
async def _anime_cmd(interaction: discord.Interaction, action: str, target: discord.Member, endpoint: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://nekos.life/api/v2/img/{endpoint}") as r:
                data = await r.json()
                e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
                e.set_author(name=f"{interaction.user.display_name} {action} {target.display_name}", icon_url=interaction.user.display_avatar.url)
                e.set_image(url=data['url'])
                e.set_footer(text=f"Powered by nekos.life | {_footer()}")
                await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="hug", description="🤗 Abraza a alguien")
async def cmd_hug(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "hugged", member, "hug")

@bot.tree.command(name="kiss", description="💋 Besa a alguien")
async def cmd_kiss(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "kissed", member, "kiss")

@bot.tree.command(name="slap", description="👋 Abofetea a alguien")
async def cmd_slap(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "slapped", member, "slap")

@bot.tree.command(name="pat", description="🖐️ Acaricia a alguien")
async def cmd_pat(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "patted", member, "pat")

@bot.tree.command(name="cuddle", description="🤗 Acúrrucate con alguien")
async def cmd_cuddle(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "cuddled", member, "cuddle")

@bot.tree.command(name="punch", description="👊 Golpea a alguien")
async def cmd_punch(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "punched", member, "punch")

@bot.tree.command(name="bite", description="🦷 Mordisquea a alguien")
async def cmd_bite(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "bit", member, "bite")

@bot.tree.command(name="highfive", description="✋ Choca esos cinco")
async def cmd_highfive(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "highfived", member, "highfive")

@bot.tree.command(name="wink", description="😉 Guiña un ojo")
async def cmd_wink(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "winked at", member, "wink")

@bot.tree.command(name="blush", description="😳 Sonroja a alguien")
async def cmd_blush(interaction: discord.Interaction, member: discord.Member):
    await _anime_cmd(interaction, "made blush", member, "blush")

# ══════════════════════════════════════════════════════════════════
#  🤖 IA Y RECURSOS (6 Comandos)
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="ai-chat", description="🤖 Habla con la IA del bot")
async def cmd_ai_chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
        response = await client.chat.completions.create(model="llama3-8b-8192", messages=[{"role": "user", "content": prompt}], max_tokens=300)
        await interaction.followup.send(embed=create_cmd_embed("🤖 AI Response", [
            ("Prompt", f"`{prompt[:100]}`...", False), ("Response", response.choices[0].message.content[:1900], False)
        ]))
    except ImportError:
        await interaction.followup.send(embed=create_cmd_embed("🤖 AI", [
            ("Result", "`GROQ_API_KEY` missing. Add it in Env.", False)
        ], color=C_WARN))
    except Exception:
        await interaction.followup.send(embed=create_cmd_embed("Error", [("Result", "API Error.", False)], color=C_ERROR))

@bot.tree.command(name="ask-ai", description="❓ Pregunta específica a la IA")
async def cmd_ask_ai(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
        response = await client.chat.completions.create(model="llama3-8b-8192", messages=[{"role": "user", "content": f"Answer concisely: {question}"}], max_tokens=300)
        await interaction.followup.send(embed=create_cmd_embed("❓ AI Answer", [("Answer", response.choices[0].message.content[:1900], False)]))
    except ImportError:
        await interaction.followup.send("Missing `groq` dependency or API key.", ephemeral=True)
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="translate", description="🌐 Traduce texto al inglés")
async def cmd_translate(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://api.mymemory.translated.net/get?q={quote(text)}&langpair=es|en"
            async with s.get(url) as r:
                data = await r.json()
                translation = data['responseData']['translatedText']
                await interaction.followup.send(embed=create_cmd_embed("🌐 Translation (ES->EN)", [
                    ("Original", f"`{text[:500]}`", False), ("Translation", f"`{translation[:500]}`", False)
                ]))
    except Exception:
        await interaction.followup.send("Translation API error.", ephemeral=True)

@bot.tree.command(name="generate-image", description="🎨 Genera una imagen con IA (Pollinations)")
async def cmd_generate_image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    img_url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1024&height=1024&nologo=true"
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} AI Generated Image"
    e.description = f"**Prompt:** {prompt}"
    e.set_image(url=img_url)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e)

@bot.tree.command(name="summarize", description="📋 Resume un texto largo")
async def cmd_summarize(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
        response = await client.chat.completions.create(model="llama3-8b-8192", messages=[{"role": "system", "content": "Summarize this concisely in 3 bullet points."}, {"role": "user", "content": text}], max_tokens=300)
        await interaction.followup.send(embed=create_cmd_embed("📋 Summary", [
            ("Result", response.choices[0].message.content[:1900], False)
        ]))
    except Exception:
        await interaction.followup.send("AI Error. Add GROQ_API_KEY.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  🎮 ROBLOX (4 Comandos)
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="roblox-user", description="🎮 Buscar usuario de Roblox por nombre")
async def cmd_roblox_user(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://users.roblox.com/v1/users/search?keyword={quote(username)}&limit=1") as r:
                data = await r.json()
                if not data['data']: return await interaction.followup.send("User not found.", ephemeral=True)
                u = data['data'][0]
                await interaction.followup.send(embed=create_cmd_embed("🎮 Roblox User", [
                    ("Username", f"`{u['name']}`", True), ("ID", f"`{u['id']}`", True),
                    ("Display", f"`{u['displayName']}`", True)
                ]))
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="roblox-id", description="🎮 Info de Roblox por ID")
async def cmd_roblox_id(interaction: discord.Interaction, user_id: int):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://users.roblox.com/v1/users/{user_id}") as r:
                if r.status != 200: return await interaction.followup.send("ID not found.", ephemeral=True)
                u = await r.json()
                await interaction.followup.send(embed=create_cmd_embed("🎮 Roblox User Info", [
                    ("Username", f"`{u['name']}`", True), ("Display", f"`{u['displayName']}`", True),
                    ("Banned", "Yes" if u['isBanned'] else "No", True)
                ]))
    except Exception:
        await interaction.followup.send("API Error.", ephemeral=True)

@bot.tree.command(name="joinserver", description="🔗 Genera link de un servidor privado")
async def cmd_joinserver(interaction: discord.Interaction, game_id: str, server_code: str):
    link = f"https://www.roblox.com/games/{game_id}?privateServerLinkCode={server_code}"
    await interaction.response.send_message(embed=create_cmd_embed("🔗 Join Server", [
        ("Link", f"[Click here to join]({link})", False)
    ]))

# ══════════════════════════════════════════════════════════════════
#  📊 ESTADÍSTICAS Y HELP
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="stats", description="📊 Estadísticas del bot")
async def cmd_stats(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_cmd_embed("Bot Statistics", [
        ("Servers", f"`{len(bot.guilds)}`", True), ("Users", f"`{sum(g.member_count for g in bot.guilds)}`", True),
        ("Commands", f"`{len(bot.tree.get_commands())}`", True), ("Ping", f"`{round(bot.latency*1000)}ms`", True),
        ("Uptime", f"`{_uptime()}`", False)
    ]))

@bot.tree.command(name="help", description="📖 Ver todos los comandos del bot")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.title = f"{EMOJI_GREEN_DOT} FMD BOT • Commands"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name="🛠️ Utilidad", value="`ping`, `uptime`, `serverinfo`, `userinfo`, `avatar`, `banner`, `roleinfo`, `channelinfo`, `emojiinfo`, `servericon`, `weather`, `math`, `crypto`, `github`, `urban`, `wikipedia`, `random`, `color`, `say`, `embed`", inline=False)
    e.add_field(name="🛡️ Moderación", value="`clear`, `kick`, `ban`, `unban`, `timeout`, `remove-timeout`, `slowmode`, `lock`, `unlock`, `warn`, `nickname`", inline=False)
    e.add_field(name="🎲 Diversión", value="`8ball`, `coinflip`, `dice`, `rps`, `meme`, `cat`, `dog`, `joke`, `trivia`, `roast`, `compliment`", inline=False)
    e.add_field(name="❤️ Anime", value="`hug`, `kiss`, `slap`, `pat`, `cuddle`, `punch`, `bite`, `highfive`, `wink`, `blush`", inline=False)
    e.add_field(name="🤖 IA / Recursos", value="`ai-chat`, `ask-ai`, `translate`, `generate-image`, `summarize`", inline=False)
    e.add_field(name="🎮 Roblox", value="`roblox-user`, `roblox-id`, `joinserver`", inline=False)
    e.add_field(name="🔓 Bypass (API)", value="`/bypass`, `/setautobypass`", inline=False)
    e.add_field(name="📊 Stats", value="`stats`, `help`", inline=False)
    e.set_footer(text=_footer())
    v = View()
    v.add_item(Button(label="Discord", emoji=EMOJI_DISCORD_OBJ, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
    v.add_item(Button(label="Invite", emoji=EMOJI_INVITE_OBJ, url=BOT_INVITE_URL, style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=e, view=v)

# ══════════════════════════════════════════════════════════════════
#  BYPASS SYSTEM (COMANDOS EXISTENTES, NO TOCADOS)
# ══════════════════════════════════════════════════════════════════
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
        e = discord.Embed(title="Auto-Bypass DESACTIVADO", description=f"{interaction.channel.mention} ya no hará bypass automático.", color=C_ERROR)
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, autobypass_channels)
        e = discord.Embed(title="Auto-Bypass ACTIVADO", description=f"Cada enlace en {interaction.channel.mention} será bypasseado automáticamente.", color=C_GREEN)
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ab_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Necesitas permiso de Administrador!", ephemeral=True)

# ── HEALTH SERVER (Para Render) ─────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'{{"status":"online","bot":"FMD BOT","uptime":"{_uptime()}"}}'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_HEAD(self): # Fix para UptimeRobot
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
