import os
import re
import json
import time
import asyncio
import logging
import threading
import random
import html
import string
from datetime import datetime, timezone, timedelta
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
import requests
import aiohttp
from dotenv import load_dotenv
from groq import AsyncGroq

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
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
WEATHER_API_KEY    = os.environ.get("WEATHER_API_KEY", "")

VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"

# ── TUS NUEVOS EMOJIS (Del bloque que pasaste) ────────────────
EMOJIS = {
    "giveaway": "<:giveaway:1526817132501798983>",
    "gift": "<:gift:1526817190660280360>",
    "copy": "<:copy:1526743644894138479>",
    "discord": "<:discord:1526743527642501273>",
    "invite": "<:invite:1526743390488756236>",
    "key": "<:key:1526743159038803978>",
    "green_dot": "<:green_dot:1526742445323190272>",
    "green_crown": "<:green_crown:1526742765311098980>",
    "clock": "<:clock:1525380296852377711>",
    "loader": "<:loader:1526741970226253834>",
    "success": "<:success:1526742163050991616>",
    "error": "❌", 
    "warning": "⚠️"
}

# ── COLORES ──────────────────────────────────────────────────────
C_GREEN  = 0x00FF66
C_WARN   = 0xFFA500
C_ERROR  = 0xED4245

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
                if isinstance(value, str) and value.strip(): return value.strip()
                if isinstance(value, (dict, list)):
                    nested = _extract_bypass_result(value)
                    if nested: return nested
        for value in data.values():
            if isinstance(value, (dict, list)):
                nested = _extract_bypass_result(value)
                if nested: return nested
    elif isinstance(data, list):
        for item in data:
            nested = _extract_bypass_result(item)
            if nested: return nested
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

# ── EMBEDS ──────────────────────────────────────────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJIS['loader']} Generating Bypass..."
    e.description = "Please wait while we process your request."
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif")
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJIS['green_dot']} Bypass Completed"
    e.description = "Generated successfully"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name=f"{EMOJIS['key']} Result", value=f"```txt\n{result[:900]}\n```", inline=False)
    e.add_field(name=f"{EMOJIS['clock']} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name=f"{EMOJIS['success']} Status", value="Successfully Generated", inline=True)
    e.add_field(name="Platform", value=platform, inline=True)
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJIS['green_dot']} Bypass Failed"
    e.description = "Something went wrong!"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name="Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name=f"{EMOJIS['clock']} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name="Platform", value=platform, inline=True)
    e.set_footer(text=_footer())
    return e

# ── VIEW ──────────────────────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        self.add_item(Button(label="Discord", emoji=EMOJIS['discord'], url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Invite", emoji=EMOJIS['invite'], url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(emoji=EMOJIS['copy'], label="Copy", style=discord.ButtonStyle.success, row=0)
    async def copy_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"{EMOJIS['success']} Copied Successfully!", ephemeral=True)

# ── AUTO ELIMINACIÓN ────────────────────────────────────────────
async def start_countdown(message: discord.Message, base_embed: discord.Embed, view: View, seconds: int = 120):
    clock_emoji = EMOJIS['clock']
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
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        
        # Datos para Economía y Moderación
        self.economy_data = self.load_json('data/economy.json')
        self.warnings_data = self.load_json('data/warnings.json')
        self.ai_channels = set()  # Canales con IA automática
        
        # Cliente Groq
        self.groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        
        # Sesión HTTP para APIs
        self.session = aiohttp.ClientSession()

    def load_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info(f"{EMOJIS['success']} Comandos globales sincronizados.")

    async def on_ready(self):
        logger.info("=========================================")
        logger.info(f"{EMOJIS['green_dot']} Bot conectado como {self.user}")
        logger.info(f"{EMOJIS['discord']} En {len(self.guilds)} servidores")
        logger.info("=========================================")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"Con {len(self.guilds)} servers | /help"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        
        # Lógica de IA automática (solo si el canal está configurado)
        if message.channel.id in self.ai_channels and self.groq_client:
            if not message.content.startswith('/'):
                try:
                    async with message.channel.typing():
                        completion = await self.groq_client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Eres un asistente útil y amigable en Discord. Responde de forma concisa y divertida."},
                                {"role": "user", "content": message.content}
                            ],
                            model="llama3-8b-8192",
                            temperature=0.7,
                            max_tokens=150
                        )
                        await message.reply(completion.choices[0].message.content, mention_author=False)
                except Exception as e:
                    logger.error(f"Error en IA: {e}")

        # Auto bypass (tu sistema intacto)
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
#  COMANDOS DE BYPASS (MANTENIDOS)
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
            platform = "PC" # No detectamos plataforma en esta versión simplificada, usamos PC
            embed = embed_success(result, elapsed, platform)
            view = FmdBypassView(result)
            msg = await interaction.edit_original_response(embed=embed, view=view)
            asyncio.create_task(start_countdown(msg, embed, view))
        else:
            platform = "PC"
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

