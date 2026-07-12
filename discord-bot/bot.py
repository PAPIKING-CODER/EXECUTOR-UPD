"""
KING BOT — Bypass + Fun Commands
"""
import sys, types

try:
    import audioop
except ImportError:
    sys.modules["audioop"] = types.ModuleType("audioop")

import os, re, json, time, asyncio, logging, threading, random, string, ast, operator, base64, hashlib
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
import requests

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

# ── LOGGING ──────────────────────────────────────────────────────
logger = logging.getLogger("KING")
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
    "https://discord.com/oauth2/authorize?client_id=1525040833814855710")

BOT_NAME   = "KING BOT"
BOT_CREDIT = "BY KING"
# Palabra que activa los comandos por texto, ej: "king afk", "king ping".
# Cambialo con la variable de entorno BOT_TRIGGER si quieres otra palabra.
BOT_TRIGGER = os.environ.get("BOT_TRIGGER", "king")

BYPASS_API_URL = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT = 30
BYPASS_RETRIES = 3
BYPASS_DELAY   = 3

AUTOBYPASS_FILE = "autobypass_channels.json"

# ── TICKETS ──────────────────────────────────────────────────────
TICKET_CONFIG_FILE = "ticket_config.json"
TICKET_COUNTER_FILE = "ticket_counter.json"

# ── COLORES ──────────────────────────────────────────────────────
C_RED   = 0xC80000   # rojo oscuro principal
C_DARK  = 0x1A0000   # casi negro con tono rojo
C_WARN  = 0xFF4500   # rojo-naranja para loading
C_INFO  = 0x8B0000   # rojo profundo

# ── IMAGEN PRINCIPAL ─────────────────────────────────────────────
IMG_MAIN = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a5485bb&is=6a53343b&hm=f6df69c459c7bad9ed031d12eee35f42ab4adbb7290fe08a3707046eb3bf7200&"

# ── EMOJIS ───────────────────────────────────────────────────────
# Se usan emojis unicode estándar (en vez de emojis personalizados) para que
# siempre se vean bien, sin importar si el bot tiene el permiso "Usar emojis
# externos" en el servidor. Antes, cuando el permiso faltaba, Discord mostraba
# el texto crudo del emoji (por eso aparecía ":_:").
E_CHECK   = "✅"   # check mark
E_REDPT   = "🔴"   # red point
E_WARN    = "⚠️"   # warning
E_RDIAM   = "💎"   # red diamond
E_ARROW   = "➡️"   # arrow
E_CROWN   = "👑"   # red crown
E_NO      = "❌"   # no
E_LOAD    = "⏳"   # load
E_USER    = "👤"   # persona
E_TICKET  = "🎫"   # ticket
E_LOCK    = "🔒"   # lock
E_INFO    = "📌"   # info

# URLs de las imágenes para set_thumbnail / set_author
URL_CHECK  = "https://cdn.discordapp.com/emojis/1511381303872716820.webp?size=100&animated=true"
URL_REDPT  = "https://cdn.discordapp.com/emojis/1463164698353733725.webp?size=100&animated=true"
URL_WARN   = "https://cdn.discordapp.com/emojis/1495901573476520106.webp?size=100"
URL_RDIAM  = "https://cdn.discordapp.com/emojis/1469195655762153502.webp?size=100&animated=true"
URL_CROWN  = "https://cdn.discordapp.com/emojis/1461735621985833061.webp?size=100&animated=true"
URL_NO     = "https://cdn.discordapp.com/emojis/606562703917449226.webp?size=100&animated=true"
URL_LOAD   = "https://cdn.discordapp.com/emojis/1463540610379022429.webp?size=100&animated=true"

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

# ticket_config: { "<guild_id>": {"category": id, "support_role": id, "log_channel": id} }
ticket_config: dict = load_json(TICKET_CONFIG_FILE, {})
def _save_tc(): save_json(TICKET_CONFIG_FILE, ticket_config)

# ticket_counter: { "<guild_id>": int }
ticket_counter: dict = load_json(TICKET_COUNTER_FILE, {})
def _save_tcounter(): save_json(TICKET_COUNTER_FILE, ticket_counter)

def _next_ticket_number(guild_id: int) -> int:
    key = str(guild_id)
    n = ticket_counter.get(key, 0) + 1
    ticket_counter[key] = n
    _save_tcounter()
    return n

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
    return f"{BOT_NAME} • {BOT_CREDIT}"

# ── BYPASS ENGINE ────────────────────────────────────────────────
_KEYS = ("content","result","loadstring","bypassed","bypassed_link",
         "bypassed_url","final_url","destination","url","link","key","output")
_http = requests.Session()
_http.headers.update({"User-Agent": "KingBot/1.0"})

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

# ── BYPASS EMBEDS  (diseño foto 2, tema rojo) ─────────────────────

def embed_ok(result: str, elapsed: float, url: str, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name="BYPASSED SUCCESSFULLY", icon_url=URL_CHECK)
    e.set_thumbnail(url=URL_CHECK)
    e.add_field(
        name=f"{E_RDIAM} RESULT",
        value=f"```\n{result[:900]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{E_USER} REQUEST BY",
        value=user.mention,
        inline=True
    )
    e.add_field(
        name=f"{E_LOAD} TIME",
        value=f"{elapsed:.2f}s",
        inline=True
    )
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"MADE WITH 💪  |  {_footer()}")
    return e

def embed_fail(error: str, url: str, elapsed: float, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name="BYPASS FAILED", icon_url=URL_NO)
    e.set_thumbnail(url=URL_NO)
    e.add_field(
        name=f"{E_RDIAM} URL",
        value=f"```\n{url[:200]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{E_WARN} ERROR",
        value=f"```\n{error or '?'}\n```",
        inline=False
    )
    e.add_field(
        name=f"{E_USER} REQUEST BY",
        value=user.mention,
        inline=True
    )
    e.add_field(
        name=f"{E_LOAD} TIME",
        value=f"{elapsed:.2f}s",
        inline=True
    )
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"MADE WITH 💪  |  {_footer()}")
    return e

def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="PROCESSING BYPASS...", icon_url=URL_LOAD)
    e.set_thumbnail(url=URL_LOAD)
    e.description = f"{E_LOAD} Bypass en proceso, espera un momento..."
    e.set_footer(text=_footer())
    return e

# ── VIEWS ────────────────────────────────────────────────────────

class BypassView(View):
    def __init__(self, result: str, elapsed: float):
        super().__init__(timeout=None)
        self._r = result
        self.add_item(Button(
            label=f"⏰  {elapsed:.2f}s",
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

    @discord.ui.button(label="📋  Copiar resultado",
                       style=discord.ButtonStyle.danger, row=1)
    async def copy_btn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            content=f"```\n{self._r[:1800]}\n```", ephemeral=True)

class FailView(View):
    def __init__(self, elapsed: float):
        super().__init__(timeout=None)
        self.add_item(Button(
            label=f"⏰  {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True, row=0))
        self.add_item(Button(
            label="SUPPORT SERVER", emoji="💬",
            url=SUPPORT_SERVER_URL,
            style=discord.ButtonStyle.link, row=0))

# ── BOT ──────────────────────────────────────────────────────────

def _get_prefix(_bot, message: discord.Message):
    """Permite activar comandos escribiendo el nombre/trigger del bot,
    ej: 'king afk', 'king ping', 'KING BOT help'. También responde a
    mención directa (@KING BOT comando)."""
    content = message.content or ""
    low = content.lower()
    prefixes = []
    for name in (BOT_NAME.lower() + " ", BOT_TRIGGER.lower() + " "):
        if low.startswith(name):
            prefixes.append(content[:len(name)])
    prefixes.extend(commands.when_mentioned(_bot, message))
    if not prefixes:
        prefixes.append("\uFFFF")  # prefijo imposible: nada calza como comando
    return prefixes

class KingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=_get_prefix, intents=intents, help_command=None)
        self._giveaway_task_started = False

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(TicketCloseView())
        self.add_view(GiveawayView())
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online como {self.user} | {len(self.guilds)} servidor(es)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"/help • {BOT_NAME}"))
        if not self._giveaway_task_started:
            self._giveaway_task_started = True
            asyncio.create_task(_giveaway_watcher())
            asyncio.create_task(_reminder_watcher())

    async def on_message(self, message: discord.Message):
        if message.author.bot: return

        # ── AFK ──
        if message.author.id in _afk_users:
            _afk_users.pop(message.author.id, None)
            try:
                await message.channel.send(
                    f"{E_CHECK} Bienvenido de vuelta {message.author.mention}, te quité el AFK.",
                    delete_after=8)
            except Exception: pass
        for u in message.mentions:
            if u.id in _afk_users:
                try:
                    await message.channel.send(
                        f"{E_WARN} {u.mention} está AFK: {_afk_users[u.id]}", delete_after=8)
                except Exception: pass

        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(_auto_bypass(message, urls))

        # ── AUTOMOD (palabras prohibidas) ──
        await _check_automod(message)

        # ── XP / NIVELES ──
        await _grant_xp(message)

        # necesario para que funcionen los comandos por prefijo/nombre del bot
        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member):
        await _handle_member_join(member)

    async def on_member_remove(self, member: discord.Member):
        await _handle_member_remove(member)

    async def on_message_delete(self, message: discord.Message):
        await _handle_message_delete(message)

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await _handle_message_edit(before, after)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await _handle_starboard_reaction(payload)

bot = KingBot()

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

# ── SLASH — BYPASS ────────────────────────────────────────────────

@bot.tree.command(name="bypass", description="Bypassea un enlace")
@app_commands.describe(url="Enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_url(url):
        e = discord.Embed(description=f"{E_WARN} URL inválida.", color=C_RED)
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
            description=f"{E_NO} Auto-bypass **desactivado** en {interaction.channel.mention}.",
            color=C_RED)
    else:
        autobypass_channels.add(cid); _save_ab()
        e = discord.Embed(
            description=(f"{E_CHECK} Auto-bypass **activado** en {interaction.channel.mention}.\n"
                         f"{E_ARROW} Los enlaces se bypasean automáticamente."),
            color=C_RED)
    e.set_author(name=BOT_NAME, icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ae(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(
            f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)

# ── SLASH — FUN ───────────────────────────────────────────────────

_8BALL = [
    "Sí, definitivamente.",  "Sin duda alguna.",      "Puedes contar con ello.",
    "Así es.",               "Muy probable.",          "Todo indica que sí.",
    "Buenas perspectivas.",  "Parece que sí.",         "Respuesta dudosa, intenta de nuevo.",
    "Pregúntame luego.",     "Mejor no decirte ahora.","No puedo predecirlo.",
    "No cuentes con ello.",  "Mi respuesta es no.",    "Mis fuentes dicen que no.",
    "Las perspectivas no son buenas.", "Muy dudoso.",
]

@bot.tree.command(name="8ball", description="Pregúntale a la bola mágica 🎱")
@app_commands.describe(pregunta="Tu pregunta")
async def cmd_8ball(interaction: discord.Interaction, pregunta: str):
    resp = random.choice(_8BALL)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎱 Magic 8-Ball", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Pregunta",  value=f"```{pregunta[:300]}```", inline=False)
    e.add_field(name=f"{E_ARROW} Respuesta", value=f"```{resp}```",           inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


_JOKES = [
    ("¿Por qué los pájaros vuelan hacia el sur en invierno?", "Porque caminando les da pereza."),
    ("¿Qué le dijo un semáforo al otro?",          "No me mires, que me estoy cambiando."),
    ("¿Cómo se llama el campeón de buceo de Japón?", "Tokofondo."),
    ("¿Qué hace una abeja en el gimnasio?",        "¡Zum-ba!"),
    ("¿Por qué el libro de matemáticas estaba triste?", "Porque tenía muchos problemas."),
    ("¿Qué le dice un jardinero a otro?",          "¡Me tienes harto-nsia!"),
    ("¿Cómo se dice 'pez' en inglés?",             "Fish... bueno, así de fácil era."),
    ("¿Qué hace un pez cuando está aburrido?",     "Nada."),
    ("¿Qué le dijo un techo al otro techo?",       "Nada, los techos no hablan."),
    ("¿Cómo muere un químico?",                    "De nitrógeno."),
]

@bot.tree.command(name="joke", description="Un chiste aleatorio 😂")
async def cmd_joke(interaction: discord.Interaction):
    setup, punchline = random.choice(_JOKES)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 😂 Chiste", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Pregunta",   value=f"```{setup}```",    inline=False)
    e.add_field(name=f"{E_ARROW} Respuesta",  value=f"```{punchline}```", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="coinflip", description="Lanza una moneda 🪙")
async def cmd_coinflip(interaction: discord.Interaction):
    result = random.choice(["🦅 CARA", "🔵 CRUZ"])
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🪙 Moneda", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Resultado",    value=f"```{result}```",       inline=False)
    e.add_field(name=f"{E_USER} Lanzado por",   value=interaction.user.mention, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="roll", description="Lanza un dado 🎲")
