"""
KING BOT — Bypass + Fun Commands
"""
import sys, types

try:
    import audioop
except ImportError:
    sys.modules["audioop"] = types.ModuleType("audioop")

import os, re, json, time, asyncio, logging, threading, random
from datetime import datetime, timezone, timedelta
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

BOT_NAME   = "FMD BOT"
BOT_CREDIT = "BY KING"

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
IMG_MAIN = "https://cdn.discordapp.com/attachments/1525556800579965058/1525566942281465876/ezgif-35ed139046075f14_1.gif?ex=6a54832e&is=6a5331ae&hm=a4db669a357a86146d47dabf764d2f5c33d1e764a23744408a074c58c4576633&"

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
        value=f"`\n{result[:900]}\n`",
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
        value=f"`\n{url[:200]}\n`",
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
            url=https://discord.gg/ZMXmwUjTBf,
            style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(
            label="INVITE ME", emoji="🤖",
            url=https://discord.com/oauth2/authorize?client_id=1525629900038475969,
            style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="📋  Copiar resultado",
                       style=discord.ButtonStyle.danger, row=1)
    async def copy_btn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            content=f"`\n{self._r[:1800]}\n`", ephemeral=True)

class FailView(View):
    def __init__(self, elapsed: float):
        super().__init__(timeout=None)
        self.add_item(Button(
            label=f"⏰  {elapsed:.2f}s",
            style=discord.ButtonStyle.secondary,
            disabled=True, row=0))
        self.add_item(Button(
            label="SUPPORT SERVER", emoji="💬",
            url=https://discord.gg/ZMXmwUjTBf
            style=discord.ButtonStyle.link, row=0))

# ── BOT ──────────────────────────────────────────────────────────

class KingBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(TicketCloseView())
        self.add_view(GiveawayView())
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online como {self.user} | {len(self.guilds)} servidor(es)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"/help • {BOT_NAME}"))
        if not getattr(self, "_giveaway_task_started", False):
            self._giveaway_task_started = True
            asyncio.create_task(_giveaway_watcher())

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
    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"{E_CHECK} Te recordaré esto en **{duracion}**: {mensaje}",
            color=C_RED), ephemeral=True)

    async def _later():
        await asyncio.sleep(secs)
        e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
        e.set_author(name=f"{BOT_NAME} — ⏰ Recordatorio", icon_url=URL_CROWN)
        e.description = mensaje
        e.set_footer(text=_footer())
        try:
            await interaction.followup.send(content=interaction.user.mention, embed=e)
        except Exception:
            try: await interaction.user.send(embed=e)
            except Exception: pass

    asyncio.create_task(_later())
    # Nota: los recordatorios viven en memoria; si el bot se reinicia antes de
    # que se cumpla el tiempo, ese recordatorio en particular se pierde.


_afk_users: dict = {}   # user_id -> mensaje afk

@bot.tree.command(name="afk", description="Marca que estás AFK (ausente)")
@app_commands.describe(mensaje="Motivo (opcional)")
async def cmd_afk(interaction: discord.Interaction, mensaje: str = "AFK"):
    _afk_users[interaction.user.id] = mensaje
    e = discord.Embed(description=f"{E_CHECK} Te marqué como AFK: {mensaje}", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


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


@bot.tree.command(name="help", description="Ver todos los comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Comandos", icon_url=URL_CROWN)
    e.set_thumbnail(url=URL_CROWN)
    e.add_field(
        name=f"{E_RDIAM} Bypass",
        value=(f"`/bypass` — Bypassea un enlace\n"
               f"`/setautobypass` — Auto-bypass en canal *(Admin)*"),
        inline=False)
    e.add_field(
        name=f"{E_CROWN} Fun",
        value=(f"`/8ball` — Bola mágica\n"
               f"`/joke` — Chiste aleatorio\n"
               f"`/coinflip` — Cara o cruz\n"
               f"`/roll [lados]` — Lanzar dado\n"
               f"`/roast <user>` — Incinerar a alguien\n"
               f"`/rps` — Piedra papel tijeras\n"
               f"`/say <msg>` — Bot dice algo *(Manage Msgs)*"),
        inline=False)
    e.add_field(
        name=f"{E_TICKET} Tickets",
        value=(f"`/ticket-setup` — Configura categoría/rol/logs *(Admin)*\n"
               f"`/ticket-panel` — Publica el panel de apertura *(Admin)*\n"
               f"`/ticket-close` — Cierra el ticket actual"),
        inline=False)
    e.add_field(
        name="🎉 Giveaways",
        value=(f"`/giveaway-start` — Inicia un giveaway *(Manage Server)*\n"
               f"`/giveaway-end` — Termínalo ahora *(Manage Server)*\n"
               f"`/giveaway-reroll` — Sortea de nuevo *(Manage Server)*"),
        inline=False)
    e.add_field(
        name="🛡️ Moderación",
        value=(f"`/kick` `/ban` `/unban` — Gestión de miembros\n"
               f"`/timeout` `/untimeout` — Silenciar temporalmente\n"
               f"`/warn` `/warnings` `/clear-warnings` — Advertencias\n"
               f"`/clear <cantidad>` — Borrar mensajes"),
        inline=False)
    e.add_field(
        name="🧩 Extras",
        value=(f"`/poll` — Encuesta rápida (hasta 4 opciones)\n"
               f"`/remind` — Recordatorio personal\n"
               f"`/afk [mensaje]` — Marcarte como AFK"),
        inline=False)
    e.add_field(
        name=f"{E_ARROW} Utilidad",
        value=(f"`/ping` — Latencia\n"
               f"`/avatar [user]` — Ver avatar\n"
               f"`/userinfo [user]` — Info de usuario\n"
               f"`/serverinfo` — Info del servidor\n"
               f"`/help` — Esta lista"),
        inline=False)
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"SYSTEM MADE WITH 🔥  |  {_footer()}")
    v = View()
    v.add_item(Button(label="SUPPORT SERVER", emoji="💬", url=SUPPORT_SERVER_URL,
                      style=discord.ButtonStyle.link))
    v.add_item(Button(label="INVITE ME",      emoji="🤖", url=BOT_INVITE_URL,
                      style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=e, view=v)

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