# ══════════════════════════════════════════════════════════════════
#  COMANDOS DE UTILIDAD / BÁSICOS (Del bloque nuevo)
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="help", description="Muestra el menú de ayuda completo")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{EMOJIS['green_crown']} Menú de Ayuda", color=0x5865F2)
    categories = {
        "🟢 Básicos": "/ping, /botinfo, /avatar, /serverinfo, /userinfo, /invite, /suggest",
        "🎉 Diversión": "/meme, /chiste, /8ball, /dado, /moneda, /ship, /roast, /compliment, /choose, /rps, /trivia, /math, /slot",
        "🛡️ Moderación": "/ban, /kick, /timeout, /warn, /warnings, /clearwarns, /limpiar, /slowmode, /lock, /unlock, /nuke",
        "💰 Economía": "/balance, /daily, /work, /beg, /rob, /dep, /with, /shop, /buy, /inventory, /leaderboard, /give",
        "🖼️ Imágenes": "/dog, /cat, /fox, /panda, /duck, /waifu, /neko",
        "⚙️ Utilidad": "/weather, /translate, /define, /calc, /qr, /poll, /github, /ip, /password, /setupia",
        "🤖 IA": "/chat (IA manual), /setupia (Auto-respuesta)"
    }
    for cat, cmds in categories.items():
        embed.add_field(name=cat, value=cmds, inline=False)
    embed.set_footer(text=f"Solicitado por {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Verifica la latencia del bot")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} Pong!", color=0x00ff00)
    embed.add_field(name="Latencia API", value=f"{latency}ms", inline=True)
    embed.add_field(name="WebSocket", value=f"{round(bot.latency*1000)}ms", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="botinfo", description="Información detallada del bot")
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{EMOJIS['discord']} Info del Bot", color=0x5865F2)
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)
    embed.add_field(name="📛 Nombre", value=bot.user.name, inline=True)
    embed.add_field(name="🆔 ID", value=bot.user.id, inline=True)
    embed.add_field(name="📊 Servidores", value=len(bot.guilds), inline=True)
    embed.add_field(name="👥 Usuarios", value=len(bot.users), inline=True)
    embed.add_field(name="🐍 Python", value="3.10+", inline=True)
    embed.add_field(name="📦 Librería", value="discord.py", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Muestra el avatar de un usuario")
async def avatar(interaction: discord.Interaction, user: discord.User = None):
    user = user or interaction.user
    embed = discord.Embed(title=f"{EMOJIS['copy']} Avatar de {user.name}", color=user.color if user.color else 0x5865F2)
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Información completa del servidor")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"{EMOJIS['green_crown']} {guild.name}", color=0x5865F2)
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👑 Dueño", value=guild.owner.mention if guild.owner else "Desconocido", inline=True)
    embed.add_field(name="👥 Miembros", value=guild.member_count, inline=True)
    embed.add_field(name="📝 Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="💬 Canales", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 Emojis", value=len(guild.emojis), inline=True)
    embed.add_field(name="📅 Creado", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Información de un usuario")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} Info de {user.name}", color=user.color if user.color else 0x5865F2)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="🆔 ID", value=user.id, inline=True)
    embed.add_field(name="📛 Nick", value=user.display_name, inline=True)
    embed.add_field(name="🤖 ¿Bot?", value="Sí" if user.bot else "No", inline=True)
    embed.add_field(name="📅 Cuenta creada", value=user.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📥 Se unió", value=user.joined_at.strftime("%d/%m/%Y") if user.joined_at else "N/A", inline=True)
    roles = [r.mention for r in user.roles[1:]]
    embed.add_field(name="🎭 Roles", value=", ".join(roles[:10]) or "Ninguno", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Invita al bot a tu servidor")
async def invite(interaction: discord.Interaction):
    url = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(8))
    embed = discord.Embed(title=f"{EMOJIS['invite']} Invitar al Bot", description=f"[Click aquí para invitar]({url})", color=0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="suggest", description="Envía una sugerencia al dueño")
async def suggest(interaction: discord.Interaction, suggestion: str):
    owner_id = int(os.environ.get("OWNER_ID", "0"))
    owner = bot.get_user(owner_id)
    if owner:
        embed = discord.Embed(title=f"{EMOJIS['gift']} Nueva Sugerencia", color=0xffaa00)
        embed.add_field(name="Usuario", value=interaction.user.mention, inline=True)
        embed.add_field(name="Servidor", value=interaction.guild.name, inline=True)
        embed.add_field(name="Sugerencia", value=suggestion, inline=False)
        try:
            await owner.send(embed=embed)
            await interaction.response.send_message(f"{EMOJIS['success']} Sugerencia enviada correctamente.", ephemeral=True)
        except:
            await interaction.response.send_message(f"{EMOJIS['error']} No pude enviar la sugerencia al dueño.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{EMOJIS['error']} El dueño no está configurado. Agrega OWNER_ID al .env", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  🎉 DIVERSIÓN
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="meme", description="Meme random de Reddit")
async def meme(interaction: discord.Interaction):
    subreddits = ['memes', 'dankmemes', 'me_irl']
    sub = random.choice(subreddits)
    async with bot.session.get(f'https://www.reddit.com/r/{sub}/random/.json') as resp:
        data = await resp.json()
    post = data[0]['data']['children'][0]['data']
    embed = discord.Embed(title=post['title'], color=0xff5700)
    embed.set_image(url=post['url'])
    embed.set_footer(text=f"👍 {post['ups']} | r/{sub}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="chiste", description="Chiste random en español")
async def chiste(interaction: discord.Interaction):
    async with bot.session.get('https://v2.jokeapi.dev/joke/Any?lang=es&type=single') as resp:
        data = await resp.json()
    await interaction.response.send_message(data.get('joke', 'No encontré chiste 😢'))

@bot.tree.command(name="8ball", description="Bola mágica 8")
async def eightball(interaction: discord.Interaction, pregunta: str):
    respuestas = ["Sí, definitivamente", "Sin duda", "Probablemente", "Pregunta de nuevo", "No cuentes con ello", "Muy dudoso"]
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} Bola 8", color=0x000000)
    embed.add_field(name="Pregunta", value=pregunta, inline=False)
    embed.add_field(name="Respuesta", value=random.choice(respuestas), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dado", description="Lanza un dado")
async def dado(interaction: discord.Interaction):
    resultado = random.randint(1, 6)
    emojis_dado = {1:'⚀', 2:'⚁', 3:'⚂', 4:'⚃', 5:'⚄', 6:'⚅'}
    await interaction.response.send_message(f"{emojis_dado[resultado]} ¡Sacaste un **{resultado}**!")

@bot.tree.command(name="moneda", description="Cara o cruz")
async def moneda(interaction: discord.Interaction):
    resultado = random.choice(['Cara', 'Cruz'])
    await interaction.response.send_message(f"🪙 ¡Salió **{resultado}**!")

@bot.tree.command(name="ship", description="Compatibilidad entre 2 usuarios")
async def ship(interaction: discord.Interaction, user1: discord.User, user2: discord.User):
    porcentaje = random.randint(0, 100)
    emoji = '💔' if porcentaje < 30 else '💛' if porcentaje < 70 else '❤️'
    embed = discord.Embed(title=f"{emoji} Ship Calculator", color=0xff69b4)
    embed.add_field(name="Pareja", value=f"{user1.name} + {user2.name}", inline=False)
    embed.add_field(name="Compatibilidad", value=f"{porcentaje}%", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roast", description="Roastea a alguien")
async def roast(interaction: discord.Interaction, user: discord.User):
    roasts = ["Eres la razón por la que el shampoo tiene instrucciones.", "Si fueras más aburrido, estarías en el diccionario.", "Tu cara es como si alguien hubiera hecho ctrl+Z en la vida real.", "Eres como un día nublado: nadie te espera con alegría."]
    await interaction.response.send_message(f"{user.mention}, {random.choice(roasts)} 🔥")

@bot.tree.command(name="compliment", description="Elogia a alguien")
async def compliment(interaction: discord.Interaction, user: discord.User):
    compliments = ["¡Tu sonrisa ilumina cualquier habitación!", "Eres más genial que el otro lado de la almohada.", "El mundo es mejor lugar porque tú estás en él.", "Tienes el corazón de oro."]
    await interaction.response.send_message(f"{user.mention}, {random.choice(compliments)} ✨")

@bot.tree.command(name="choose", description="Elige entre opciones")
async def choose(interaction: discord.Interaction, opciones: str):
    lista = [o.strip() for o in opciones.split(',')]
    if len(lista) < 2:
        return await interaction.response.send_message(f"{EMOJIS['error']} Dame al menos 2 opciones separadas por comas", ephemeral=True)
    await interaction.response.send_message(f"🎯 Elijo: **{random.choice(lista)}**")

@bot.tree.command(name="rps", description="Piedra, papel o tijera")
async def rps(interaction: discord.Interaction, eleccion: str):
    opciones = ['piedra', 'papel', 'tijera']
    if eleccion.lower() not in opciones:
        return await interaction.response.send_message(f"{EMOJIS['error']} Elige: piedra, papel o tijera", ephemeral=True)
    bot_choice = random.choice(opciones)
    emojis_rps = {'piedra': '🪨', 'papel': '📄', 'tijera': '✂️'}
    if eleccion.lower() == bot_choice: resultado = "🤝 Empate"
    elif (eleccion.lower() == 'piedra' and bot_choice == 'tijera') or (eleccion.lower() == 'papel' and bot_choice == 'piedra') or (eleccion.lower() == 'tijera' and bot_choice == 'papel'):
        resultado = "✅ ¡Ganaste!"
    else:
        resultado = "❌ Perdiste"
    await interaction.response.send_message(f"Tú: {emojis_rps[eleccion.lower()]} | Bot: {emojis_rps[bot_choice]}\n{resultado}")

@bot.tree.command(name="trivia", description="Pregunta de trivia")
async def trivia(interaction: discord.Interaction):
    async with bot.session.get('https://opentdb.com/api.php?amount=1') as resp:
        data = await resp.json()
    q = data['results'][0]
    pregunta = html.unescape(q['question'])
    opciones = q['incorrect_answers'] + [q['correct_answer']]
    random.shuffle(opciones)
    opciones = [html.unescape(o) for o in opciones]
    embed = discord.Embed(title=f"{EMOJIS['green_crown']} Trivia", description=pregunta, color=0x5865F2)
    embed.add_field(name="Opciones", value='\n'.join([f"{i+1}. {o}" for i, o in enumerate(opciones)]))
    await interaction.response.send_message(embed=embed)
    def check(m): return m.author == interaction.user and m.channel.id == interaction.channel.id and m.content.isdigit() and 1 <= int(m.content) <= 4
    try:
        msg = await bot.wait_for('message', timeout=30, check=check)
        respuesta_usuario = opciones[int(msg.content) - 1]
        respuesta_correcta = html.unescape(q['correct_answer'])
        if respuesta_usuario == respuesta_correcta:
            await msg.reply(f"{EMOJIS['success']} ¡Correcto!")
        else:
            await msg.reply(f"{EMOJIS['error']} Incorrecto. Era: {respuesta_correcta}")
    except asyncio.TimeoutError:
        await interaction.followup.send(f"{EMOJIS['clock']} Se acabó el tiempo")

@bot.tree.command(name="math", description="Desafío matemático")
async def math(interaction: discord.Interaction):
    a, b = random.randint(1, 50), random.randint(1, 50)
    op = random.choice(['+', '-', '*'])
    if op == '+': respuesta = a + b
    elif op == '-': respuesta = a - b
    else: respuesta = a * b
    await interaction.response.send_message(f"🧮 ¿Cuánto es **{a} {op} {b}**?")
    def check(m): return m.author == interaction.user and m.channel.id == interaction.channel.id
    try:
        msg = await bot.wait_for('message', timeout=30, check=check)
        if msg.content == str(respuesta):
            await msg.reply(f"{EMOJIS['success']} ¡Correcto!")
        else:
            await msg.reply(f"{EMOJIS['error']} Incorrecto. Era {respuesta}")
    except asyncio.TimeoutError:
        await interaction.followup.send(f"{EMOJIS['clock']} Tiempo. Era {respuesta}")

@bot.tree.command(name="slot", description="Máquina tragamonedas")
async def slot(interaction: discord.Interaction):
    symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    r1, r2, r3 = random.choices(symbols, k=3)
    resultado = f"| {r1} | {r2} | {r3} |"
    if r1 == r2 == r3: msg = f"🎰 {resultado}\n{EMOJIS['green_crown']} ¡JACKPOT!"
    elif r1 == r2 or r2 == r3 or r1 == r3: msg = f"🎰 {resultado}\n✨ ¡Casi!"
    else: msg = f"🎰 {resultado}\n😢 Sigue intentando"
    await interaction.response.send_message(msg)

# ══════════════════════════════════════════════════════════════════
#  🛡️ MODERACIÓN
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="ban", description="Banea a un usuario")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, razon: str = "Sin razón"):
    if user.top_role >= interaction.user.top_role:
        return await interaction.response.send_message(f"{EMOJIS['error']} No puedes banear a alguien con rol igual o superior", ephemeral=True)
    try:
        await user.ban(reason=razon)
        embed = discord.Embed(title=f"{EMOJIS['green_dot']} Usuario Baneado", color=0xff0000)
        embed.add_field(name="Usuario", value=user.mention)
        embed.add_field(name="Moderador", value=interaction.user.mention)
        embed.add_field(name="Razón", value=razon)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(f"{EMOJIS['error']} No tengo permisos para banear.", ephemeral=True)

@bot.tree.command(name="kick", description="Expulsa a un usuario")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, razon: str = "Sin razón"):
    try:
        await user.kick(reason=razon)
        await interaction.response.send_message(f"{EMOJIS['green_dot']} {user.mention} fue expulsado. Razón: {razon}")
    except discord.Forbidden:
        await interaction.response.send_message(f"{EMOJIS['error']} No tengo permisos.", ephemeral=True)