@app_commands.describe(lados="Número de caras del dado (por defecto 6)")
async def cmd_roll(interaction: discord.Interaction, lados: int = 6):
    if lados < 2 or lados > 1000:
        return await interaction.response.send_message(
            f"{E_WARN} El dado debe tener entre 2 y 1000 caras.", ephemeral=True)
    result = random.randint(1, lados)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎲 Dado d{lados}", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Resultado",  value=f"```🎲 {result} / {lados}```",  inline=False)
    e.add_field(name=f"{E_USER} Lanzado por", value=interaction.user.mention,          inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


_ROASTS = [
    "Eres tan lento que tardas 2 horas en ver 60 Minutes.",
    "Si la inteligencia fuera agua, estarías en el desierto.",
    "Eres la razón por la que los instructivos tienen advertencias.",
    "Te busqué en el diccionario bajo la palabra 'mediocre'... foto perfecta.",
    "Eres como una nube: cuando desapareces el día mejora.",
    "La evolución dio marcha atrás contigo.",
    "Tienes cara de que tu árbol genealógico es un cactus.",
    "Eres tan aburrido que te pusiste a dormir en tu propio sueño.",
    "Tu red Wi-Fi tiene mejor señal que tu cerebro.",
    "Si fueras más inútil, tendrías que regarme dos veces por semana.",
]

@bot.tree.command(name="roast", description="Insulto suave a alguien 🔥")
@app_commands.describe(usuario="Usuario a incinerar")
async def cmd_roast(interaction: discord.Interaction, usuario: discord.Member):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🔥 Roast", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Víctima",  value=usuario.mention,          inline=True)
    e.add_field(name=f"{E_USER} Por",       value=interaction.user.mention,  inline=True)
    e.add_field(name=f"{E_ARROW} Veredicto",value=f"```{random.choice(_ROASTS)}```", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


_RPS_MAP = {"piedra": "🪨", "papel": "📄", "tijeras": "✂️"}
_RPS_WIN = {("piedra","tijeras"),("tijeras","papel"),("papel","piedra")}

@bot.tree.command(name="rps", description="Piedra, Papel o Tijeras ✊")
@app_commands.describe(eleccion="Tu elección")
@app_commands.choices(eleccion=[
    app_commands.Choice(name="Piedra 🪨",  value="piedra"),
    app_commands.Choice(name="Papel 📄",   value="papel"),
    app_commands.Choice(name="Tijeras ✂️", value="tijeras"),
])
async def cmd_rps(interaction: discord.Interaction, eleccion: str):
    bot_pick = random.choice(list(_RPS_MAP.keys()))
    if eleccion == bot_pick:
        outcome = "🟡 EMPATE"
    elif (eleccion, bot_pick) in _RPS_WIN:
        outcome = f"{E_CHECK} GANASTE"
    else:
        outcome = f"{E_NO} PERDISTE"
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — ✊ Piedra Papel Tijeras", icon_url=URL_CROWN)
    e.add_field(name=f"{E_USER} Tú",         value=f"```{_RPS_MAP[eleccion]} {eleccion.upper()}```", inline=True)
    e.add_field(name=f"{E_CROWN} {BOT_NAME}", value=f"```{_RPS_MAP[bot_pick]} {bot_pick.upper()}```", inline=True)
    e.add_field(name=f"{E_ARROW} Resultado",  value=f"```{outcome}```",                               inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="say", description="Haz que el bot diga algo")
@app_commands.describe(mensaje="Mensaje a decir")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_say(interaction: discord.Interaction, mensaje: str):
    await interaction.response.send_message("✅ Enviado.", ephemeral=True)
    await interaction.channel.send(mensaje[:2000])

@cmd_say.error
async def _say_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar mensajes**.", ephemeral=True)


# ── SISTEMA DE TICKETS ──────────────────────────────────────────────

def _guild_ticket_cfg(guild_id: int) -> dict:
    return ticket_config.get(str(guild_id), {})

class TicketPanelView(View):
    """Vista persistente con el botón para abrir un ticket. custom_id fijo
    para que siga funcionando tras reiniciar el bot."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", emoji="🎫",
                        style=discord.ButtonStyle.danger,
                        custom_id="king_ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, _):
        await _create_ticket(interaction)

class TicketCloseView(View):
    """Vista persistente dentro de cada ticket, con botón de cierre."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cerrar Ticket", emoji="🔒",
                        style=discord.ButtonStyle.secondary,
                        custom_id="king_ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, _):
        await _close_ticket(interaction)

async def _create_ticket(interaction: discord.Interaction):
    guild = interaction.guild
    cfg = _guild_ticket_cfg(guild.id)
    if not cfg.get("category"):
        e = discord.Embed(
            description=f"{E_WARN} El sistema de tickets aún no está configurado. "
                        f"Un administrador debe usar `/ticket-setup` primero.",
            color=C_RED)
        return await interaction.response.send_message(embed=e, ephemeral=True)

    category = guild.get_channel(cfg["category"])
    if category is None:
        e = discord.Embed(
            description=f"{E_WARN} La categoría configurada para tickets ya no existe. "
                        f"Pide a un administrador que ejecute `/ticket-setup` de nuevo.",
            color=C_RED)
        return await interaction.response.send_message(embed=e, ephemeral=True)

    # Evita que un usuario tenga varios tickets abiertos a la vez
    existing = discord.utils.get(category.text_channels,
                                  topic=f"ticket-owner:{interaction.user.id}")
    if existing:
        e = discord.Embed(
            description=f"{E_WARN} Ya tienes un ticket abierto: {existing.mention}",
            color=C_RED)
        return await interaction.response.send_message(embed=e, ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    number = _next_ticket_number(guild.id)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
    }
    support_role_id = cfg.get("support_role")
    if support_role_id:
        role = guild.get_role(support_role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True)

    channel = await guild.create_text_channel(
        name=f"ticket-{number:04d}",
        category=category,
        overwrites=overwrites,
        topic=f"ticket-owner:{interaction.user.id}",
        reason=f"Ticket abierto por {interaction.user}",
    )

    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_TICKET} Ticket #{number:04d}", icon_url=URL_CROWN)
    e.description = (f"¡Hola {interaction.user.mention}! Gracias por abrir un ticket.\n"
                     f"Cuéntanos en qué podemos ayudarte y el equipo de soporte "
                     f"te responderá lo antes posible.\n\n"
                     f"{E_LOCK} Pulsa **Cerrar Ticket** cuando el problema esté resuelto.")
    e.set_footer(text=_footer())

    ping = interaction.user.mention
    if support_role_id and guild.get_role(support_role_id):
        ping += f" {guild.get_role(support_role_id).mention}"

    await channel.send(content=ping, embed=e, view=TicketCloseView())

    ok = discord.Embed(
        description=f"{E_CHECK} Tu ticket fue creado: {channel.mention}",
        color=C_RED)
    await interaction.followup.send(embed=ok, ephemeral=True)

    log_id = cfg.get("log_channel")
    if log_id:
        log_ch = guild.get_channel(log_id)
        if log_ch:
            le = discord.Embed(
                description=f"{E_TICKET} {channel.mention} abierto por {interaction.user.mention}",
                color=C_RED, timestamp=datetime.now(timezone.utc))
            le.set_footer(text=_footer())
            try: await log_ch.send(embed=le)
            except Exception: pass

async def _close_ticket(interaction: discord.Interaction):
    channel = interaction.channel
    guild = interaction.guild
    cfg = _guild_ticket_cfg(guild.id)

    is_admin = interaction.user.guild_permissions.administrator
    support_role_id = cfg.get("support_role")
    has_support_role = bool(support_role_id and any(r.id == support_role_id for r in interaction.user.roles))
    is_owner = channel.topic == f"ticket-owner:{interaction.user.id}"

    if not (is_admin or has_support_role or is_owner):
        e = discord.Embed(description=f"{E_WARN} No tienes permiso para cerrar este ticket.", color=C_RED)
        return await interaction.response.send_message(embed=e, ephemeral=True)

    e = discord.Embed(
        description=f"{E_LOCK} Este ticket se cerrará en 5 segundos...",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

    log_id = cfg.get("log_channel")
    if log_id:
        log_ch = guild.get_channel(log_id)
        if log_ch:
            le = discord.Embed(
                description=f"{E_LOCK} {channel.name} cerrado por {interaction.user.mention}",
                color=C_RED, timestamp=datetime.now(timezone.utc))
            le.set_footer(text=_footer())
            try: await log_ch.send(embed=le)
            except Exception: pass

    await asyncio.sleep(5)
    try: await channel.delete(reason=f"Ticket cerrado por {interaction.user}")
    except Exception: pass


@bot.tree.command(name="ticket-setup", description="Configura el sistema de tickets (Admin)")
@app_commands.describe(
    categoria="Categoría donde se crearán los canales de ticket",
    rol_soporte="Rol que puede ver y atender los tickets (opcional)",
    canal_logs="Canal donde se registran aperturas/cierres (opcional)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_ticket_setup(interaction: discord.Interaction,
                            categoria: discord.CategoryChannel,
                            rol_soporte: discord.Role = None,
                            canal_logs: discord.TextChannel = None):
    ticket_config[str(interaction.guild_id)] = {
        "category": categoria.id,
        "support_role": rol_soporte.id if rol_soporte else None,
        "log_channel": canal_logs.id if canal_logs else None,
    }
    _save_tc()
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_TICKET} Tickets configurados", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Categoría", value=categoria.mention, inline=True)
    e.add_field(name=f"{E_USER} Rol soporte", value=rol_soporte.mention if rol_soporte else "—", inline=True)
    e.add_field(name=f"{E_INFO} Canal de logs", value=canal_logs.mention if canal_logs else "—", inline=True)
    e.add_field(name=f"{E_ARROW} Siguiente paso",
                value="Usa `/ticket-panel` en el canal donde quieras publicar el botón de apertura.",
                inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_ticket_setup.error
async def _ticket_setup_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)


@bot.tree.command(name="ticket-panel", description="Publica el panel para abrir tickets (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_ticket_panel(interaction: discord.Interaction):
    if not _guild_ticket_cfg(interaction.guild_id).get("category"):
        e = discord.Embed(
            description=f"{E_WARN} Primero configura el sistema con `/ticket-setup`.",
            color=C_RED)
        return await interaction.response.send_message(embed=e, ephemeral=True)

    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_TICKET} Soporte", icon_url=URL_CROWN)
    e.description = (f"¿Necesitas ayuda? Pulsa el botón de abajo para abrir un ticket privado "
                     f"con el equipo de soporte.")
    e.set_thumbnail(url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.channel.send(embed=e, view=TicketPanelView())
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Panel publicado.", color=C_RED), ephemeral=True)

@cmd_ticket_panel.error
async def _ticket_panel_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)


@bot.tree.command(name="ticket-close", description="Cierra el ticket actual")
async def cmd_ticket_close(interaction: discord.Interaction):
    cfg = _guild_ticket_cfg(interaction.guild_id)
    if interaction.channel.category_id != cfg.get("category"):
        e = discord.Embed(description=f"{E_WARN} Este comando solo funciona dentro de un canal de ticket.",
                          color=C_RED)
        return await interaction.response.send_message(embed=e, ephemeral=True)
    await _close_ticket(interaction)


# ── SISTEMA DE GIVEAWAYS ─────────────────────────────────────────────

GIVEAWAYS_FILE = "giveaways.json"
# giveaways: { "<message_id>": {channel_id, guild_id, prize, winners, end_ts,
#                                host_id, entries:[ids], ended: bool} }
giveaways: dict = load_json(GIVEAWAYS_FILE, {})
def _save_gw(): save_json(GIVEAWAYS_FILE, giveaways)

_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_DUR_SECS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

def _parse_duration(text: str):
    m = _DURATION_RE.match(text.strip())
    if not m: return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if n <= 0: return None
    return n * _DUR_SECS[unit]