@bot.tree.command(name="timeout", description="Silencia temporalmente")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, user: discord.Member, minutos: int, razon: str = "Sin razón"):
    try:
        await user.timeout(timedelta(minutes=minutos), reason=razon)
        await interaction.response.send_message(f"{EMOJIS['green_dot']} {user.mention} silenciado por {minutos} minutos")
    except discord.Forbidden:
        await interaction.response.send_message(f"{EMOJIS['error']} No tengo permisos.", ephemeral=True)

@bot.tree.command(name="warn", description="Advierte a un usuario")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, user: discord.Member, razon: str):
    uid = str(user.id)
    if uid not in bot.warnings_data:
        bot.warnings_data[uid] = []
    bot.warnings_data[uid].append({'mod': interaction.user.id, 'reason': razon, 'date': datetime.now().isoformat()})
    bot.save_json('data/warnings.json', bot.warnings_data)
    await interaction.response.send_message(f"{EMOJIS['warning']} {user.mention} advertido: {razon}")

@bot.tree.command(name="warnings", description="Ver advertencias de un usuario")
async def warnings(interaction: discord.Interaction, user: discord.Member):
    warns = bot.warnings_data.get(str(user.id), [])
    if not warns:
        return await interaction.response.send_message(f"{EMOJIS['success']} {user.mention} no tiene advertencias")
    embed = discord.Embed(title=f"{EMOJIS['warning']} Advertencias de {user.name}", color=0xffaa00)
    for i, w in enumerate(warns, 1):
        embed.add_field(name=f"#{i}", value=w['reason'], inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarns", description="Borra advertencias")
@app_commands.checks.has_permissions(moderate_members=True)
async def clearwarns(interaction: discord.Interaction, user: discord.Member):
    bot.warnings_data.pop(str(user.id), None)
    bot.save_json('data/warnings.json', bot.warnings_data)
    await interaction.response.send_message(f"{EMOJIS['success']} Advertencias de {user.mention} borradas")

@bot.tree.command(name="limpiar", description="Borra mensajes")
@app_commands.checks.has_permissions(manage_messages=True)
async def limpiar(interaction: discord.Interaction, cantidad: int = 10):
    if cantidad > 100:
        return await interaction.response.send_message(f"{EMOJIS['error']} Máximo 100 mensajes", ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=cantidad+1)
        await interaction.response.send_message(f"{EMOJIS['success']} {len(deleted)-1} mensajes borrados", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"{EMOJIS['error']} No tengo permisos para borrar mensajes.", ephemeral=True)

@bot.tree.command(name="slowmode", description="Cambia el slowmode")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, segundos: int):
    await interaction.channel.edit(slowmode_delay=segundos)
    await interaction.response.send_message(f"{EMOJIS['clock']} Slowmode: {segundos}s")

@bot.tree.command(name="lock", description="Bloquea el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(f"{EMOJIS['green_dot']} Canal bloqueado")

@bot.tree.command(name="unlock", description="Desbloquea el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(f"{EMOJIS['green_dot']} Canal desbloqueado")

@bot.tree.command(name="nuke", description="Clona y borra el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def nuke(interaction: discord.Interaction):
    position = interaction.channel.position
    try:
        nuevo = await interaction.channel.clone()
        await interaction.channel.delete()
        await nuevo.edit(position=position)
        await nuevo.send(f"{EMOJIS['green_dot']} ¡Canal nuked!")
    except discord.Forbidden:
        await interaction.response.send_message(f"{EMOJIS['error']} No tengo permisos.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  💰 ECONOMÍA
# ══════════════════════════════════════════════════════════════════

def get_economy_user(uid):
    if str(uid) not in bot.economy_data:
        bot.economy_data[str(uid)] = {'wallet': 0, 'bank': 0, 'inventory': [], 'last_daily': 0, 'last_work': 0}
        bot.save_json('data/economy.json', bot.economy_data)
    return bot.economy_data[str(uid)]

@bot.tree.command(name="balance", description="Ver tu saldo")
async def balance(interaction: discord.Interaction, user: discord.User = None):
    user = user or interaction.user
    data = get_economy_user(user.id)
    embed = discord.Embed(title=f"{EMOJIS['green_crown']} Balance de {user.name}", color=0xffd700)
    embed.add_field(name="💵 Cartera", value=f"${data['wallet']}", inline=True)
    embed.add_field(name="🏦 Banco", value=f"${data['bank']}", inline=True)
    embed.add_field(name="💎 Total", value=f"${data['wallet'] + data['bank']}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Recompensa diaria")
async def daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    data = get_economy_user(uid)
    now = time.time()
    if now - data['last_daily'] < 86400:
        horas_restantes = int((86400 - (now - data['last_daily'])) / 3600)
        return await interaction.response.send_message(f"{EMOJIS['clock']} Vuelve en {horas_restantes}h", ephemeral=True)
    amount = random.randint(100, 500)
    data['wallet'] += amount
    data['last_daily'] = now
    bot.save_json('data/economy.json', bot.economy_data)
    await interaction.response.send_message(f"{EMOJIS['success']} ¡Recibiste ${amount}!")

@bot.tree.command(name="work", description="Trabaja por monedas")
async def work(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    data = get_economy_user(uid)
    now = time.time()
    if now - data['last_work'] < 3600:
        mins = int((3600 - (now - data['last_work'])) / 60)
        return await interaction.response.send_message(f"{EMOJIS['clock']} Espera {mins} min", ephemeral=True)
    trabajos = ['Programador', 'Youtuber', 'Cajero', 'Médico', 'Chef']
    amount = random.randint(50, 200)
    data['wallet'] += amount
    data['last_work'] = now
    bot.save_json('data/economy.json', bot.economy_data)
    await interaction.response.send_message(f"{EMOJIS['success']} Trabajaste como {random.choice(trabajos)} y ganaste ${amount}")

@bot.tree.command(name="beg", description="Pide limosna")
async def beg(interaction: discord.Interaction):
    if random.random() < 0.4:
        amount = random.randint(1, 50)
        data = get_economy_user(interaction.user.id)
        data['wallet'] += amount
        bot.save_json('data/economy.json', bot.economy_data)
        await interaction.response.send_message(f"{EMOJIS['success']} Alguien te dio ${amount}")
    else:
        await interaction.response.send_message(f"{EMOJIS['error']} Nadie te dio nada")

@bot.tree.command(name="rob", description="Roba a otro usuario")
async def rob(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        return await interaction.response.send_message(f"{EMOJIS['error']} No puedes robarte a ti mismo", ephemeral=True)
    victim = get_economy_user(user.id)
    thief = get_economy_user(interaction.user.id)
    if victim['wallet'] < 100:
        return await interaction.response.send_message(f"{EMOJIS['error']} Ese usuario no tiene suficiente", ephemeral=True)
    if random.random() < 0.5:
        amount = random.randint(50, victim['wallet'])
        victim['wallet'] -= amount
        thief['wallet'] += amount
        bot.save_json('data/economy.json', bot.economy_data)
        await interaction.response.send_message(f"{EMOJIS['success']} ¡Robaste ${amount} a {user.mention}!")
    else:
        amount = random.randint(50, 200)
        thief['wallet'] = max(0, thief['wallet'] - amount)
        bot.save_json('data/economy.json', bot.economy_data)
        await interaction.response.send_message(f"{EMOJIS['error']} ¡Te atraparon! Pagaste ${amount}")

@bot.tree.command(name="dep", description="Deposita al banco")
async def dep(interaction: discord.Interaction, cantidad: int):
    data = get_economy_user(interaction.user.id)
    if cantidad > data['wallet']:
        return await interaction.response.send_message(f"{EMOJIS['error']} No tienes suficiente", ephemeral=True)
    data['wallet'] -= cantidad
    data['bank'] += cantidad
    bot.save_json('data/economy.json', bot.economy_data)
    await interaction.response.send_message(f"{EMOJIS['success']} Depositaste ${cantidad}")

@bot.tree.command(name="with", description="Retira del banco")
async def withdraw(interaction: discord.Interaction, cantidad: int):
    data = get_economy_user(interaction.user.id)
    if cantidad > data['bank']:
        return await interaction.response.send_message(f"{EMOJIS['error']} No tienes suficiente en el banco", ephemeral=True)
    data['bank'] -= cantidad
    data['wallet'] += cantidad
    bot.save_json('data/economy.json', bot.economy_data)
    await interaction.response.send_message(f"{EMOJIS['success']} Retiraste ${cantidad}")

@bot.tree.command(name="shop", description="Tienda del servidor")
async def shop(interaction: discord.Interaction):
    items = {'🎮 Consola': 1000, '📱 Celular': 500, '💻 Laptop': 2000, '🚗 Auto': 5000, '🏠 Casa': 10000}
    embed = discord.Embed(title=f"{EMOJIS['gift']} Tienda", color=0xffd700)
    for item, price in items.items():
        embed.add_field(name=item, value=f"${price}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Compra un item")
async def buy(interaction: discord.Interaction, item: str):
    items_map = {'consola': 1000, 'celular': 500, 'laptop': 2000, 'auto': 5000, 'casa': 10000}
    item_lower = item.lower()
    if item_lower not in items_map:
        return await interaction.response.send_message(f"{EMOJIS['error']} Item no existe. Usa /shop", ephemeral=True)
    data = get_economy_user(interaction.user.id)
    if data['wallet'] < items_map[item_lower]:
        return await interaction.response.send_message(f"{EMOJIS['error']} No tienes suficiente dinero", ephemeral=True)
    data['wallet'] -= items_map[item_lower]
    data['inventory'].append(item_lower)
    bot.save_json('data/economy.json', bot.economy_data)
    await interaction.response.send_message(f"{EMOJIS['success']} Compraste {item_lower}")

@bot.tree.command(name="inventory", description="Ver inventario")
async def inventory(interaction: discord.Interaction):
    data = get_economy_user(interaction.user.id)
    inv = data['inventory']
    if not inv:
        return await interaction.response.send_message(f"{EMOJIS['error']} Tu inventario está vacío")
    counts = Counter(inv)
    items_str = '\n'.join([f"{item} x{count}" for item, count in counts.items()])
    embed = discord.Embed(title=f"{EMOJIS['gift']} Inventario", description=items_str, color=0xffd700)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Top de usuarios ricos")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(bot.economy_data.items(), key=lambda x: x[1]['wallet'] + x[1]['bank'], reverse=True)[:10]
    embed = discord.Embed(title=f"{EMOJIS['green_crown']} Leaderboard", color=0xffd700)
    for i, (uid, data) in enumerate(sorted_users, 1):
        total = data['wallet'] + data['bank']
        embed.add_field(name=f"#{i}", value=f"<@{uid}> - ${total}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="give", description="Da dinero a otro usuario")
async def give(interaction: discord.Interaction, user: discord.User, cantidad: int):
    if cantidad <= 0:
        return await interaction.response.send_message(f"{EMOJIS['error']} Cantidad inválida", ephemeral=True)
    giver = get_economy_user(interaction.user.id)
    if giver['wallet'] < cantidad:
        return await interaction.response.send_message(f"{EMOJIS['error']} No tienes suficiente", ephemeral=True)
    giver['wallet'] -= cantidad
    receiver = get_economy_user(user.id)
    receiver['wallet'] += cantidad
    bot.save_json('data/economy.json', bot.economy_data)
    await interaction.response.send_message(f"{EMOJIS['success']} Le diste ${cantidad} a {user.mention}")

# ══════════════════════════════════════════════════════════════════
#  🖼️ IMÁGENES
# ══════════════════════════════════════════════════════════════════

async def send_animal_image(interaction, api_url, key_path, title, emoji):
    try:
        async with bot.session.get(api_url) as resp:
            data = await resp.json()
        if 'file' in data: img_url = data['file']
        elif 'image' in data: img_url = data['image']
        elif 'link' in data: img_url = data['link']
        elif 'url' in data: img_url = data['url']
        else: img_url = data[0]['url']
        embed = discord.Embed(title=f"{emoji} {title}", color=0x00ffcc)
        embed.set_image(url=img_url)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJIS['error']} Error al cargar imagen: {e}", ephemeral=True)

@bot.tree.command(name="dog", description="Foto de perro")
async def dog(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://dog.ceo/api/breeds/image/random', 'url', 'Perro', '🐶')

@bot.tree.command(name="cat", description="Foto de gato")
async def cat(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://api.thecatapi.com/v1/images/search', 'url', 'Gato', '🐱')

@bot.tree.command(name="fox", description="Foto de zorro")
async def fox(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://randomfox.ca/floof/', 'image', 'Zorro', '🦊')

@bot.tree.command(name="panda", description="Foto de panda")
async def panda(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://some-random-api.com/img/panda', 'link', 'Panda', '🐼')

@bot.tree.command(name="duck", description="Foto de pato")
async def duck(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://random-d.uk/api/random', 'url', 'Pato', '🦆')

@bot.tree.command(name="waifu", description="Imagen anime waifu")
async def waifu(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://api.waifu.pics/sfw/waifu', 'url', 'Waifu', '💕')

@bot.tree.command(name="neko", description="Imagen neko")
async def neko(interaction: discord.Interaction):
    await send_animal_image(interaction, 'https://api.waifu.pics/sfw/neko', 'url', 'Neko', '🐾')

# ══════════════════════════════════════════════════════════════════
#  ⚙️ UTILIDAD E IA
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="weather", description="Clima de una ciudad")
async def weather(interaction: discord.Interaction, ciudad: str):
    if WEATHER_API_KEY:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={WEATHER_API_KEY}&units=metric&lang=es"
        async with bot.session.get(url) as resp:
            data = await resp.json()
        if data['cod'] != 200:
            return await interaction.response.send_message(f"{EMOJIS['error']} Ciudad no encontrada", ephemeral=True)
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        humidity = data['main']['humidity']
        desc = data['weather'][0]['description']
        embed = discord.Embed(title=f"{EMOJIS['green_dot']} Clima en {ciudad}", color=0x00bfff)
        embed.add_field(name="🌡️ Temp", value=f"{temp}°C", inline=True)
        embed.add_field(name="🌡️ Sensación", value=f"{feels_like}°C", inline=True)
        embed.add_field(name="💧 Humedad", value=f"{humidity}%", inline=True)
        embed.add_field(name="☁️ Descripción", value=desc.capitalize(), inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"{EMOJIS['warning']} Configura WEATHER_API_KEY para datos precisos.", ephemeral=True)

@bot.tree.command(name="translate", description="Traduce texto (Español <-> Inglés)")
async def translate(interaction: discord.Interaction, texto: str, idioma: str = 'en'):
    # Ejemplo conceptual. Se puede usar API de MyMemory si se desea.
    await interaction.response.send_message(f"{EMOJIS['warning']} La traducción requiere configuración avanzada. Texto recibido: {texto}", ephemeral=True)

@bot.tree.command(name="define", description="Define una palabra en inglés")
async def define(interaction: discord.Interaction, palabra: str):
    async with bot.session.get(f'https://api.dictionaryapi.dev/api/v2/entries/en/{palabra}') as resp:
        if resp.status != 200:
            return await interaction.response.send_message(f"{EMOJIS['error']} Palabra no encontrada", ephemeral=True)
        data = await resp.json()
    meaning = data[0]['meanings'][0]
    definition = meaning['definitions'][0]['definition']
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} {palabra}", description=definition, color=0x5865F2)
    embed.add_field(name="Tipo", value=meaning['partOfSpeech'], inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="calc", description="Calculadora segura")
async def calc(interaction: discord.Interaction, expresion: str):
    allowed = set('0123456789+-*/.() ')
    if not all(c in allowed for c in expresion):
        return await interaction.response.send_message(f"{EMOJIS['error']} Expresión inválida", ephemeral=True)
    try:
        resultado = eval(expresion)
        await interaction.response.send_message(f"🧮 `{expresion}` = **{resultado}**")
    except:
        await interaction.response.send_message(f"{EMOJIS['error']} Error en la expresión", ephemeral=True)

@bot.tree.command(name="qr", description="Genera código QR")
async def qr(interaction: discord.Interaction, texto: str):
    url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={texto}'
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} Código QR", color=0x000000)
    embed.set_image(url=url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="poll", description="Crea una encuesta rápida")
async def poll(interaction: discord.Interaction, pregunta: str, opciones: str):
    lista = [o.strip() for o in opciones.split(',')]
    if len(lista) < 2 or len(lista) > 10:
        return await interaction.response.send_message(f"{EMOJIS['error']} Entre 2 y 10 opciones", ephemeral=True)
    emojis_num = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} {pregunta}", color=0x5865F2)
    for i, op in enumerate(lista):
        embed.add_field(name=f"{emojis_num[i]} {op}", value="‎", inline=False)
    msg = await interaction.response.send_message(embed=embed)
    original_msg = await interaction.original_response()
    for i in range(len(lista)):
        await original_msg.add_reaction(emojis_num[i])

@bot.tree.command(name="github", description="Info de usuario GitHub")
async def github(interaction: discord.Interaction, user: str):
    async with bot.session.get(f'https://api.github.com/users/{user}') as resp:
        if resp.status != 200:
            return await interaction.response.send_message(f"{EMOJIS['error']} Usuario no encontrado", ephemeral=True)
        data = await resp.json()
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} {data['login']}", url=data['html_url'], color=0x000000)
    if data['avatar_url']: embed.set_thumbnail(url=data['avatar_url'])
    embed.add_field(name="📝 Bio", value=data.get('bio') or 'N/A', inline=False)
    embed.add_field(name="👥 Seguidores", value=data['followers'], inline=True)
    embed.add_field(name="👤 Siguiendo", value=data['following'], inline=True)
    embed.add_field(name="📦 Repos", value=data['public_repos'], inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ip", description="Info de una IP pública")
async def ip(interaction: discord.Interaction, ip: str = None):
    if not ip:
        async with bot.session.get('https://api.ipify.org?format=json') as resp:
            data_ip = await resp.json()
            ip = data_ip['ip']
    async with bot.session.get(f'http://ip-api.com/json/{ip}') as resp:
        data = await resp.json()
    if data['status'] == 'fail':
        return await interaction.response.send_message(f"{EMOJIS['error']} IP inválida o privada", ephemeral=True)
    embed = discord.Embed(title=f"{EMOJIS['green_dot']} Info de {ip}", color=0x5865F2)
    embed.add_field(name="🏙️ Ciudad", value=data.get('city', 'N/A'), inline=True)
    embed.add_field(name="🗺️ País", value=data.get('country', 'N/A'), inline=True)
    embed.add_field(name="📍 Región", value=data.get('regionName', 'N/A'), inline=True)
    embed.add_field(name="🕐 Zona", value=data.get('timezone', 'N/A'), inline=True)
    embed.add_field(name="🌐 ISP", value=data.get('isp', 'N/A'), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="password", description="Genera contraseña segura")
async def password(interaction: discord.Interaction, longitud: int = 16):
    chars = string.ascii_letters + string.digits + string.punctuation
    pwd = ''.join(random.choices(chars, k=longitud))
    await interaction.response.send_message(f"{EMOJIS['green_dot']} Contraseña generada:\n`{pwd}`", ephemeral=True)

@bot.tree.command(name="setupia", description="Configura IA automática en este canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def setupia(interaction: discord.Interaction):
    if not bot.groq_client:
        return await interaction.response.send_message(f"{EMOJIS['error']} La API de Groq no está configurada.", ephemeral=True)
    channel_id = interaction.channel.id
    if channel_id in bot.ai_channels:
        bot.ai_channels.remove(channel_id)
        await interaction.response.send_message(f"{EMOJIS['warning']} IA desactivada en este canal.")
    else:
        bot.ai_channels.add(channel_id)
        await interaction.response.send_message(f"{EMOJIS['success']} IA activada en este canal. Ahora responderé automáticamente a los mensajes.")

@bot.tree.command(name="chat", description="Habla con la IA manualmente")
async def chat(interaction: discord.Interaction, mensaje: str):
    if not bot.groq_client:
        return await interaction.response.send_message(f"{EMOJIS['error']} La API de Groq no está configurada.", ephemeral=True)
    await interaction.response.defer()
    try:
        completion = await bot.groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un asistente útil en Discord."},
                {"role": "user", "content": mensaje}
            ],
            model="llama3-8b-8192",
            temperature=0.7,
            max_tokens=200
        )
        embed = discord.Embed(title=f"{EMOJIS['green_dot']} IA Response", description=completion.choices[0].message.content, color=0x5865F2)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"{EMOJIS['error']} Error en la IA: {e}", ephemeral=True)

# ── HEALTH SERVER (Para Render) ─────────────────────────────────
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