def embed_giveaway(prize: str, winners: int, end_ts: float, host_id: int, entries: int) -> discord.Embed:
    e = discord.Embed(color=C_RED, description=(
        f"{E_RDIAM} **Premio:** {prize}\n"
        f"{E_CROWN} **Ganadores:** {winners}\n"
        f"{E_USER} **Organiza:** <@{host_id}>\n"
        f"{E_ARROW} **Termina:** <t:{int(end_ts)}:R>\n"
        f"{E_TICKET} **Participantes:** {entries}\n\n"
        f"Pulsa el botón 🎉 para participar."
    ))
    e.set_author(name=f"{BOT_NAME} — 🎉 Giveaway", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    return e

class GiveawayView(View):
    """Vista persistente; el custom_id es fijo y busca el giveaway por el
    ID del mensaje al que está pegada, así funciona tras reiniciar el bot."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participar", emoji="🎉",
                        style=discord.ButtonStyle.danger,
                        custom_id="king_giveaway_enter")
    async def enter(self, interaction: discord.Interaction, _):
        gid = str(interaction.message.id)
        gw = giveaways.get(gid)
        if not gw or gw.get("ended"):
            return await interaction.response.send_message(
                f"{E_WARN} Este giveaway ya no está activo.", ephemeral=True)
        uid = interaction.user.id
        if uid in gw["entries"]:
            gw["entries"].remove(uid)
            _save_gw()
            return await interaction.response.send_message(
                f"{E_NO} Saliste del giveaway.", ephemeral=True)
        gw["entries"].append(uid)
        _save_gw()
        await interaction.response.send_message(
            f"{E_CHECK} ¡Estás participando! Buena suerte 🍀", ephemeral=True)

async def _finish_giveaway(message_id: str, reroll: bool = False):
    gw = giveaways.get(message_id)
    if not gw: return None
    channel = bot.get_channel(gw["channel_id"])
    if channel is None:
        try: channel = await bot.fetch_channel(gw["channel_id"])
        except Exception: return None
    try:
        msg = await channel.fetch_message(int(message_id))
    except Exception:
        msg = None

    entries = gw.get("entries", [])
    n = min(gw.get("winners", 1), len(entries))
    winners = random.sample(entries, n) if n > 0 else []

    if winners:
        mentions = ", ".join(f"<@{w}>" for w in winners)
        result = discord.Embed(
            description=(f"{E_CROWN} **¡Felicidades!** {mentions}\n"
                         f"Ganaste: **{gw['prize']}**"),
            color=C_RED, timestamp=datetime.now(timezone.utc))
    else:
        mentions = None
        result = discord.Embed(
            description=f"{E_WARN} Nadie participó, no hubo ganador para **{gw['prize']}**.",
            color=C_RED, timestamp=datetime.now(timezone.utc))
    result.set_author(name=f"{BOT_NAME} — 🎉 Giveaway {'rerolleado' if reroll else 'finalizado'}",
                      icon_url=URL_CROWN)
    result.set_footer(text=_footer())

    if msg:
        try:
            end_embed = embed_giveaway(gw["prize"], gw["winners"], gw["end_ts"], gw["host_id"], len(entries))
            end_embed.title = "🔒 GIVEAWAY FINALIZADO"
            v = View()
            v.add_item(Button(label="Finalizado", style=discord.ButtonStyle.secondary, disabled=True))
            await msg.edit(embed=end_embed, view=v)
        except Exception: pass
        try:
            await channel.send(content=mentions, embed=result)
        except Exception: pass

    gw["ended"] = True
    _save_gw()
    return winners

async def _giveaway_watcher():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        for mid, gw in list(giveaways.items()):
            if not gw.get("ended") and gw.get("end_ts", 0) <= now:
                try: await _finish_giveaway(mid)
                except Exception as e: logger.warning(f"giveaway_watcher: {e}")
        await asyncio.sleep(15)


@bot.tree.command(name="giveaway-start", description="Inicia un giveaway 🎉")
@app_commands.describe(premio="Qué se sortea", duracion="Ej: 30s, 10m, 2h, 1d",
                        ganadores="Cantidad de ganadores (por defecto 1)",
                        canal="Canal donde publicarlo (por defecto el actual)")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_giveaway_start(interaction: discord.Interaction, premio: str, duracion: str,
                              ganadores: app_commands.Range[int, 1, 20] = 1,
                              canal: discord.TextChannel = None):
    secs = _parse_duration(duracion)
    if not secs:
        return await interaction.response.send_message(
            f"{E_WARN} Duración inválida. Usa formato como `30s`, `10m`, `2h`, `1d`.", ephemeral=True)
    target = canal or interaction.channel
    end_ts = time.time() + secs

    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Giveaway publicado en {target.mention}.", color=C_RED),
        ephemeral=True)

    msg = await target.send(embed=embed_giveaway(premio, ganadores, end_ts, interaction.user.id, 0),
                             view=GiveawayView())
    giveaways[str(msg.id)] = {
        "channel_id": target.id, "guild_id": interaction.guild_id, "prize": premio,
        "winners": ganadores, "end_ts": end_ts, "host_id": interaction.user.id,
        "entries": [], "ended": False,
    }
    _save_gw()

@cmd_giveaway_start.error
async def _gw_start_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar servidor**.", ephemeral=True)


@bot.tree.command(name="giveaway-end", description="Termina un giveaway ahora mismo (Admin)")
@app_commands.describe(message_id="ID del mensaje del giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_giveaway_end(interaction: discord.Interaction, message_id: str):
    gw = giveaways.get(message_id)
    if not gw or gw.get("ended"):
        return await interaction.response.send_message(
            f"{E_WARN} No encontré un giveaway activo con ese ID.", ephemeral=True)
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Giveaway finalizado.", color=C_RED), ephemeral=True)
    await _finish_giveaway(message_id)

@cmd_giveaway_end.error
async def _gw_end_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar servidor**.", ephemeral=True)


@bot.tree.command(name="giveaway-reroll", description="Sortea de nuevo un giveaway ya finalizado (Admin)")
@app_commands.describe(message_id="ID del mensaje del giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_giveaway_reroll(interaction: discord.Interaction, message_id: str):
    gw = giveaways.get(message_id)
    if not gw or not gw.get("ended"):
        return await interaction.response.send_message(
            f"{E_WARN} Ese giveaway no existe o todavía no ha terminado.", ephemeral=True)
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Rerolleando...", color=C_RED), ephemeral=True)
    await _finish_giveaway(message_id, reroll=True)

@cmd_giveaway_reroll.error
async def _gw_reroll_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar servidor**.", ephemeral=True)


# ── SLASH — MODERACIÓN ───────────────────────────────────────────────

WARNS_FILE = "warns.json"
# warns: { "guild_id": { "user_id": [ {"reason":.., "mod_id":.., "ts":..} ] } }
warns: dict = load_json(WARNS_FILE, {})
def _save_warns(): save_json(WARNS_FILE, warns)

@bot.tree.command(name="kick", description="Expulsa a un miembro (Kick Members)")
@app_commands.describe(usuario="Usuario a expulsar", razon="Motivo (opcional)")
@app_commands.checks.has_permissions(kick_members=True)
async def cmd_kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin especificar"):
    if usuario.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        return await interaction.response.send_message(
            f"{E_WARN} No puedes expulsar a alguien con un rol igual o superior al tuyo.", ephemeral=True)
    try:
        await usuario.kick(reason=f"{razon} — por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permisos para expulsarlo.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 👢 Kick", icon_url=URL_CROWN)
    e.add_field(name=f"{E_USER} Usuario", value=f"{usuario} (`{usuario.id}`)", inline=False)
    e.add_field(name=f"{E_ARROW} Razón", value=razon, inline=False)
    e.add_field(name=f"{E_CROWN} Moderador", value=interaction.user.mention, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_kick.error
async def _kick_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Expulsar miembros**.", ephemeral=True)


@bot.tree.command(name="ban", description="Banea a un miembro (Ban Members)")
@app_commands.describe(usuario="Usuario a banear", razon="Motivo (opcional)",
                        borrar_mensajes="Días de mensajes a borrar (0-7, por defecto 0)")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin especificar",
                   borrar_mensajes: app_commands.Range[int, 0, 7] = 0):
    if usuario.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        return await interaction.response.send_message(
            f"{E_WARN} No puedes banear a alguien con un rol igual o superior al tuyo.", ephemeral=True)
    try:
        await usuario.ban(reason=f"{razon} — por {interaction.user}", delete_message_days=borrar_mensajes)
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permisos para banearlo.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🔨 Ban", icon_url=URL_CROWN)
    e.add_field(name=f"{E_USER} Usuario", value=f"{usuario} (`{usuario.id}`)", inline=False)
    e.add_field(name=f"{E_ARROW} Razón", value=razon, inline=False)
    e.add_field(name=f"{E_CROWN} Moderador", value=interaction.user.mention, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_ban.error
async def _ban_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Banear miembros**.", ephemeral=True)


@bot.tree.command(name="unban", description="Desbanea a un usuario por ID (Ban Members)")
@app_commands.describe(user_id="ID del usuario a desbanear")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    try:
        uid = int(user_id)
        user = await bot.fetch_user(uid)
        await interaction.guild.unban(user, reason=f"Desbaneado por {interaction.user}")
    except (ValueError, discord.NotFound):
        return await interaction.response.send_message(f"{E_WARN} No encontré ese ID baneado.", ephemeral=True)
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permisos para desbanear.", ephemeral=True)
    e = discord.Embed(description=f"{E_CHECK} **{user}** fue desbaneado.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_unban.error
async def _unban_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Banear miembros**.", ephemeral=True)


@bot.tree.command(name="timeout", description="Silencia temporalmente a un miembro (Moderate Members)")
@app_commands.describe(usuario="Usuario a silenciar", duracion="Ej: 10m, 1h, 1d (máx 28d)",
                        razon="Motivo (opcional)")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_timeout(interaction: discord.Interaction, usuario: discord.Member, duracion: str,
                       razon: str = "Sin especificar"):
    secs = _parse_duration(duracion)
    if not secs or secs > 28 * 86400:
        return await interaction.response.send_message(
            f"{E_WARN} Duración inválida (máximo 28d). Usa formato como `10m`, `1h`, `1d`.", ephemeral=True)
    try:
        await usuario.timeout(discord.utils.utcnow() + timedelta(seconds=secs),
                               reason=f"{razon} — por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permisos para silenciarlo.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🔇 Timeout", icon_url=URL_CROWN)
    e.add_field(name=f"{E_USER} Usuario", value=usuario.mention, inline=True)
    e.add_field(name=f"{E_ARROW} Duración", value=duracion, inline=True)
    e.add_field(name=f"{E_WARN} Razón", value=razon, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_timeout.error
async def _timeout_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Moderar miembros**.", ephemeral=True)


@bot.tree.command(name="untimeout", description="Quita el silencio a un miembro (Moderate Members)")
@app_commands.describe(usuario="Usuario a des-silenciar")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_untimeout(interaction: discord.Interaction, usuario: discord.Member):
    try:
        await usuario.timeout(None, reason=f"Timeout removido por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permisos.", ephemeral=True)
    e = discord.Embed(description=f"{E_CHECK} Se quitó el silencio a {usuario.mention}.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_untimeout.error
async def _untimeout_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Moderar miembros**.", ephemeral=True)


@bot.tree.command(name="warn", description="Da una advertencia a un miembro (Moderate Members)")
@app_commands.describe(usuario="Usuario a advertir", razon="Motivo")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_warn(interaction: discord.Interaction, usuario: discord.Member, razon: str):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warns.setdefault(gid, {}).setdefault(uid, []).append({
        "reason": razon, "mod_id": interaction.user.id, "ts": time.time()})
    _save_warns()
    total = len(warns[gid][uid])
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — ⚠️ Advertencia", icon_url=URL_CROWN)
    e.add_field(name=f"{E_USER} Usuario", value=usuario.mention, inline=True)
    e.add_field(name=f"{E_RDIAM} Total warns", value=f"`{total}`", inline=True)
    e.add_field(name=f"{E_WARN} Razón", value=razon, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)
    try:
        await usuario.send(f"{E_WARN} Recibiste una advertencia en **{interaction.guild.name}**: {razon}")
    except Exception: pass

@cmd_warn.error
async def _warn_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Moderar miembros**.", ephemeral=True)


@bot.tree.command(name="warnings", description="Ver las advertencias de un miembro")
@app_commands.describe(usuario="Usuario a consultar")
async def cmd_warnings(interaction: discord.Interaction, usuario: discord.Member):
    lst = warns.get(str(interaction.guild_id), {}).get(str(usuario.id), [])
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — ⚠️ Advertencias de {usuario.display_name}", icon_url=URL_CROWN)
    if not lst:
        e.description = "Este usuario no tiene advertencias."
    else:
        for i, w in enumerate(lst[-10:], 1):
            e.add_field(name=f"#{i}", value=f"{w['reason']}\n<@{w['mod_id']}> • <t:{int(w['ts'])}:R>",
                       inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="clear-warnings", description="Borra las advertencias de un miembro (Moderate Members)")
@app_commands.describe(usuario="Usuario a limpiar")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_clear_warnings(interaction: discord.Interaction, usuario: discord.Member):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warns.get(gid, {}).pop(uid, None)
    _save_warns()
    e = discord.Embed(description=f"{E_CHECK} Advertencias de {usuario.mention} eliminadas.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_clear_warnings.error
async def _cw_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Moderar miembros**.", ephemeral=True)


# ── SLASH — EXTRAS ────────────────────────────────────────────────────

@bot.tree.command(name="poll", description="Crea una encuesta rápida")
@app_commands.describe(pregunta="La pregunta de la encuesta",
                        opcion1="Opción 1", opcion2="Opción 2",
                        opcion3="Opción 3 (opcional)", opcion4="Opción 4 (opcional)")
async def cmd_poll(interaction: discord.Interaction, pregunta: str, opcion1: str, opcion2: str,
                    opcion3: str = None, opcion4: str = None):
    opciones = [o for o in (opcion1, opcion2, opcion3, opcion4) if o]
    numeros = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 📊 Encuesta", icon_url=URL_CROWN)
    e.description = f"**{pregunta}**\n\n" + "\n".join(
        f"{numeros[i]} {op}" for i, op in enumerate(opciones))
    e.add_field(name=f"{E_USER} Creada por", value=interaction.user.mention, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    for i in range(len(opciones)):
        try: await msg.add_reaction(numeros[i])
        except Exception: pass


@bot.tree.command(name="remind", description="Te recuerda algo después de un tiempo")
@app_commands.describe(duracion="Ej: 30s, 10m, 2h, 1d", mensaje="Qué quieres que te recuerde")
async def cmd_remind(interaction: discord.Interaction, duracion: str, mensaje: str):
    secs = _parse_duration(duracion)
    if not secs:
        return await interaction.response.send_message(
            f"{E_WARN} Duración inválida. Usa formato como `30s`, `10m`, `2h`, `1d`.", ephemeral=True)

    rid = f"{interaction.user.id}-{int(time.time()*1000)}"
    reminders[rid] = {
        "user_id": interaction.user.id, "channel_id": interaction.channel.id,
        "guild_id": interaction.guild_id, "text": mensaje,
        "due_ts": time.time() + secs, "done": False,
    }
    _save_reminders()

    e = discord.Embed(
        description=f"{E_CHECK} Te recordaré esto en **{duracion}**: {mensaje}\n"
                    f"({E_INFO} usa `/remindlist` para ver tus recordatorios pendientes)",
        color=C_RED)
    await interaction.response.send_message(embed=e, ephemeral=True)
    # Nota: el recordatorio queda guardado en reminders.json y lo dispara
    # _reminder_watcher(), así que sobrevive aunque el bot se reinicie.


_afk_users: dict = {}   # user_id -> mensaje afk

@bot.tree.command(name="afk", description="Marca que estás AFK (ausente)")
@app_commands.describe(mensaje="Motivo (opcional)")
async def cmd_afk(interaction: discord.Interaction, mensaje: str = "AFK"):
    _afk_users[interaction.user.id] = mensaje
    e = discord.Embed(description=f"{E_CHECK} Te marqué como AFK: {mensaje}", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


# ── SISTEMA DE NIVELES / XP ──────────────────────────────────────────

LEVELS_FILE = "levels.json"
# levels: { "guild_id": { "user_id": {"xp": int, "level": int} } }
levels: dict = load_json(LEVELS_FILE, {})
def _save_levels(): save_json(LEVELS_FILE, levels)

_xp_cooldown: dict = {}   # (guild_id, user_id) -> last_ts
XP_MIN, XP_MAX, XP_COOLDOWN = 8, 18, 45   # xp por mensaje y segundos de espera

def _xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100

def _get_user_level(guild_id: int, user_id: int) -> dict:
    g = levels.setdefault(str(guild_id), {})
    return g.setdefault(str(user_id), {"xp": 0, "level": 0})

async def _grant_xp(message: discord.Message):
    if not message.guild: return
    key = (message.guild.id, message.author.id)
    now = time.time()
    if now - _xp_cooldown.get(key, 0) < XP_COOLDOWN: return
    _xp_cooldown[key] = now

    data = _get_user_level(message.guild.id, message.author.id)
    data["xp"] += random.randint(XP_MIN, XP_MAX)
    leveled_up = False
    while data["xp"] >= _xp_for_level(data["level"]):
        data["xp"] -= _xp_for_level(data["level"])
        data["level"] += 1
        leveled_up = True
    _save_levels()

    if leveled_up:
        e = discord.Embed(
            description=f"{E_CROWN} {message.author.mention} subió a **nivel {data['level']}**! 🎉",
            color=C_RED)
        try: await message.channel.send(embed=e, delete_after=10)
        except Exception: pass

def _draw_progress_bar(draw, x, y, w, h, pct, fg=(200, 0, 0), bg=(40, 40, 40)):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg)
    if pct > 0:
        fill_w = max(h, int(w * pct))
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=h // 2, fill=fg)

def _load_font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try: return ImageFont.truetype(path, size)
        except Exception: continue
    return ImageFont.load_default()

async def _build_rank_card(member: discord.Member) -> discord.File:
    data = _get_user_level(member.guild.id, member.id)
    need = _xp_for_level(data["level"])
    pct = data["xp"] / need if need else 0

    guild_levels = levels.get(str(member.guild.id), {})
    ranked = sorted(guild_levels.items(), key=lambda kv: (kv[1]["level"], kv[1]["xp"]), reverse=True)
    rank = next((i + 1 for i, (uid, _) in enumerate(ranked) if uid == str(member.id)), len(ranked))

    W, H = 900, 260
    card = Image.new("RGBA", (W, H), (20, 0, 0, 255))
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, W - 1, H - 1], outline=(200, 0, 0), width=4)

    avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((180, 180))
    mask = Image.new("L", (180, 180), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 180, 180], fill=255)
    card.paste(avatar, (40, 40), mask)

    f_big = _load_font(38)
    f_med = _load_font(26)
    f_small = _load_font(22)

    draw.text((250, 40), member.display_name[:20], font=f_big, fill=(255, 255, 255))
    draw.text((250, 90), f"Rank #{rank}  •  Nivel {data['level']}", font=f_med, fill=(230, 150, 150))
    _draw_progress_bar(draw, 250, 150, 590, 34, min(pct, 1.0))
    draw.text((250, 195), f"{data['xp']} / {need} XP", font=f_small, fill=(255, 255, 255))

    buf = BytesIO()
    card.save(buf, "PNG")
    buf.seek(0)
    return discord.File(buf, filename="rank.png")

@bot.tree.command(name="rank", description="Muestra tu tarjeta de nivel/XP")
@app_commands.describe(usuario="Usuario a consultar (por defecto tú)")
async def cmd_rank(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    try:
        file = await _build_rank_card(usuario)
        await interaction.followup.send(file=file)
    except Exception as ex:
        logger.warning(f"rank card: {ex}")
        await interaction.followup.send(f"{E_WARN} No pude generar la tarjeta de nivel.")


@bot.tree.command(name="leaderboard", description="Top 10 con más XP del servidor")
async def cmd_leaderboard(interaction: discord.Interaction):
    guild_levels = levels.get(str(interaction.guild_id), {})
    ranked = sorted(guild_levels.items(), key=lambda kv: (kv[1]["level"], kv[1]["xp"]), reverse=True)[:10]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🏆 Leaderboard de XP", icon_url=URL_CROWN)
    if not ranked:
        e.description = "Todavía nadie tiene XP en este servidor."
    else:
        lines = []
        for i, (uid, d) in enumerate(ranked, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"`#{i}`")
            lines.append(f"{medal} <@{uid}> — Nivel **{d['level']}** ({d['xp']} XP)")
        e.description = "\n".join(lines)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="setlevel", description="Fija el nivel de un usuario (Admin)")
@app_commands.describe(usuario="Usuario a modificar", nivel="Nuevo nivel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlevel(interaction: discord.Interaction, usuario: discord.Member,
                        nivel: app_commands.Range[int, 0, 1000]):
    data = _get_user_level(interaction.guild_id, usuario.id)
    data["level"], data["xp"] = nivel, 0
    _save_levels()
    e = discord.Embed(description=f"{E_CHECK} {usuario.mention} ahora es nivel **{nivel}**.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_setlevel.error
async def _setlevel_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)


# ── SISTEMA DE ECONOMÍA ──────────────────────────────────────────────

ECONOMY_FILE = "economy.json"
CURRENCY = "🪙"
# economy: { "guild_id": { "user_id": {"balance": int, "last_daily": ts, "last_work": ts} } }
economy: dict = load_json(ECONOMY_FILE, {})
def _save_eco(): save_json(ECONOMY_FILE, economy)

def _get_wallet(guild_id: int, user_id: int) -> dict:
    g = economy.setdefault(str(guild_id), {})
    return g.setdefault(str(user_id), {"balance": 0, "last_daily": 0, "last_work": 0})

_WORK_JOBS = [
    ("repartiendo pizzas", 40, 120), ("streameando", 30, 150), ("vendiendo bypasses", 60, 200),
    ("moderando el server", 50, 130), ("programando bots", 70, 180), ("jugando Roblox", 20, 100),
]

@bot.tree.command(name="balance", description="Ver tu saldo o el de otro usuario")
@app_commands.describe(usuario="Usuario a consultar (por defecto tú)")
async def cmd_balance(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    w = _get_wallet(interaction.guild_id, usuario.id)
    e = discord.Embed(
        description=f"{CURRENCY} **{usuario.display_name}** tiene `{w['balance']}` monedas.",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="daily", description="Reclama tu recompensa diaria")
async def cmd_daily(interaction: discord.Interaction):
    w = _get_wallet(interaction.guild_id, interaction.user.id)
    now = time.time()
    if now - w["last_daily"] < 86400:
        restante = 86400 - (now - w["last_daily"])
        h, r = divmod(int(restante), 3600); m, _s = divmod(r, 60)
        return await interaction.response.send_message(
            f"{E_WARN} Ya reclamaste tu diario. Vuelve en `{h}h {m}m`.", ephemeral=True)
    amount = random.randint(150, 300)
    w["balance"] += amount
    w["last_daily"] = now
    _save_eco()
    e = discord.Embed(description=f"{E_CHECK} Reclamaste tu diario: **+{amount}** {CURRENCY}", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="work", description="Trabaja para ganar monedas")
async def cmd_work(interaction: discord.Interaction):
    w = _get_wallet(interaction.guild_id, interaction.user.id)
    now = time.time()
    if now - w["last_work"] < 1800:
        restante = 1800 - (now - w["last_work"])
        m, s = divmod(int(restante), 60)
        return await interaction.response.send_message(
            f"{E_WARN} Estás cansado. Puedes volver a trabajar en `{m}m {s}s`.", ephemeral=True)
    job, lo, hi = random.choice(_WORK_JOBS)
    amount = random.randint(lo, hi)
    w["balance"] += amount
    w["last_work"] = now
    _save_eco()
    e = discord.Embed(
        description=f"{E_CHECK} Estuviste **{job}** y ganaste **+{amount}** {CURRENCY}",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="pay", description="Transfiere monedas a otro usuario")
@app_commands.describe(usuario="A quién le pagas", cantidad="Cuánto le das")
async def cmd_pay(interaction: discord.Interaction, usuario: discord.Member,
                   cantidad: app_commands.Range[int, 1, 1_000_000]):
    if usuario.id == interaction.user.id:
        return await interaction.response.send_message(f"{E_WARN} No puedes pagarte a ti mismo.", ephemeral=True)
    sender = _get_wallet(interaction.guild_id, interaction.user.id)
    if sender["balance"] < cantidad:
        return await interaction.response.send_message(f"{E_WARN} No tienes suficientes monedas.", ephemeral=True)
    receiver = _get_wallet(interaction.guild_id, usuario.id)
    sender["balance"] -= cantidad
    receiver["balance"] += cantidad
    _save_eco()
    e = discord.Embed(
        description=f"{E_CHECK} {interaction.user.mention} le pagó **{cantidad}** {CURRENCY} a {usuario.mention}",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="eco-leaderboard", description="Top 10 usuarios más ricos del servidor")
async def cmd_eco_leaderboard(interaction: discord.Interaction):
    g = economy.get(str(interaction.guild_id), {})
    ranked = sorted(g.items(), key=lambda kv: kv[1]["balance"], reverse=True)[:10]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {CURRENCY} Top economía", icon_url=URL_CROWN)
    if not ranked:
        e.description = "Nadie tiene monedas todavía."
    else:
        lines = []
        for i, (uid, d) in enumerate(ranked, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"`#{i}`")
            lines.append(f"{medal} <@{uid}> — `{d['balance']}` {CURRENCY}")
        e.description = "\n".join(lines)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="add-money", description="Agrega monedas a un usuario (Admin)")
@app_commands.describe(usuario="Usuario", cantidad="Cuánto agregar (puede ser negativo)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_add_money(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    w = _get_wallet(interaction.guild_id, usuario.id)
    w["balance"] = max(0, w["balance"] + cantidad)
    _save_eco()
    e = discord.Embed(description=f"{E_CHECK} Saldo de {usuario.mention} ahora es `{w['balance']}` {CURRENCY}",
                      color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@cmd_add_money.error
async def _add_money_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)


# ── SLASH — UTILIDAD ──────────────────────────────────────────────

@bot.tree.command(name="ping", description="Ver latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    bar = "🟥" * min(10, ms // 20)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🏓 Ping", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Latencia",   value=f"```{ms}ms```",       inline=True)
    e.add_field(name=f"{E_ARROW} Uptime",      value=f"```{_uptime()}```",  inline=True)
    e.add_field(name=f"{E_CROWN} Servidores",  value=f"```{len(bot.guilds)}```", inline=True)
    if bar: e.add_field(name="Señal", value=bar, inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="avatar", description="Muestra el avatar de un usuario")
@app_commands.describe(usuario="Usuario (por defecto tú mismo)")
async def cmd_avatar(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Avatar de {usuario.display_name}", icon_url=URL_CROWN)
    e.set_image(url=usuario.display_avatar.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="userinfo", description="Muestra información de un usuario")
@app_commands.describe(usuario="Usuario (por defecto tú mismo)")
async def cmd_userinfo(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    roles = [r.mention for r in usuario.roles if r.name != "@everyone"]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_USER} Info de usuario", icon_url=URL_CROWN)
    e.set_thumbnail(url=usuario.display_avatar.url)
    e.add_field(name=f"{E_RDIAM} Usuario", value=f"{usuario.mention}\n`{usuario}`", inline=True)
    e.add_field(name=f"{E_INFO} ID", value=f"`{usuario.id}`", inline=True)
    e.add_field(name=f"{E_ARROW} Cuenta creada", value=discord.utils.format_dt(usuario.created_at, "R"), inline=True)
    e.add_field(name=f"{E_CROWN} Se unió", value=discord.utils.format_dt(usuario.joined_at, "R") if usuario.joined_at else "—", inline=True)
    e.add_field(name=f"{E_CHECK} Roles ({len(roles)})", value=(", ".join(roles[:15]) or "Ninguno"), inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="serverinfo", description="Muestra información del servidor")
async def cmd_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_INFO} Info del servidor", icon_url=URL_CROWN)
    if g.icon: e.set_thumbnail(url=g.icon.url)
    e.add_field(name=f"{E_RDIAM} Nombre", value=g.name, inline=True)
    e.add_field(name=f"{E_CROWN} Dueño", value=g.owner.mention if g.owner else "—", inline=True)
    e.add_field(name=f"{E_USER} Miembros", value=f"`{g.member_count}`", inline=True)
    e.add_field(name=f"{E_ARROW} Creado", value=discord.utils.format_dt(g.created_at, "R"), inline=True)
    e.add_field(name=f"{E_CHECK} Canales", value=f"`{len(g.channels)}`", inline=True)
    e.add_field(name=f"{E_TICKET} Roles", value=f"`{len(g.roles)}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="clear", description="Elimina mensajes del canal (Manage Messages)")
@app_commands.describe(cantidad="Cantidad de mensajes a borrar (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear(interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=cantidad)
    e = discord.Embed(description=f"{E_CHECK} Se eliminaron **{len(deleted)}** mensajes.", color=C_RED)
    await interaction.followup.send(embed=e, ephemeral=True)

@cmd_clear.error
async def _clear_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar mensajes**.", ephemeral=True)


# ── AUTOMOD + LOGS + BIENVENIDAS ─────────────────────────────────────

GUILD_CONFIG_FILE = "guild_config.json"
# guild_config: { "guild_id": {
#   "automod_on": bool, "bad_words": [..], "mod_log": id,
#   "welcome_channel": id, "welcome_msg": str,
#   "leave_channel": id, "leave_msg": str, "autorole": id } }
guild_config: dict = load_json(GUILD_CONFIG_FILE, {})
def _save_gc(): save_json(GUILD_CONFIG_FILE, guild_config)
def _gc(guild_id: int) -> dict:
    return guild_config.setdefault(str(guild_id), {})

_last_deleted: dict = {}   # channel_id -> {"author":.., "content":.., "ts":..}
_last_edited: dict = {}    # channel_id -> {"author":.., "before":.., "after":.., "ts":..}

async def _check_automod(message: discord.Message):
    if not message.guild or message.author.guild_permissions.manage_messages: return
    cfg = _gc(message.guild.id)
    if not cfg.get("automod_on") or not cfg.get("bad_words"): return
    low = message.content.lower()
    if any(w in low for w in cfg["bad_words"]):
        try: await message.delete()
        except Exception: return
        try:
            await message.channel.send(
                f"{E_WARN} {message.author.mention}, ese mensaje contiene una palabra prohibida.",
                delete_after=6)
        except Exception: pass
        log_id = cfg.get("mod_log")
        if log_id:
            log_ch = message.guild.get_channel(log_id)
            if log_ch:
                le = discord.Embed(
                    description=f"{E_WARN} AutoMod borró un mensaje de {message.author.mention} en {message.channel.mention}",
                    color=C_RED, timestamp=datetime.now(timezone.utc))
                le.set_footer(text=_footer())
                try: await log_ch.send(embed=le)
                except Exception: pass

async def _handle_member_join(member: discord.Member):
    cfg = _gc(member.guild.id)
    role_id = cfg.get("autorole")
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            try: await member.add_roles(role, reason="Autorole")
            except Exception: pass

    ch_id = cfg.get("welcome_channel")
    if ch_id:
        ch = member.guild.get_channel(ch_id)
        if ch:
            msg = cfg.get("welcome_msg") or "¡Bienvenido {user} a {server}!"
            text = msg.replace("{user}", member.mention).replace("{server}", member.guild.name)
            e = discord.Embed(description=text, color=C_RED, timestamp=datetime.now(timezone.utc))
            e.set_author(name=f"{BOT_NAME} — 👋 Nuevo miembro", icon_url=URL_CROWN)
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_footer(text=_footer())
            try: await ch.send(embed=e)
            except Exception: pass

    log_id = cfg.get("mod_log")
    if log_id:
        log_ch = member.guild.get_channel(log_id)
        if log_ch:
            le = discord.Embed(description=f"{E_CHECK} {member.mention} se unió al servidor.",
                              color=C_RED, timestamp=datetime.now(timezone.utc))
            le.set_footer(text=_footer())
            try: await log_ch.send(embed=le)
            except Exception: pass

async def _handle_member_remove(member: discord.Member):
    cfg = _gc(member.guild.id)
    ch_id = cfg.get("leave_channel")
    if ch_id:
        ch = member.guild.get_channel(ch_id)
        if ch:
            msg = cfg.get("leave_msg") or "{user} salió del servidor."
            text = msg.replace("{user}", str(member)).replace("{server}", member.guild.name)
            e = discord.Embed(description=text, color=C_RED, timestamp=datetime.now(timezone.utc))
            e.set_author(name=f"{BOT_NAME} — 👋 Se fue un miembro", icon_url=URL_CROWN)
            e.set_footer(text=_footer())
            try: await ch.send(embed=e)
            except Exception: pass

    log_id = cfg.get("mod_log")
    if log_id:
        log_ch = member.guild.get_channel(log_id)
        if log_ch:
            le = discord.Embed(description=f"{E_NO} {member} salió del servidor.",
                              color=C_RED, timestamp=datetime.now(timezone.utc))
            le.set_footer(text=_footer())
            try: await log_ch.send(embed=le)
            except Exception: pass

async def _handle_message_delete(message: discord.Message):
    if not message.guild or message.author.bot: return
    _last_deleted[message.channel.id] = {
        "author": str(message.author), "content": message.content or "*(sin texto / adjunto)*",
        "ts": time.time()}
    cfg = _gc(message.guild.id)
    log_id = cfg.get("mod_log")
    if log_id:
        log_ch = message.guild.get_channel(log_id)
        if log_ch and log_ch.id != message.channel.id:
            le = discord.Embed(
                description=f"🗑️ Mensaje borrado en {message.channel.mention} de {message.author.mention}",
                color=C_RED, timestamp=datetime.now(timezone.utc))
            le.add_field(name="Contenido", value=(message.content or "*(sin texto)*")[:1000], inline=False)
            le.set_footer(text=_footer())
            try: await log_ch.send(embed=le)
            except Exception: pass

async def _handle_message_edit(before: discord.Message, after: discord.Message):
    if not before.guild or before.author.bot or before.content == after.content: return
    _last_edited[before.channel.id] = {
        "author": str(before.author), "before": before.content, "after": after.content,
        "ts": time.time()}
    cfg = _gc(before.guild.id)
    log_id = cfg.get("mod_log")
    if log_id:
        log_ch = before.guild.get_channel(log_id)
        if log_ch and log_ch.id != before.channel.id:
            le = discord.Embed(
                description=f"✏️ Mensaje editado en {before.channel.mention} de {before.author.mention}",
                color=C_RED, timestamp=datetime.now(timezone.utc))
            le.add_field(name="Antes", value=(before.content or "*(vacío)*")[:500], inline=False)
            le.add_field(name="Después", value=(after.content or "*(vacío)*")[:500], inline=False)
            le.set_footer(text=_footer())
            try: await log_ch.send(embed=le)
            except Exception: pass


@bot.tree.command(name="automod-toggle", description="Activa/desactiva el filtro de palabras (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_automod_toggle(interaction: discord.Interaction):
    cfg = _gc(interaction.guild_id)
    cfg["automod_on"] = not cfg.get("automod_on", False)
    _save_gc()
    estado = "activado ✅" if cfg["automod_on"] else "desactivado ❌"
    await interaction.response.send_message(
        embed=discord.Embed(description=f"AutoMod {estado}.", color=C_RED), ephemeral=True)

@bot.tree.command(name="automod-addword", description="Agrega una palabra prohibida (Admin)")
@app_commands.describe(palabra="Palabra a bloquear")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_automod_addword(interaction: discord.Interaction, palabra: str):
    cfg = _gc(interaction.guild_id)
    cfg.setdefault("bad_words", [])
    w = palabra.lower().strip()
    if w in cfg["bad_words"]:
        return await interaction.response.send_message(f"{E_WARN} Esa palabra ya está en la lista.", ephemeral=True)
    cfg["bad_words"].append(w)
    _save_gc()
    await interaction.response.send_message(f"{E_CHECK} Palabra agregada al filtro.", ephemeral=True)

@bot.tree.command(name="automod-removeword", description="Quita una palabra prohibida (Admin)")
@app_commands.describe(palabra="Palabra a quitar")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_automod_removeword(interaction: discord.Interaction, palabra: str):
    cfg = _gc(interaction.guild_id)
    w = palabra.lower().strip()
    if w not in cfg.get("bad_words", []):
        return await interaction.response.send_message(f"{E_WARN} Esa palabra no está en la lista.", ephemeral=True)
    cfg["bad_words"].remove(w)
    _save_gc()
    await interaction.response.send_message(f"{E_CHECK} Palabra quitada del filtro.", ephemeral=True)

@bot.tree.command(name="automod-words", description="Lista las palabras filtradas (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_automod_words(interaction: discord.Interaction):
    words = _gc(interaction.guild_id).get("bad_words", [])
    e = discord.Embed(
        description=("`" + "`, `".join(words) + "`") if words else "No hay palabras filtradas.",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

async def _admin_perm_error(i: discord.Interaction, e: app_commands.AppCommandError):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)
    else:
        logger.warning(f"command error: {e}")

for _c in (cmd_automod_toggle, cmd_automod_addword, cmd_automod_removeword, cmd_automod_words):
    _c.error(_admin_perm_error)


@bot.tree.command(name="setmodlog", description="Define el canal de logs de moderación (Admin)")
@app_commands.describe(canal="Canal donde se registrarán los eventos")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setmodlog(interaction: discord.Interaction, canal: discord.TextChannel):
    _gc(interaction.guild_id)["mod_log"] = canal.id
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Canal de logs: {canal.mention}", color=C_RED), ephemeral=True)

@bot.tree.command(name="welcome-setup", description="Configura el mensaje de bienvenida (Admin)")
@app_commands.describe(canal="Canal de bienvenida", mensaje="Usa {user} y {server} como variables")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_welcome_setup(interaction: discord.Interaction, canal: discord.TextChannel,
                             mensaje: str = "¡Bienvenido {user} a {server}!"):
    cfg = _gc(interaction.guild_id)
    cfg["welcome_channel"], cfg["welcome_msg"] = canal.id, mensaje
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Bienvenidas configuradas en {canal.mention}", color=C_RED),
        ephemeral=True)

@bot.tree.command(name="leave-setup", description="Configura el mensaje de despedida (Admin)")
@app_commands.describe(canal="Canal de despedidas", mensaje="Usa {user} y {server} como variables")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_leave_setup(interaction: discord.Interaction, canal: discord.TextChannel,
                           mensaje: str = "{user} salió del servidor."):
    cfg = _gc(interaction.guild_id)
    cfg["leave_channel"], cfg["leave_msg"] = canal.id, mensaje
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Despedidas configuradas en {canal.mention}", color=C_RED),
        ephemeral=True)

for _c in (cmd_setmodlog, cmd_welcome_setup, cmd_leave_setup):
    _c.error(_admin_perm_error)


@bot.tree.command(name="snipe", description="Muestra el último mensaje borrado del canal")
async def cmd_snipe(interaction: discord.Interaction):
    d = _last_deleted.get(interaction.channel.id)
    if not d:
        return await interaction.response.send_message(f"{E_WARN} No hay nada que snipear aquí.", ephemeral=True)
    e = discord.Embed(description=d["content"][:1000], color=C_RED,
                      timestamp=datetime.fromtimestamp(d["ts"], tz=timezone.utc))
    e.set_author(name=f"{d['author']} dijo:")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="editsnipe", description="Muestra la última edición de mensaje en el canal")
async def cmd_editsnipe(interaction: discord.Interaction):
    d = _last_edited.get(interaction.channel.id)
    if not d:
        return await interaction.response.send_message(f"{E_WARN} No hay nada que snipear aquí.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.fromtimestamp(d["ts"], tz=timezone.utc))
    e.set_author(name=f"{d['author']} editó:")
    e.add_field(name="Antes", value=(d["before"] or "*(vacío)*")[:500], inline=False)
    e.add_field(name="Después", value=(d["after"] or "*(vacío)*")[:500], inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


# ── ROLES ────────────────────────────────────────────────────────────

@bot.tree.command(name="addrole", description="Da un rol a un usuario (Manage Roles)")
@app_commands.describe(usuario="Usuario", rol="Rol a asignar")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_addrole(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    try:
        await usuario.add_roles(rol, reason=f"Por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permiso para dar ese rol.", ephemeral=True)
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} {rol.mention} agregado a {usuario.mention}", color=C_RED))

@bot.tree.command(name="removerole", description="Quita un rol a un usuario (Manage Roles)")
@app_commands.describe(usuario="Usuario", rol="Rol a quitar")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_removerole(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    try:
        await usuario.remove_roles(rol, reason=f"Por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No tengo permiso para quitar ese rol.", ephemeral=True)
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} {rol.mention} quitado a {usuario.mention}", color=C_RED))

@bot.tree.command(name="autorole-set", description="Rol automático al unirse alguien (Admin)")
@app_commands.describe(rol="Rol a asignar automáticamente")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_autorole_set(interaction: discord.Interaction, rol: discord.Role):
    _gc(interaction.guild_id)["autorole"] = rol.id
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Autorole: {rol.mention}", color=C_RED), ephemeral=True)

@bot.tree.command(name="autorole-off", description="Desactiva el rol automático (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_autorole_off(interaction: discord.Interaction):
    _gc(interaction.guild_id)["autorole"] = None
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Autorole desactivado.", color=C_RED), ephemeral=True)

async def _manage_roles_perm_error(i: discord.Interaction, e: app_commands.AppCommandError):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar roles**.", ephemeral=True)
    else:
        logger.warning(f"command error: {e}")

for _c in (cmd_addrole, cmd_removerole):
    _c.error(_manage_roles_perm_error)
for _c in (cmd_autorole_set, cmd_autorole_off):
    _c.error(_admin_perm_error)


class RoleMenuSelect(Select):
    def __init__(self, options_map: dict):
        # options_map: {role_id(str): label}
        opts = [discord.SelectOption(label=label, value=rid) for rid, label in options_map.items()]
        super().__init__(placeholder="Elige tus roles...", min_values=0,
                         max_values=len(opts), options=opts,
                         custom_id="king_rolemenu_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        chosen = set(self.values)
        all_ids = {opt.value for opt in self.options}
        added, removed = [], []
        for rid in all_ids:
            role = guild.get_role(int(rid))
            if not role: continue
            has = role in interaction.user.roles
            if rid in chosen and not has:
                await interaction.user.add_roles(role, reason="Rolemenu"); added.append(role.mention)
            elif rid not in chosen and has:
                await interaction.user.remove_roles(role, reason="Rolemenu"); removed.append(role.mention)
        msg = []
        if added: msg.append(f"{E_CHECK} Agregado: {', '.join(added)}")
        if removed: msg.append(f"{E_NO} Quitado: {', '.join(removed)}")
        await interaction.response.send_message("\n".join(msg) or "Sin cambios.", ephemeral=True)

class RoleMenuView(View):
    def __init__(self, options_map: dict):
        super().__init__(timeout=None)
        self.add_item(RoleMenuSelect(options_map))

@bot.tree.command(name="rolemenu-create", description="Crea un menú de roles auto-asignables (Admin)")
@app_commands.describe(titulo="Título del panel",
                        rol1="Rol 1", rol2="Rol 2 (opcional)",
                        rol3="Rol 3 (opcional)", rol4="Rol 4 (opcional)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_rolemenu_create(interaction: discord.Interaction, titulo: str,
                               rol1: discord.Role, rol2: discord.Role = None,
                               rol3: discord.Role = None, rol4: discord.Role = None):
    roles = [r for r in (rol1, rol2, rol3, rol4) if r]
    options_map = {str(r.id): r.name for r in roles}
    e = discord.Embed(description=titulo, color=C_RED)
    e.set_author(name=f"{BOT_NAME} — 🎭 Roles", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.channel.send(embed=e, view=RoleMenuView(options_map))
    await interaction.response.send_message(f"{E_CHECK} Menú de roles publicado.", ephemeral=True)

@cmd_rolemenu_create.error
async def _rolemenu_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)


# ── IMÁGENES (Pillow) ────────────────────────────────────────────────

async def _get_avatar_image(member: discord.Member, size: int = 512) -> Image.Image:
    data = await member.display_avatar.replace(size=size, format="png").read()
    return Image.open(BytesIO(data)).convert("RGBA")

def _to_file(img: Image.Image, name: str) -> discord.File:
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return discord.File(buf, filename=name)

def _circle_mask(img: Image.Image) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, img.size[0], img.size[1]], fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out

@bot.tree.command(name="pfp-circle", description="Recorta tu avatar en círculo")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_pfp_circle(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    img = _circle_mask(await _get_avatar_image(usuario))
    await interaction.followup.send(file=_to_file(img, "circle.png"))

@bot.tree.command(name="pfp-invert", description="Invierte los colores de tu avatar")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_pfp_invert(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    img = await _get_avatar_image(usuario)
    rgb = img.convert("RGB")
    inv = ImageOps.invert(rgb).convert("RGBA")
    inv.putalpha(img.getchannel("A"))
    await interaction.followup.send(file=_to_file(inv, "invert.png"))

@bot.tree.command(name="pfp-grayscale", description="Pone tu avatar en blanco y negro")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_pfp_grayscale(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    img = await _get_avatar_image(usuario)
    gray = ImageOps.grayscale(img.convert("RGB")).convert("RGBA")
    gray.putalpha(img.getchannel("A"))
    await interaction.followup.send(file=_to_file(gray, "grayscale.png"))

@bot.tree.command(name="pfp-blur", description="Difumina tu avatar")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_pfp_blur(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    img = await _get_avatar_image(usuario)
    blurred = img.filter(ImageFilter.GaussianBlur(8))
    await interaction.followup.send(file=_to_file(blurred, "blur.png"))

@bot.tree.command(name="pfp-pixelate", description="Pixela tu avatar")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_pfp_pixelate(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    img = await _get_avatar_image(usuario)
    small = img.resize((32, 32), Image.NEAREST)
    pixelated = small.resize(img.size, Image.NEAREST)
    await interaction.followup.send(file=_to_file(pixelated, "pixelate.png"))

@bot.tree.command(name="jail", description="Te mete a la cárcel 🚔")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_jail(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    img = (await _get_avatar_image(usuario)).resize((512, 512))
    draw = ImageDraw.Draw(img)
    bar_w = 22
    for x in range(0, 512, 64):
        draw.rectangle([x, 0, x + bar_w, 512], fill=(10, 10, 10, 235))
    await interaction.followup.send(file=_to_file(img, "jail.png"))

@bot.tree.command(name="wanted", description="Crea un cartel de SE BUSCA con tu avatar")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_wanted(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    await interaction.response.defer()
    avatar = (await _get_avatar_image(usuario)).resize((420, 420))
    poster = Image.new("RGB", (500, 620), (222, 196, 150))
    draw = ImageDraw.Draw(poster)
    draw.rectangle([10, 10, 489, 609], outline=(60, 30, 10), width=6)
    f_title = _load_font(56)
    f_sub = _load_font(28)
    tw = draw.textlength("SE BUSCA", font=f_title)
    draw.text(((500 - tw) / 2, 30), "SE BUSCA", font=f_title, fill=(40, 20, 10))
    poster.paste(avatar, (40, 120), avatar)
    sub = f"{usuario.display_name}"[:22]
    tw2 = draw.textlength(sub, font=f_sub)
    draw.text(((500 - tw2) / 2, 555), sub, font=f_sub, fill=(40, 20, 10))
    await interaction.followup.send(file=_to_file(poster.convert("RGBA"), "wanted.png"))

@bot.tree.command(name="meme", description="Crea un meme con texto arriba/abajo")
@app_commands.describe(arriba="Texto de arriba (opcional)", abajo="Texto de abajo (opcional)",
                        imagen="Imagen a usar (si no, usa tu avatar)")
async def cmd_meme(interaction: discord.Interaction, arriba: str = "", abajo: str = "",
                    imagen: discord.Attachment = None):
    await interaction.response.defer()
    if imagen:
        data = await imagen.read()
        img = Image.open(BytesIO(data)).convert("RGBA")
        if img.width > 800:
            ratio = 800 / img.width
            img = img.resize((800, int(img.height * ratio)))
    else:
        img = (await _get_avatar_image(interaction.user)).resize((512, 512))

    draw = ImageDraw.Draw(img)
    font = _load_font(max(24, img.width // 14))

    def _draw_impact(text, y):
        text = text.upper()
        tw = draw.textlength(text, font=font)
        x = max(4, (img.width - tw) / 2)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=(255, 255, 255))

    if arriba: _draw_impact(arriba, 10)
    if abajo: _draw_impact(abajo, img.height - font.size - 20)

    await interaction.followup.send(file=_to_file(img, "meme.png"))


@bot.tree.command(name="qr", description="Genera un código QR")
@app_commands.describe(texto="Texto o URL a codificar")
async def cmd_qr(interaction: discord.Interaction, texto: str):
    if not HAS_QRCODE:
        return await interaction.response.send_message(
            f"{E_WARN} Falta instalar la librería `qrcode` en el servidor del bot (`pip install qrcode[pil]`).",
            ephemeral=True)
    await interaction.response.defer()
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    await interaction.followup.send(file=_to_file(img, "qr.png"))


@bot.tree.command(name="color", description="Muestra una muestra de color a partir de un código HEX")
@app_commands.describe(hex_code="Código de color, ej: #FF0000 o FF0000")
async def cmd_color(interaction: discord.Interaction, hex_code: str):
    h = hex_code.strip().lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        return await interaction.response.send_message(f"{E_WARN} Código HEX inválido. Ej: `#FF0000`", ephemeral=True)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    img = Image.new("RGB", (300, 300), (r, g, b))
    e = discord.Embed(description=f"HEX: `#{h.upper()}`\nRGB: `({r}, {g}, {b})`", color=discord.Color(int(h, 16)))
    e.set_thumbnail(url="attachment://color.png")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, file=_to_file(img.convert("RGBA"), "color.png"))


# ── UTILIDAD EXTRA (web) ─────────────────────────────────────────────

@bot.tree.command(name="membercount", description="Cuántos miembros tiene el servidor")
async def cmd_membercount(interaction: discord.Interaction):
    g = interaction.guild
    humans = sum(1 for m in g.members if not m.bot)
    bots = g.member_count - humans
    e = discord.Embed(
        description=f"{E_USER} **{g.member_count}** miembros totales\n"
                    f"👤 `{humans}` humanos  •  🤖 `{bots}` bots",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="botinfo", description="Información sobre el bot")
async def cmd_botinfo(interaction: discord.Interaction):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME}", icon_url=URL_CROWN)
    e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="Latencia", value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.add_field(name="Librería", value=f"`discord.py {discord.__version__}`", inline=True)
    e.add_field(name="Prefijo por nombre", value=f"`{BOT_NAME}` o `{BOT_TRIGGER}`", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="invite", description="Genera un link de invitación del servidor")
async def cmd_invite(interaction: discord.Interaction):
    try:
        invite = await interaction.channel.create_invite(max_age=86400, reason=f"Pedido por {interaction.user}")
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{E_CHECK} {invite.url}", color=C_RED), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"{E_WARN} No tengo permiso para crear invitaciones.", ephemeral=True)

@bot.tree.command(name="firstmessage", description="Salta al primer mensaje del canal")
async def cmd_firstmessage(interaction: discord.Interaction):
    await interaction.response.defer()
    async for msg in interaction.channel.history(limit=1, oldest_first=True):
        return await interaction.followup.send(
            embed=discord.Embed(description=f"{E_ARROW} [Primer mensaje]({msg.jump_url}) — por {msg.author.mention}",
                                color=C_RED))
    await interaction.followup.send(f"{E_WARN} No encontré mensajes.")

@bot.tree.command(name="define", description="Busca la definición de una palabra (inglés)")
@app_commands.describe(palabra="Palabra a buscar")
async def cmd_define(interaction: discord.Interaction, palabra: str):
    await interaction.response.defer()
    loop = asyncio.get_running_loop()
    try:
        r = await loop.run_in_executor(None, lambda: requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(palabra)}", timeout=8))
        data = r.json()
        if not isinstance(data, list): raise ValueError("no results")
        meaning = data[0]["meanings"][0]
        definition = meaning["definitions"][0]["definition"]
        pos = meaning.get("partOfSpeech", "")
        e = discord.Embed(description=f"**{palabra}** *({pos})*\n{definition}", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(f"{E_WARN} No encontré una definición para `{palabra}`.")

@bot.tree.command(name="shorten", description="Acorta una URL")
@app_commands.describe(url="Enlace a acortar")
async def cmd_shorten(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    loop = asyncio.get_running_loop()
    try:
        r = await loop.run_in_executor(None, lambda: requests.get(
            "https://is.gd/create.php", params={"format": "simple", "url": url}, timeout=8))
        if not r.text.startswith("http"): raise ValueError(r.text)
        e = discord.Embed(description=f"{E_CHECK} {r.text.strip()}", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(f"{E_WARN} No pude acortar ese enlace.")

@bot.tree.command(name="weather", description="Ver el clima de una ciudad")
@app_commands.describe(ciudad="Nombre de la ciudad")
async def cmd_weather(interaction: discord.Interaction, ciudad: str):
    await interaction.response.defer()
    loop = asyncio.get_running_loop()
    try:
        r = await loop.run_in_executor(None, lambda: requests.get(
            f"https://wttr.in/{quote(ciudad)}", params={"format": "3"}, timeout=8))
        e = discord.Embed(description=f"🌤️ {r.text.strip()}", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(f"{E_WARN} No pude obtener el clima de `{ciudad}`.")

@bot.tree.command(name="translate", description="Traduce un texto")
@app_commands.describe(texto="Texto a traducir", idioma_destino="Código de idioma, ej: en, es, fr")
async def cmd_translate(interaction: discord.Interaction, texto: str, idioma_destino: str = "en"):
    await interaction.response.defer()
    loop = asyncio.get_running_loop()
    try:
        r = await loop.run_in_executor(None, lambda: requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": texto, "langpair": f"auto|{idioma_destino}"}, timeout=8))
        data = r.json()
        translated = data["responseData"]["translatedText"]
        e = discord.Embed(color=C_RED)
        e.add_field(name="Original", value=texto[:500], inline=False)
        e.add_field(name=f"Traducido ({idioma_destino})", value=translated[:500], inline=False)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(f"{E_WARN} No pude traducir ese texto.")


SUGGESTION_FILE_CFG = "suggest_channel"

@bot.tree.command(name="suggest-setup", description="Define el canal de sugerencias (Admin)")
@app_commands.describe(canal="Canal donde se publicarán las sugerencias")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_suggest_setup(interaction: discord.Interaction, canal: discord.TextChannel):
    _gc(interaction.guild_id)[SUGGESTION_FILE_CFG] = canal.id
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Sugerencias en {canal.mention}", color=C_RED), ephemeral=True)

@cmd_suggest_setup.error
async def _suggest_setup_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)

@bot.tree.command(name="suggest", description="Envía una sugerencia para el servidor")
@app_commands.describe(texto="Tu sugerencia")
async def cmd_suggest(interaction: discord.Interaction, texto: str):
    ch_id = _gc(interaction.guild_id).get(SUGGESTION_FILE_CFG)
    channel = interaction.guild.get_channel(ch_id) if ch_id else interaction.channel
    if channel is None:
        return await interaction.response.send_message(f"{E_WARN} Canal de sugerencias no válido.", ephemeral=True)
    e = discord.Embed(description=texto, color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"💡 Sugerencia de {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    e.set_footer(text=_footer())
    msg = await channel.send(embed=e)
    for r in ("👍", "👎"):
        try: await msg.add_reaction(r)
        except Exception: pass
    await interaction.response.send_message(f"{E_CHECK} Sugerencia enviada en {channel.mention}", ephemeral=True)


# ── GESTIÓN DE SERVIDOR ──────────────────────────────────────────────

@bot.tree.command(name="lock", description="Bloquea el canal actual (Manage Channels)")
@app_commands.describe(razon="Motivo (opcional)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_lock(interaction: discord.Interaction, razon: str = "Sin especificar"):
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow,
                                              reason=f"{razon} — por {interaction.user}")
    e = discord.Embed(description=f"{E_LOCK} Canal bloqueado. Razón: {razon}", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="unlock", description="Desbloquea el canal actual (Manage Channels)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_unlock(interaction: discord.Interaction):
    ow = interaction.channel.overwrites_for(interaction.guild.default_role)
    ow.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=ow,
                                              reason=f"Por {interaction.user}")
    e = discord.Embed(description=f"{E_CHECK} Canal desbloqueado.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="slowmode", description="Cambia el modo lento del canal (Manage Channels)")
@app_commands.describe(segundos="Segundos entre mensajes (0 para desactivar, máx 21600)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_slowmode(interaction: discord.Interaction, segundos: app_commands.Range[int, 0, 21600]):
    await interaction.channel.edit(slowmode_delay=segundos, reason=f"Por {interaction.user}")
    txt = "desactivado" if segundos == 0 else f"{segundos}s por mensaje"
    e = discord.Embed(description=f"{E_CHECK} Modo lento {txt}.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="nickname", description="Cambia el apodo de un usuario (Manage Nicknames)")
@app_commands.describe(usuario="Usuario", apodo="Nuevo apodo (vacío para quitarlo)")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def cmd_nickname(interaction: discord.Interaction, usuario: discord.Member, apodo: str = None):
    try:
        await usuario.edit(nick=apodo, reason=f"Por {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(f"{E_WARN} No puedo cambiar el apodo de ese usuario.", ephemeral=True)
    e = discord.Embed(description=f"{E_CHECK} Apodo de {usuario.mention} actualizado.", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="nuke", description="Vacía por completo el canal actual clonándolo (Manage Channels)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_nuke(interaction: discord.Interaction):
    channel = interaction.channel
    await interaction.response.send_message(f"{E_WARN} Reiniciando este canal...", ephemeral=True)
    new_ch = await channel.clone(reason=f"Nuke por {interaction.user}")
    await new_ch.edit(position=channel.position)
    e = discord.Embed(description=f"{E_CHECK} Canal reiniciado por {interaction.user.mention}", color=C_RED)
    e.set_footer(text=_footer())
    await new_ch.send(embed=e)
    await channel.delete(reason=f"Nuke por {interaction.user}")

async def _manage_channels_perm_error(i: discord.Interaction, e: app_commands.AppCommandError):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar canales**.", ephemeral=True)
    else:
        logger.warning(f"command error: {e}")

for _c in (cmd_lock, cmd_unlock, cmd_slowmode):
    _c.error(_manage_channels_perm_error)
cmd_nuke.error(_admin_perm_error)

@cmd_nickname.error
async def _nickname_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar apodos**.", ephemeral=True)


@bot.tree.command(name="channelinfo", description="Información del canal actual")
async def cmd_channelinfo(interaction: discord.Interaction):
    ch = interaction.channel
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — #️⃣ Info del canal", icon_url=URL_CROWN)
    e.add_field(name="Nombre", value=ch.name, inline=True)
    e.add_field(name="ID", value=f"`{ch.id}`", inline=True)
    e.add_field(name="Tipo", value=str(ch.type), inline=True)
    e.add_field(name="Creado", value=discord.utils.format_dt(ch.created_at, "R"), inline=True)
    if isinstance(ch, discord.TextChannel):
        e.add_field(name="Modo lento", value=f"{ch.slowmode_delay}s", inline=True)
        e.add_field(name="NSFW", value="Sí" if ch.is_nsfw() else "No", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="roleinfo", description="Información de un rol")
@app_commands.describe(rol="Rol a consultar")
async def cmd_roleinfo(interaction: discord.Interaction, rol: discord.Role):
    e = discord.Embed(color=rol.color if rol.color.value else C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎭 Info de rol", icon_url=URL_CROWN)
    e.add_field(name="Nombre", value=rol.mention, inline=True)
    e.add_field(name="ID", value=f"`{rol.id}`", inline=True)
    e.add_field(name="Color", value=str(rol.color), inline=True)
    e.add_field(name="Miembros", value=f"`{len(rol.members)}`", inline=True)
    e.add_field(name="Posición", value=f"`{rol.position}`", inline=True)
    e.add_field(name="Mencionable", value="Sí" if rol.mentionable else "No", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="emojilist", description="Lista los emojis personalizados del servidor")
async def cmd_emojilist(interaction: discord.Interaction):
    emojis = interaction.guild.emojis
    if not emojis:
        return await interaction.response.send_message(f"{E_WARN} Este servidor no tiene emojis personalizados.", ephemeral=True)
    txt = " ".join(str(em) for em in emojis[:80])
    e = discord.Embed(description=txt, color=C_RED)
    e.set_author(name=f"{BOT_NAME} — 😀 Emojis ({len(emojis)})", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="banner", description="Muestra el banner del servidor")
async def cmd_banner(interaction: discord.Interaction):
    g = interaction.guild
    if not g.banner:
        return await interaction.response.send_message(f"{E_WARN} Este servidor no tiene banner.", ephemeral=True)
    e = discord.Embed(color=C_RED)
    e.set_author(name=f"{BOT_NAME} — 🖼️ Banner de {g.name}", icon_url=URL_CROWN)
    e.set_image(url=g.banner.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="report", description="Reporta a un usuario a los moderadores")
@app_commands.describe(usuario="Usuario a reportar", razon="Motivo del reporte")
async def cmd_report(interaction: discord.Interaction, usuario: discord.Member, razon: str):
    cfg = _gc(interaction.guild_id)
    log_id = cfg.get("mod_log")
    channel = interaction.guild.get_channel(log_id) if log_id else None
    if channel is None:
        return await interaction.response.send_message(
            f"{E_WARN} No hay un canal de logs configurado (`/setmodlog`), avisa a un admin directamente.",
            ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"🚨 Reporte de {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    e.add_field(name="Usuario reportado", value=usuario.mention, inline=True)
    e.add_field(name="Canal", value=interaction.channel.mention, inline=True)
    e.add_field(name="Motivo", value=razon, inline=False)
    e.set_footer(text=_footer())
    await channel.send(embed=e)
    await interaction.response.send_message(f"{E_CHECK} Reporte enviado a los moderadores.", ephemeral=True)

@bot.tree.command(name="audit-log", description="Muestra las últimas acciones del registro de auditoría (Admin)")
@app_commands.checks.has_permissions(view_audit_log=True)
async def cmd_audit_log(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    lines = []
    async for entry in interaction.guild.audit_logs(limit=8):
        lines.append(f"`{entry.action.name}` — {entry.user} → {entry.target} • "
                     f"{discord.utils.format_dt(entry.created_at, 'R')}")
    e = discord.Embed(description="\n".join(lines) or "Sin registros.", color=C_RED)
    e.set_author(name=f"{BOT_NAME} — 📜 Audit Log", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.followup.send(embed=e, ephemeral=True)

@cmd_audit_log.error
async def _audit_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Ver registro de auditoría**.", ephemeral=True)


# ── STARBOARD ─────────────────────────────────────────────────────────

STARBOARD_FILE = "starboard.json"
# starboard cfg vive en guild_config bajo "star_channel"/"star_threshold"/"star_emoji"
# starboard_posts: { "original_message_id": starboard_message_id }
starboard_posts: dict = load_json(STARBOARD_FILE, {})
def _save_star(): save_json(STARBOARD_FILE, starboard_posts)

async def _handle_starboard_reaction(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None: return
    cfg = _gc(payload.guild_id)
    channel_id = cfg.get("star_channel")
    if not channel_id: return
    emoji = cfg.get("star_emoji", "⭐")
    if str(payload.emoji) != emoji: return
    threshold = cfg.get("star_threshold", 3)

    guild = bot.get_guild(payload.guild_id)
    if not guild: return
    src_channel = guild.get_channel(payload.channel_id)
    if src_channel is None or src_channel.id == channel_id: return
    try:
        message = await src_channel.fetch_message(payload.message_id)
    except Exception:
        return
    reaction = discord.utils.get(message.reactions, emoji=emoji)
    count = reaction.count if reaction else 0
    if count < threshold: return

    board = guild.get_channel(channel_id)
    if board is None: return

    key = str(message.id)
    e = discord.Embed(description=message.content or "*(sin texto)*", color=discord.Color.gold(),
                      timestamp=message.created_at)
    e.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    e.add_field(name="Fuente", value=f"[Ir al mensaje]({message.jump_url}) en {src_channel.mention}", inline=False)
    if message.attachments:
        e.set_image(url=message.attachments[0].url)
    e.set_footer(text=f"{emoji} {count} • {_footer()}")

    existing_id = starboard_posts.get(key)
    if existing_id:
        try:
            star_msg = await board.fetch_message(existing_id)
            await star_msg.edit(embed=e)
            return
        except Exception:
            pass

    star_msg = await board.send(content=f"{emoji} **{count}** — {src_channel.mention}", embed=e)
    starboard_posts[key] = star_msg.id
    _save_star()


@bot.tree.command(name="starboard-setup", description="Configura el starboard (Admin)")
@app_commands.describe(canal="Canal donde se publicarán los mensajes destacados",
                        umbral="Cantidad de reacciones necesarias (por defecto 3)",
                        emoji="Emoji a contar (por defecto ⭐)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_starboard_setup(interaction: discord.Interaction, canal: discord.TextChannel,
                               umbral: app_commands.Range[int, 1, 50] = 3, emoji: str = "⭐"):
    cfg = _gc(interaction.guild_id)
    cfg["star_channel"], cfg["star_threshold"], cfg["star_emoji"] = canal.id, umbral, emoji
    _save_gc()
    e = discord.Embed(
        description=f"{E_CHECK} Starboard activo en {canal.mention}\nUmbral: `{umbral}` {emoji}",
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="starboard-off", description="Desactiva el starboard (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_starboard_off(interaction: discord.Interaction):
    cfg = _gc(interaction.guild_id)
    cfg["star_channel"] = None
    _save_gc()
    await interaction.response.send_message(
        embed=discord.Embed(description=f"{E_CHECK} Starboard desactivado.", color=C_RED), ephemeral=True)

for _c in (cmd_starboard_setup, cmd_starboard_off):
    _c.error(_admin_perm_error)


# ── MINIJUEGOS / DIVERSIÓN AVANZADA ──────────────────────────────────

_TRIVIA_BANK = [
    ("¿Cuál es el planeta más grande del sistema solar?", ["Júpiter", "Saturno", "Tierra", "Marte"], 0),
    ("¿En qué año llegó el hombre a la luna?", ["1965", "1969", "1972", "1959"], 1),
    ("¿Cuál es el río más largo del mundo?", ["Nilo", "Amazonas", "Yangtsé", "Misisipi"], 1),
    ("¿Cuántos huesos tiene el cuerpo humano adulto?", ["206", "180", "220", "195"], 0),
    ("¿Qué lenguaje de programación creó Guido van Rossum?", ["Java", "Python", "Ruby", "C++"], 1),
    ("¿Cuál es el océano más grande?", ["Atlántico", "Índico", "Pacífico", "Ártico"], 2),
    ("¿Cuántos jugadores tiene un equipo de fútbol en cancha?", ["9", "10", "11", "12"], 2),
]

class TriviaView(View):
    def __init__(self, correct_idx: int, author_id: int):
        super().__init__(timeout=20)
        self.correct_idx = correct_idx
        self.author_id = author_id
        self.answered = False

    async def _answer(self, interaction: discord.Interaction, idx: int):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(f"{E_WARN} Esta trivia no es tuya.", ephemeral=True)
        if self.answered:
            return await interaction.response.send_message(f"{E_WARN} Ya respondiste.", ephemeral=True)
        self.answered = True
        for item in self.children: item.disabled = True
        correct = idx == self.correct_idx
        for i, item in enumerate(self.children):
            item.style = discord.ButtonStyle.success if i == self.correct_idx else (
                discord.ButtonStyle.danger if i == idx else discord.ButtonStyle.secondary)
        msg = f"{E_CHECK} ¡Correcto!" if correct else f"{E_NO} Incorrecto."
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(msg, ephemeral=True)
        self.stop()

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def a(self, i, _): await self._answer(i, 0)
    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def b(self, i, _): await self._answer(i, 1)
    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def c(self, i, _): await self._answer(i, 2)
    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def d(self, i, _): await self._answer(i, 3)

@bot.tree.command(name="trivia", description="Responde una pregunta de trivia")
async def cmd_trivia(interaction: discord.Interaction):
    q, options, correct = random.choice(_TRIVIA_BANK)
    letters = ["A", "B", "C", "D"]
    desc = "\n".join(f"**{letters[i]}.** {opt}" for i, opt in enumerate(options))
    e = discord.Embed(description=f"**{q}**\n\n{desc}", color=C_RED)
    e.set_author(name=f"{BOT_NAME} — 🧠 Trivia", icon_url=URL_CROWN)
    e.set_footer(text="Tienes 20 segundos para responder.")
    await interaction.response.send_message(embed=e, view=TriviaView(correct, interaction.user.id))

@bot.tree.command(name="ship", description="Calcula la compatibilidad entre dos usuarios 💘")
@app_commands.describe(usuario1="Primer usuario", usuario2="Segundo usuario")
async def cmd_ship(interaction: discord.Interaction, usuario1: discord.Member, usuario2: discord.Member):
    seed = usuario1.id + usuario2.id
    pct = seed % 101
    bar_filled = "❤️" * (pct // 10)
    bar_empty = "🖤" * (10 - pct // 10)
    e = discord.Embed(
        description=(f"**{usuario1.display_name}** 💘 **{usuario2.display_name}**\n\n"
                     f"{bar_filled}{bar_empty}\n**{pct}%** de compatibilidad"),
        color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="mock", description="sPoNgEbOb CaSe a tu texto")
@app_commands.describe(texto="Texto a transformar")
async def cmd_mock(interaction: discord.Interaction, texto: str):
    out = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(texto))
    await interaction.response.send_message(out[:2000])

@bot.tree.command(name="reverse", description="Invierte un texto")
@app_commands.describe(texto="Texto a invertir")
async def cmd_reverse(interaction: discord.Interaction, texto: str):
    await interaction.response.send_message(texto[::-1][:2000])

@bot.tree.command(name="choose", description="Elige aleatoriamente entre varias opciones")
@app_commands.describe(opciones="Opciones separadas por ; (ej: pizza;sushi;tacos)")
async def cmd_choose(interaction: discord.Interaction, opciones: str):
    items = [o.strip() for o in opciones.split(";") if o.strip()]
    if len(items) < 2:
        return await interaction.response.send_message(f"{E_WARN} Dame al menos 2 opciones separadas por `;`.", ephemeral=True)
    pick = random.choice(items)
    e = discord.Embed(description=f"{E_ARROW} Elijo: **{pick}**", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="rate", description="Le pone puntaje a lo que quieras, del 1 al 10")
@app_commands.describe(cosa="Qué quieres que califique")
async def cmd_rate(interaction: discord.Interaction, cosa: str):
    score = (sum(ord(c) for c in cosa.lower()) % 10) + 1
    e = discord.Embed(description=f"Le doy a **{cosa}** un **{score}/10** {'🔥' if score >= 8 else '👍' if score >=5 else '😬'}",
                      color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


# ── UTILIDAD AVANZADA (calculadora segura, hash, base64) ─────────────

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}

def _safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)): return node.value
        raise ValueError("valor no numérico")
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("expresión no permitida")

@bot.tree.command(name="calc", description="Calculadora (+ - * / % ** paréntesis)")
@app_commands.describe(expresion="Ej: (5 + 3) * 2 / 4")
async def cmd_calc(interaction: discord.Interaction, expresion: str):
    try:
        tree = ast.parse(expresion, mode="eval")
        result = _safe_eval(tree.body)
        e = discord.Embed(description=f"`{expresion}` = **{result:g}**" if isinstance(result, float)
                          else f"`{expresion}` = **{result}**", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except ZeroDivisionError:
        await interaction.response.send_message(f"{E_WARN} No se puede dividir entre 0.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(
            f"{E_WARN} Expresión inválida. Solo se permiten números y `+ - * / % ** ()`.", ephemeral=True)


@bot.tree.command(name="base64", description="Codifica o decodifica texto en Base64")
@app_commands.describe(accion="encode o decode", texto="Texto a procesar")
@app_commands.choices(accion=[
    app_commands.Choice(name="Codificar (encode)", value="encode"),
    app_commands.Choice(name="Decodificar (decode)", value="decode")])
async def cmd_base64(interaction: discord.Interaction, accion: app_commands.Choice[str], texto: str):
    try:
        if accion.value == "encode":
            result = base64.b64encode(texto.encode()).decode()
        else:
            result = base64.b64decode(texto.encode()).decode()
    except Exception:
        return await interaction.response.send_message(f"{E_WARN} No pude procesar ese texto.", ephemeral=True)
    e = discord.Embed(description=f"```{result[:1500]}```", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="hash", description="Genera el hash de un texto")
@app_commands.describe(texto="Texto a hashear", algoritmo="Algoritmo a usar")
@app_commands.choices(algoritmo=[
    app_commands.Choice(name="MD5", value="md5"),
    app_commands.Choice(name="SHA1", value="sha1"),
    app_commands.Choice(name="SHA256", value="sha256")])
async def cmd_hash(interaction: discord.Interaction, texto: str, algoritmo: app_commands.Choice[str]):
    h = hashlib.new(algoritmo.value, texto.encode()).hexdigest()
    e = discord.Embed(description=f"```{h}```", color=C_RED)
    e.set_footer(text=f"{algoritmo.name} • {_footer()}")
    await interaction.response.send_message(embed=e)


# ── RECORDATORIOS PERSISTENTES ───────────────────────────────────────

REMINDERS_FILE = "reminders.json"
# reminders: { "id": {"user_id":.., "channel_id":.., "guild_id":.., "text":.., "due_ts":.., "done": bool} }
reminders: dict = load_json(REMINDERS_FILE, {})
def _save_reminders(): save_json(REMINDERS_FILE, reminders)

async def _reminder_watcher():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        for rid, r in list(reminders.items()):
            if r.get("done"): continue
            if r["due_ts"] <= now:
                r["done"] = True
                _save_reminders()
                channel = bot.get_channel(r["channel_id"])
                e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
                e.set_author(name=f"{BOT_NAME} — ⏰ Recordatorio", icon_url=URL_CROWN)
                e.description = r["text"]
                e.set_footer(text=_footer())
                try:
                    if channel:
                        await channel.send(content=f"<@{r['user_id']}>", embed=e)
                    else:
                        raise ValueError("sin canal")
                except Exception:
                    try:
                        user = await bot.fetch_user(r["user_id"])
                        await user.send(embed=e)
                    except Exception: pass
        await asyncio.sleep(20)

@bot.tree.command(name="remindlist", description="Ver tus recordatorios activos")
async def cmd_remindlist(interaction: discord.Interaction):
    mine = [r for r in reminders.values()
            if r["user_id"] == interaction.user.id and not r.get("done")]
    if not mine:
        return await interaction.response.send_message(f"{E_WARN} No tienes recordatorios activos.", ephemeral=True)
    lines = [f"• {r['text'][:60]} — <t:{int(r['due_ts'])}:R>" for r in mine[:15]]
    e = discord.Embed(description="\n".join(lines), color=C_RED)
    e.set_author(name=f"{BOT_NAME} — ⏰ Tus recordatorios", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="help", description="Ver todos los comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Comandos", icon_url=URL_CROWN)
    e.set_thumbnail(url=URL_CROWN)
    e.description = (f"También puedes usar comandos rápidos escribiendo `{BOT_TRIGGER}` o "
                     f"`{BOT_NAME}` antes del comando, ej: `{BOT_TRIGGER} ping`, `{BOT_TRIGGER} afk`.")
    e.add_field(
        name=f"{E_RDIAM} Bypass",
        value="`/bypass` `/setautobypass` *(Admin)*",
        inline=True)
    e.add_field(
        name=f"{E_CROWN} Fun",
        value="`/8ball` `/joke` `/coinflip` `/roll` `/roast` `/rps` `/say`",
        inline=True)
    e.add_field(
        name=f"{E_TICKET} Tickets",
        value="`/ticket-setup` `/ticket-panel` `/ticket-close` *(Admin)*",
        inline=True)
    e.add_field(
        name="🎉 Giveaways",
        value="`/giveaway-start` `/giveaway-end` `/giveaway-reroll` *(Manage Server)*",
        inline=True)
    e.add_field(
        name="🛡️ Moderación",
        value="`/kick` `/ban` `/unban` `/timeout` `/untimeout` `/warn` `/warnings` `/clear-warnings` `/clear`",
        inline=True)
    e.add_field(
        name="🤖 AutoMod y Logs",
        value="`/automod-toggle` `/automod-addword` `/automod-removeword` `/automod-words` "
              "`/setmodlog` `/snipe` `/editsnipe` *(Admin)*",
        inline=True)
    e.add_field(
        name="👋 Bienvenidas y Roles",
        value="`/welcome-setup` `/leave-setup` `/addrole` `/removerole` `/autorole-set` "
              "`/autorole-off` `/rolemenu-create`",
        inline=True)
    e.add_field(
        name="⭐ Niveles",
        value="`/rank` `/leaderboard` `/setlevel` *(Admin)*",
        inline=True)
    e.add_field(
        name=f"{CURRENCY} Economía",
        value="`/balance` `/daily` `/work` `/pay` `/eco-leaderboard` `/add-money` *(Admin)*",
        inline=True)
    e.add_field(
        name="🖼️ Imágenes",
        value="`/pfp-circle` `/pfp-invert` `/pfp-grayscale` `/pfp-blur` `/pfp-pixelate` "
              "`/jail` `/wanted` `/meme` `/qr` `/color`",
        inline=True)
    e.add_field(
        name="🧩 Extras",
        value="`/poll` `/remind` `/remindlist` `/afk` `/suggest` `/suggest-setup` *(Admin)*",
        inline=True)
    e.add_field(
        name="⚙️ Gestión de servidor",
        value="`/lock` `/unlock` `/slowmode` `/nickname` `/nuke` `/channelinfo` `/roleinfo` "
              "`/emojilist` `/banner` `/report` `/audit-log`",
        inline=True)
    e.add_field(
        name="🌟 Starboard",
        value="`/starboard-setup` `/starboard-off` *(Admin)*",
        inline=True)
    e.add_field(
        name="🎮 Minijuegos",
        value="`/trivia` `/ship` `/mock` `/reverse` `/choose` `/rate`",
        inline=True)
    e.add_field(
        name="🔧 Utilidad avanzada",
        value="`/calc` `/base64` `/hash`",
        inline=True)
    e.add_field(
        name=f"{E_ARROW} Utilidad",
        value="`/ping` `/avatar` `/userinfo` `/serverinfo` `/membercount` `/botinfo` `/invite` "
              "`/firstmessage` `/define` `/shorten` `/weather` `/translate` `/help`",
        inline=True)
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"SYSTEM MADE WITH 🔥  |  {_footer()}")
    v = View()
    v.add_item(Button(label="SUPPORT SERVER", emoji="💬", url=SUPPORT_SERVER_URL,
                      style=discord.ButtonStyle.link))
    v.add_item(Button(label="INVITE ME",      emoji="🤖", url=BOT_INVITE_URL,
                      style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=e, view=v)

# ── COMANDOS POR PREFIJO (nombre del bot) ────────────────────────────
# Estos responden cuando escribes el nombre/trigger del bot antes del
# comando, ej:  "king ping"   "KING BOT afk estudiando"   "king 8ball ...?"
# Sirven como atajo rápido para los comandos más usados; para las opciones
# avanzadas (con varios parámetros, como /ticket-setup o /giveaway-start)
# usa siempre el comando slash correspondiente.

@bot.command(name="ping")
async def prefix_ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    e = discord.Embed(description=f"{E_CHECK} Pong! `{latency}ms`", color=C_RED)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="afk")
async def prefix_afk(ctx: commands.Context, *, mensaje: str = "AFK"):
    _afk_users[ctx.author.id] = mensaje
    e = discord.Embed(description=f"{E_CHECK} Te marqué como AFK: {mensaje}", color=C_RED)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="avatar")
async def prefix_avatar(ctx: commands.Context, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Avatar de {usuario.display_name}", icon_url=URL_CROWN)
    e.set_image(url=usuario.display_avatar.url)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="userinfo")
async def prefix_userinfo(ctx: commands.Context, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    roles = [r.mention for r in usuario.roles if r.name != "@everyone"]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_USER} Info de usuario", icon_url=URL_CROWN)
    e.set_thumbnail(url=usuario.display_avatar.url)
    e.add_field(name=f"{E_RDIAM} Usuario", value=f"{usuario.mention}\n`{usuario}`", inline=True)
    e.add_field(name=f"{E_INFO} ID", value=f"`{usuario.id}`", inline=True)
    e.add_field(name=f"{E_CHECK} Roles ({len(roles)})", value=(", ".join(roles[:15]) or "Ninguno"), inline=False)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="serverinfo")
async def prefix_serverinfo(ctx: commands.Context):
    g = ctx.guild
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {E_INFO} Info del servidor", icon_url=URL_CROWN)
    if g.icon: e.set_thumbnail(url=g.icon.url)
    e.add_field(name=f"{E_RDIAM} Nombre", value=g.name, inline=True)
    e.add_field(name=f"{E_USER} Miembros", value=f"`{g.member_count}`", inline=True)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="balance")
async def prefix_balance(ctx: commands.Context, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    w = _get_wallet(ctx.guild.id, usuario.id)
    e = discord.Embed(description=f"{CURRENCY} **{usuario.display_name}** tiene `{w['balance']}` monedas.",
                      color=C_RED)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="rank")
async def prefix_rank(ctx: commands.Context, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    try:
        file = await _build_rank_card(usuario)
        await ctx.send(file=file)
    except Exception:
        await ctx.send(f"{E_WARN} No pude generar la tarjeta de nivel.")

@bot.command(name="8ball")
async def prefix_8ball(ctx: commands.Context, *, pregunta: str = None):
    if not pregunta:
        return await ctx.send(f"{E_WARN} Escribe una pregunta. Ej: `{BOT_TRIGGER} 8ball ¿ganaré hoy?`")
    resp = random.choice(_8BALL)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎱 Magic 8-Ball", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Pregunta", value=f"```{pregunta[:300]}```", inline=False)
    e.add_field(name=f"{E_ARROW} Respuesta", value=f"```{resp}```", inline=False)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="coinflip")
async def prefix_coinflip(ctx: commands.Context):
    result = random.choice(["CARA", "CRUZ"])
    e = discord.Embed(description=f"🪙 Salió: **{result}**", color=C_RED)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="roll")
async def prefix_roll(ctx: commands.Context, caras: int = 6):
    caras = max(2, min(caras, 1000))
    e = discord.Embed(description=f"🎲 Salió: **{random.randint(1, caras)}** (d{caras})", color=C_RED)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.command(name="help")
async def prefix_help(ctx: commands.Context):
    e = discord.Embed(
        description=(f"Usa `/help` para ver la lista completa de {len(bot.tree.get_commands())}+ comandos.\n\n"
                     f"Comandos rápidos por texto: `{BOT_TRIGGER} ping`, `{BOT_TRIGGER} afk [motivo]`, "
                     f"`{BOT_TRIGGER} avatar [@user]`, `{BOT_TRIGGER} userinfo [@user]`, "
                     f"`{BOT_TRIGGER} serverinfo`, `{BOT_TRIGGER} balance [@user]`, `{BOT_TRIGGER} rank [@user]`, "
                     f"`{BOT_TRIGGER} 8ball <pregunta>`, `{BOT_TRIGGER} coinflip`, `{BOT_TRIGGER} roll [caras]`."),
        color=C_RED)
    e.set_author(name=f"{BOT_NAME} — Ayuda rápida", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    await ctx.send(embed=e)

@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, (commands.CommandNotFound, commands.MissingRequiredArgument)):
        return
    logger.warning(f"prefix command error: {error}")


# ── HEALTH SERVER ─────────────────────────────────────────────────

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
    logger.info(f"🌐 Health server :{PORT}")

# ── MAIN ──────────────────────────────────────────────────────────

async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado.")
        return
    start_web()
    logger.info(f"🚀 Iniciando {BOT_NAME}...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
