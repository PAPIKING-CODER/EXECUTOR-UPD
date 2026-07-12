"""
FMD BOT — Bypass + Fun Commands
"""
import os, re, json, time, asyncio, logging, threading, random
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
import requests
import aiohttp

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

# ── LOGGING ──────────────────────────────────────────────────────
logger = logging.getLogger("FMD")
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
BOT_CREDIT = "Made with 💪"

BYPASS_API_URL = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT = 30
BYPASS_RETRIES = 3
BYPASS_DELAY   = 3

AUTOBYPASS_FILE = "autobypass_channels.json"

# ── TICKETS ──────────────────────────────────────────────────────
TICKET_CONFIG_FILE = "ticket_config.json"
TICKET_COUNTER_FILE = "ticket_counter.json"

# ── ECONOMÍA ─────────────────────────────────────────────────────
ECONOMY_FILE = "economy.json"

# ── COLORES ──────────────────────────────────────────────────────
C_RED   = 0xC80000   # rojo oscuro principal
C_DARK  = 0x1A0000   # casi negro con tono rojo
C_WARN  = 0xFF4500   # rojo-naranja para loading
C_INFO  = 0x8B0000   # rojo profundo

# ── IMAGEN PRINCIPAL ─────────────────────────────────────────────
IMG_MAIN = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a5485bb&is=6a53343b&hm=f6df69c459c7bad9ed031d12eee35f42ab4adbb7290fe08a3707046eb3bf7200&"

# ── EMOJIS ───────────────────────────────────────────────────────
E_CHECK   = "✅"
E_REDPT   = "🔴"
E_WARN    = "⚠️"
E_RDIAM   = "💎"
E_ARROW   = "➡️"
E_CROWN   = "👑"
E_NO      = "❌"
E_LOAD    = "⏳"
E_USER    = "👤"
E_TICKET  = "🎫"
E_LOCK    = "🔒"
E_INFO    = "📌"

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

ticket_config: dict = load_json(TICKET_CONFIG_FILE, {})
def _save_tc(): save_json(TICKET_CONFIG_FILE, ticket_config)

ticket_counter: dict = load_json(TICKET_COUNTER_FILE, {})
def _save_tcounter(): save_json(TICKET_COUNTER_FILE, ticket_counter)

economy: dict = load_json(ECONOMY_FILE, {})
def _save_eco(): save_json(ECONOMY_FILE, economy)

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
    return "Made with 💪"

def _get_balance(user_id: int) -> int:
    return economy.get(str(user_id), 0)

def _set_balance(user_id: int, amount: int):
    economy[str(user_id)] = max(0, amount)
    _save_eco()

def _add_balance(user_id: int, amount: int) -> int:
    new = _get_balance(user_id) + amount
    if new < 0: new = 0
    economy[str(user_id)] = new
    _save_eco()
    return new

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

# ── BYPASS EMBEDS ────────────────────────────────────────────────

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
    e.set_footer(text=_footer())
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
    e.set_footer(text=_footer())
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

class KingBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
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

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

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


# ── NUEVOS COMANDOS DE DIVERSIÓN ───────────────────────────────────

@bot.tree.command(name="rate", description="Califica algo del 1 al 10")
@app_commands.describe(cosa="Lo que quieras calificar")
async def cmd_rate(interaction: discord.Interaction, cosa: str):
    rating = random.randint(1, 10)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 📊 Rate", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Cosa", value=cosa[:200], inline=False)
    e.add_field(name=f"{E_ARROW} Puntuación", value=f"```{rating}/10```", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="choose", description="Elige una opción entre varias")
@app_commands.describe(opciones="Opciones separadas por coma (ej: pizza, pasta, sushi)")
async def cmd_choose(interaction: discord.Interaction, opciones: str):
    items = [x.strip() for x in opciones.split(",") if x.strip()]
    if len(items) < 2:
        return await interaction.response.send_message(f"{E_WARN} Necesitas al menos 2 opciones.", ephemeral=True)
    elegida = random.choice(items)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎯 Choose", icon_url=URL_CROWN)
    e.add_field(name=f"{E_RDIAM} Opciones", value=", ".join(items), inline=False)
    e.add_field(name=f"{E_ARROW} Elijo", value=f"```{elegida}```", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="math", description="Realiza una operación matemática simple")
@app_commands.describe(expresion="Ej: 2+2, 10*5, 100/4")
async def cmd_math(interaction: discord.Interaction, expresion: str):
    if not re.match(r'^[\d+\-*/() ]+$', expresion):
        return await interaction.response.send_message(f"{E_WARN} Expresión inválida. Usa solo números y + - * / ( ).", ephemeral=True)
    try:
        result = eval(expresion)
        e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
        e.set_author(name=f"{BOT_NAME} — 🧮 Math", icon_url=URL_CROWN)
        e.add_field(name=f"{E_RDIAM} Operación", value=f"```{expresion}```", inline=False)
        e.add_field(name=f"{E_ARROW} Resultado", value=f"```{result}```", inline=False)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except Exception:
        await interaction.response.send_message(f"{E_WARN} Error en la operación.", ephemeral=True)

@bot.tree.command(name="slot", description="Máquina tragaperras 🎰")
async def cmd_slot(interaction: discord.Interaction):
    emojis = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
    result = [random.choice(emojis) for _ in range(3)]
    win = result[0] == result[1] == result[2]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎰 Slot", icon_url=URL_CROWN)
    e.description = f"```{result[0]} {result[1]} {result[2]}```\n{'🎉 **¡GANASTE!**' if win else '😢 Perdiste...'}"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="truth", description="Verdad o reto - Verdad")
async def cmd_truth(interaction: discord.Interaction):
    truths = [
        "¿Cuál es tu mayor miedo?",
        "¿Has mentido alguna vez en una entrevista?",
        "¿Cuál es tu secreto más vergonzoso?",
        "¿Qué es lo que más te arrepientes de no haber hecho?",
        "¿A quién admiras en secreto?",
        "¿Cuál fue tu peor cita?",
        "¿Alguna vez has robado algo?",
        "¿Cuál es tu mayor inseguridad?",
    ]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🤔 Verdad", icon_url=URL_CROWN)
    e.description = f"**{random.choice(truths)}**"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="dare", description="Verdad o reto - Reto")
async def cmd_dare(interaction: discord.Interaction):
    dares = [
        "Haz 10 flexiones ahora mismo.",
        "Canta una canción en el chat de voz.",
        "Envía un mensaje de texto a tu ex.",
        "Come algo picante sin beber agua.",
        "Haz una imitación de un famoso.",
        "Baila durante 1 minuto.",
        "Habla en acento extranjero por 5 minutos.",
        "Toma una foto de tu refrigerador y publícala.",
    ]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 😈 Reto", icon_url=URL_CROWN)
    e.description = f"**{random.choice(dares)}**"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── COMANDOS DE INTERACCIÓN (con Nekos.life) ──────────────────────

_INTERACTIONS = {
    "hug": "🤗 abrazó a",
    "kiss": "😘 besó a",
    "slap": "✋ abofeteó a",
    "pat": "🤚 acarició a",
    "punch": "👊 golpeó a",
    "highfive": "🙏 chocó los cinco con"
}

_NEKOS_ENDPOINTS = {
    "hug": "hug",
    "kiss": "kiss",
    "slap": "slap",
    "pat": "pat",
    "punch": "punch",
    "highfive": "highfive"
}

async def _get_neko_gif(action: str) -> str:
    """Obtiene un GIF de Nekos.life para la acción dada."""
    endpoint = _NEKOS_ENDPOINTS.get(action)
    if not endpoint:
        return None
    url = f"https://nekos.life/api/v2/img/{endpoint}"
    try:
        async with bot.session.get(url, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("url")
    except Exception as e:
        logger.warning(f"Nekos.life error: {e}")
    return None

@bot.tree.command(name="hug", description="Abraza a alguien")
@app_commands.describe(usuario="Usuario")
async def cmd_hug(interaction: discord.Interaction, usuario: discord.Member):
    await _interaction_cmd(interaction, usuario, "hug")

@bot.tree.command(name="kiss", description="Besa a alguien")
@app_commands.describe(usuario="Usuario")
async def cmd_kiss(interaction: discord.Interaction, usuario: discord.Member):
    await _interaction_cmd(interaction, usuario, "kiss")

@bot.tree.command(name="slap", description="Abofetea a alguien")
@app_commands.describe(usuario="Usuario")
async def cmd_slap(interaction: discord.Interaction, usuario: discord.Member):
    await _interaction_cmd(interaction, usuario, "slap")

@bot.tree.command(name="pat", description="Acaricia a alguien")
@app_commands.describe(usuario="Usuario")
async def cmd_pat(interaction: discord.Interaction, usuario: discord.Member):
    await _interaction_cmd(interaction, usuario, "pat")

@bot.tree.command(name="punch", description="Golpea a alguien")
@app_commands.describe(usuario="Usuario")
async def cmd_punch(interaction: discord.Interaction, usuario: discord.Member):
    await _interaction_cmd(interaction, usuario, "punch")

@bot.tree.command(name="highfive", description="Choca los cinco con alguien")
@app_commands.describe(usuario="Usuario")
async def cmd_highfive(interaction: discord.Interaction, usuario: discord.Member):
    await _interaction_cmd(interaction, usuario, "highfive")

async def _interaction_cmd(interaction: discord.Interaction, usuario: discord.Member, action: str):
    if usuario == interaction.user:
        return await interaction.response.send_message(f"{E_WARN} No puedes {action} a ti mismo.", ephemeral=True)
    
    # Obtener GIF de Nekos.life
    gif_url = await _get_neko_gif(action)
    
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — {action.capitalize()}", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} {_INTERACTIONS[action]} {usuario.mention} 🥰"
    if gif_url:
        e.set_image(url=gif_url)
    else:
        e.add_field(name="", value="*(No se pudo cargar el GIF, pero el sentimiento cuenta)*", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ship", description="Calcula compatibilidad entre dos usuarios")
@app_commands.describe(usuario1="Primer usuario", usuario2="Segundo usuario (opcional)")
async def cmd_ship(interaction: discord.Interaction, usuario1: discord.Member, usuario2: discord.Member = None):
    if usuario2 is None:
        usuario2 = interaction.user
    if usuario1 == usuario2:
        return await interaction.response.send_message(f"{E_WARN} No puedo shippear a alguien consigo mismo.", ephemeral=True)
    porcentaje = random.randint(1, 100)
    emoji = "❤️" if porcentaje > 70 else "💔" if porcentaje < 40 else "💛"
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 💕 Ship", icon_url=URL_CROWN)
    e.description = f"{usuario1.mention} + {usuario2.mention}\n\n**Compatibilidad: {porcentaje}%** {emoji}"
    if porcentaje > 80:
        e.description += "\n¡Almas gemelas! 👩‍❤️‍👨"
    elif porcentaje < 30:
        e.description += "\nMejor no... 😅"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── COMANDOS DE ECONOMÍA ─────────────────────────────────────────

@bot.tree.command(name="balance", description="Muestra tu saldo de monedas")
async def cmd_balance(interaction: discord.Interaction):
    saldo = _get_balance(interaction.user.id)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 💰 Balance", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} tienes **{saldo}** monedas."
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="daily", description="Reclama tus monedas diarias")
async def cmd_daily(interaction: discord.Interaction):
    amount = random.randint(50, 150)
    new_bal = _add_balance(interaction.user.id, amount)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 📅 Daily", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} has recibido **{amount}** monedas. Ahora tienes **{new_bal}**."
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="work", description="Trabaja para ganar monedas")
async def cmd_work(interaction: discord.Interaction):
    amount = random.randint(10, 40)
    new_bal = _add_balance(interaction.user.id, amount)
    trabajos = ["programador", "cocinero", "músico", "escritor", "diseñador", "constructor"]
    trabajo = random.choice(trabajos)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 💼 Work", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} trabajó como **{trabajo}** y ganó **{amount}** monedas. Saldo: **{new_bal}**."
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="beg", description="Pide monedas a la suerte")
async def cmd_beg(interaction: discord.Interaction):
    if random.random() < 0.3:
        amount = random.randint(1, 10)
        new_bal = _add_balance(interaction.user.id, amount)
        msg = f"Te dieron {amount} monedas. Saldo: {new_bal}."
    else:
        msg = "Nadie te dio nada 😢"
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🥺 Beg", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} {msg}"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="gamble", description="Apuesta monedas (50% de ganar)")
@app_commands.describe(cantidad="Cantidad a apostar")
async def cmd_gamble(interaction: discord.Interaction, cantidad: int):
    saldo = _get_balance(interaction.user.id)
    if cantidad <= 0:
        return await interaction.response.send_message(f"{E_WARN} La cantidad debe ser positiva.", ephemeral=True)
    if cantidad > saldo:
        return await interaction.response.send_message(f"{E_WARN} No tienes suficientes monedas. Saldo: {saldo}", ephemeral=True)
    win = random.choice([True, False])
    if win:
        ganancia = cantidad
        new_bal = _add_balance(interaction.user.id, ganancia)
        msg = f"¡Ganaste {ganancia} monedas! 🎉 Saldo: {new_bal}"
    else:
        _add_balance(interaction.user.id, -cantidad)
        new_bal = _get_balance(interaction.user.id)
        msg = f"Perdiste {cantidad} monedas. 😢 Saldo: {new_bal}"
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎲 Gamble", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} {msg}"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="transfer", description="Transfiere monedas a otro usuario")
@app_commands.describe(usuario="Usuario destino", cantidad="Cantidad")
async def cmd_transfer(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if usuario == interaction.user:
        return await interaction.response.send_message(f"{E_WARN} No puedes transferirte a ti mismo.", ephemeral=True)
    if cantidad <= 0:
        return await interaction.response.send_message(f"{E_WARN} Cantidad inválida.", ephemeral=True)
    saldo = _get_balance(interaction.user.id)
    if cantidad > saldo:
        return await interaction.response.send_message(f"{E_WARN} No tienes suficientes monedas. Saldo: {saldo}", ephemeral=True)
    _add_balance(interaction.user.id, -cantidad)
    _add_balance(usuario.id, cantidad)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 💸 Transfer", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention} transfirió **{cantidad}** monedas a {usuario.mention}."
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="inventory", description="Muestra tu inventario (por ahora solo monedas)")
async def cmd_inventory(interaction: discord.Interaction):
    saldo = _get_balance(interaction.user.id)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🎒 Inventory", icon_url=URL_CROWN)
    e.description = f"{interaction.user.mention}\n🪙 Monedas: **{saldo}**\n(Próximamente más objetos)"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="leaderboard", description="Top 10 de los más ricos")
async def cmd_leaderboard(interaction: discord.Interaction):
    top = sorted(economy.items(), key=lambda x: x[1], reverse=True)[:10]
    if not top:
        return await interaction.response.send_message("No hay datos de economía aún.")
    desc = ""
    for idx, (uid, bal) in enumerate(top, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"Usuario {uid}"
        desc += f"{idx}. **{name}** — {bal} monedas\n"
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🏆 Leaderboard", icon_url=URL_CROWN)
    e.description = desc
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── COMANDOS DE UTILIDAD ADICIONALES ─────────────────────────────

@bot.tree.command(name="invite", description="Crea una invitación al canal actual")
@app_commands.checks.has_permissions(create_instant_invite=True)
async def cmd_invite(interaction: discord.Interaction):
    try:
        link = await interaction.channel.create_invite(max_age=3600, max_uses=10)
    except Exception as e:
        return await interaction.response.send_message(f"{E_WARN} No pude crear invitación: {e}", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🔗 Invite", icon_url=URL_CROWN)
    e.description = f"Invita a otros: {link}"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)
@cmd_invite.error
async def _invite_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas permiso para crear invitaciones.", ephemeral=True)

@bot.tree.command(name="roleinfo", description="Muestra información de un rol")
@app_commands.describe(rol="Rol")
async def cmd_roleinfo(interaction: discord.Interaction, rol: discord.Role):
    e = discord.Embed(color=rol.color, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — ℹ️ Role Info", icon_url=URL_CROWN)
    e.add_field(name="Nombre", value=rol.name, inline=True)
    e.add_field(name="ID", value=rol.id, inline=True)
    e.add_field(name="Color", value=str(rol.color), inline=True)
    e.add_field(name="Mencionable", value="Sí" if rol.mentionable else "No", inline=True)
    e.add_field(name="Miembros", value=len(rol.members), inline=True)
    e.add_field(name="Posición", value=rol.position, inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="channelinfo", description="Muestra información del canal actual")
async def cmd_channelinfo(interaction: discord.Interaction):
    ch = interaction.channel
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — ℹ️ Channel Info", icon_url=URL_CROWN)
    e.add_field(name="Nombre", value=ch.name, inline=True)
    e.add_field(name="ID", value=ch.id, inline=True)
    e.add_field(name="Tipo", value=str(ch.type), inline=True)
    if isinstance(ch, discord.TextChannel):
        e.add_field(name="Tema", value=ch.topic or "Ninguno", inline=False)
        e.add_field(name="Posición", value=ch.position, inline=True)
        e.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="botinfo", description="Muestra información del bot")
async def cmd_botinfo(interaction: discord.Interaction):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🤖 Bot Info", icon_url=URL_CROWN)
    e.add_field(name="Nombre", value=BOT_NAME, inline=True)
    e.add_field(name="Creador", value="BY KING", inline=True)
    e.add_field(name="Servidores", value=len(bot.guilds), inline=True)
    e.add_field(name="Usuarios", value=sum(g.member_count for g in bot.guilds), inline=True)
    e.add_field(name="Uptime", value=_uptime(), inline=True)
    e.add_field(name="Latencia", value=f"{round(bot.latency * 1000)}ms", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="servericon", description="Muestra el icono del servidor")
async def cmd_servericon(interaction: discord.Interaction):
    g = interaction.guild
    if not g.icon:
        return await interaction.response.send_message(f"{E_WARN} Este servidor no tiene icono.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🖼️ Server Icon", icon_url=URL_CROWN)
    e.set_image(url=g.icon.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverbanner", description="Muestra el banner del servidor")
async def cmd_serverbanner(interaction: discord.Interaction):
    g = interaction.guild
    if not g.banner:
        return await interaction.response.send_message(f"{E_WARN} Este servidor no tiene banner.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🖼️ Server Banner", icon_url=URL_CROWN)
    e.set_image(url=g.banner.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="emojiinfo", description="Muestra información de un emoji")
@app_commands.describe(emoji="Emoji (mención)")
async def cmd_emojiinfo(interaction: discord.Interaction, emoji: str):
    emoji_obj = None
    for e in interaction.guild.emojis:
        if str(e) == emoji or e.name == emoji:
            emoji_obj = e
            break
    if not emoji_obj:
        return await interaction.response.send_message(f"{E_WARN} No encontré ese emoji en el servidor.", ephemeral=True)
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — ℹ️ Emoji Info", icon_url=URL_CROWN)
    e.set_thumbnail(url=emoji_obj.url)
    e.add_field(name="Nombre", value=emoji_obj.name, inline=True)
    e.add_field(name="ID", value=emoji_obj.id, inline=True)
    e.add_field(name="Animado", value="Sí" if emoji_obj.animated else "No", inline=True)
    e.add_field(name="Creado", value=discord.utils.format_dt(emoji_obj.created_at, "R"), inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="banner", description="Muestra el banner de un usuario")
@app_commands.describe(usuario="Usuario (por defecto tú)")
async def cmd_banner(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    try:
        user = await bot.fetch_user(usuario.id)
        if not user.banner:
            return await interaction.response.send_message(f"{E_WARN} {usuario.display_name} no tiene banner.", ephemeral=True)
        e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
        e.set_author(name=f"{BOT_NAME} — 🖼️ Banner de {usuario.display_name}", icon_url=URL_CROWN)
        e.set_image(url=user.banner.url)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except:
        await interaction.response.send_message(f"{E_WARN} No pude obtener el banner.", ephemeral=True)

# ── COMANDOS DE MODERACIÓN ADICIONALES ───────────────────────────

@bot.tree.command(name="addrole", description="Asigna un rol a un usuario (Manage Roles)")
@app_commands.describe(usuario="Usuario", rol="Rol a asignar")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_addrole(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    if rol >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        return await interaction.response.send_message(f"{E_WARN} No puedes asignar un rol superior o igual al tuyo.", ephemeral=True)
    try:
        await usuario.add_roles(rol, reason=f"Agregado por {interaction.user}")
        e = discord.Embed(description=f"{E_CHECK} Se asignó {rol.mention} a {usuario.mention}.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await interaction.response.send_message(f"{E_WARN} No tengo permisos para asignar ese rol.", ephemeral=True)
@cmd_addrole.error
async def _addrole_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar roles**.", ephemeral=True)

@bot.tree.command(name="removerole", description="Remueve un rol a un usuario (Manage Roles)")
@app_commands.describe(usuario="Usuario", rol="Rol a remover")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_removerole(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    if rol >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        return await interaction.response.send_message(f"{E_WARN} No puedes remover un rol superior o igual al tuyo.", ephemeral=True)
    try:
        await usuario.remove_roles(rol, reason=f"Removido por {interaction.user}")
        e = discord.Embed(description=f"{E_CHECK} Se removió {rol.mention} de {usuario.mention}.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await interaction.response.send_message(f"{E_WARN} No tengo permisos para remover ese rol.", ephemeral=True)
@cmd_removerole.error
async def _removerole_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar roles**.", ephemeral=True)

@bot.tree.command(name="nick", description="Cambia el apodo de un usuario (Manage Nicknames)")
@app_commands.describe(usuario="Usuario", apodo="Nuevo apodo")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def cmd_nick(interaction: discord.Interaction, usuario: discord.Member, apodo: str = None):
    try:
        await usuario.edit(nick=apodo, reason=f"Cambiado por {interaction.user}")
        e = discord.Embed(description=f"{E_CHECK} Apodo de {usuario.mention} cambiado a `{apodo or 'ninguno'}`.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await interaction.response.send_message(f"{E_WARN} No tengo permisos para cambiar el apodo.", ephemeral=True)
@cmd_nick.error
async def _nick_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar apodos**.", ephemeral=True)

@bot.tree.command(name="lock", description="Bloquea el canal (Manage Channels)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_lock(interaction: discord.Interaction):
    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        e = discord.Embed(description=f"{E_LOCK} Canal bloqueado.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except:
        await interaction.response.send_message(f"{E_WARN} No pude bloquear el canal.", ephemeral=True)
@cmd_lock.error
async def _lock_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar canales**.", ephemeral=True)

@bot.tree.command(name="unlock", description="Desbloquea el canal (Manage Channels)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_unlock(interaction: discord.Interaction):
    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
        e = discord.Embed(description=f"{E_CHECK} Canal desbloqueado.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except:
        await interaction.response.send_message(f"{E_WARN} No pude desbloquear el canal.", ephemeral=True)
@cmd_unlock.error
async def _unlock_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar canales**.", ephemeral=True)

@bot.tree.command(name="slowmode", description="Establece slowmode en el canal (Manage Channels)")
@app_commands.describe(segundos="Segundos entre mensajes (0 para desactivar)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_slowmode(interaction: discord.Interaction, segundos: int):
    if segundos < 0 or segundos > 21600:
        return await interaction.response.send_message(f"{E_WARN} El slowmode debe estar entre 0 y 21600 segundos.", ephemeral=True)
    try:
        await interaction.channel.edit(slowmode_delay=segundos)
        e = discord.Embed(description=f"{E_CHECK} Slowmode establecido a {segundos}s.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except:
        await interaction.response.send_message(f"{E_WARN} No pude cambiar el slowmode.", ephemeral=True)
@cmd_slowmode.error
async def _slowmode_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar canales**.", ephemeral=True)

@bot.tree.command(name="topic", description="Cambia el tema del canal (Manage Channels)")
@app_commands.describe(tema="Nuevo tema")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_topic(interaction: discord.Interaction, tema: str):
    try:
        await interaction.channel.edit(topic=tema)
        e = discord.Embed(description=f"{E_CHECK} Tema actualizado.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except:
        await interaction.response.send_message(f"{E_WARN} No pude cambiar el tema.", ephemeral=True)
@cmd_topic.error
async def _topic_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar canales**.", ephemeral=True)

@bot.tree.command(name="softban", description="Expulsa y borra mensajes (Ban Members)")
@app_commands.describe(usuario="Usuario", razon="Motivo")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_softban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin especificar"):
    try:
        await usuario.ban(reason=f"Softban - {razon} — por {interaction.user}", delete_message_days=1)
        await usuario.unban(reason=f"Softban deshecho - {razon} — por {interaction.user}")
        e = discord.Embed(description=f"{E_CHECK} Softban aplicado a {usuario.mention}.", color=C_RED)
        e.set_footer(text=_footer())
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await interaction.response.send_message(f"{E_WARN} No tengo permisos.", ephemeral=True)
@cmd_softban.error
async def _softban_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Banear miembros**.", ephemeral=True)

# ── OTROS COMANDOS ÚTILES ────────────────────────────────────────

@bot.tree.command(name="embed", description="Envía un mensaje embed")
@app_commands.describe(titulo="Título", descripcion="Descripción", color="Color en hex (ej: ff0000)")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_embed(interaction: discord.Interaction, titulo: str, descripcion: str, color: str = "C80000"):
    try:
        color_int = int(color.replace("#",""), 16)
    except:
        color_int = C_RED
    e = discord.Embed(title=titulo, description=descripcion, color=color_int, timestamp=datetime.now(timezone.utc))
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=False)
@cmd_embed.error
async def _embed_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Gestionar mensajes**.", ephemeral=True)

@bot.tree.command(name="dm", description="Envía un mensaje privado a un usuario")
@app_commands.describe(usuario="Usuario", mensaje="Mensaje")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_dm(interaction: discord.Interaction, usuario: discord.Member, mensaje: str):
    try:
        await usuario.send(f"Mensaje de {interaction.user}:\n{mensaje}")
        await interaction.response.send_message(f"{E_CHECK} Mensaje enviado a {usuario.mention}.", ephemeral=True)
    except:
        await interaction.response.send_message(f"{E_WARN} No pude enviar el mensaje.", ephemeral=True)
@cmd_dm.error
async def _dm_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message(f"{E_WARN} Necesitas **Administrador**.", ephemeral=True)

@bot.tree.command(name="feedback", description="Envía un feedback al creador del bot")
@app_commands.describe(mensaje="Tu mensaje")
async def cmd_feedback(interaction: discord.Interaction, mensaje: str):
    owner = bot.get_user(1525040833814855710)  # Reemplaza con tu ID
    if not owner:
        return await interaction.response.send_message(f"{E_WARN} No se pudo enviar el feedback.", ephemeral=True)
    try:
        await owner.send(f"Feedback de {interaction.user} ({interaction.user.id}) en {interaction.guild.name}:\n{mensaje}")
        await interaction.response.send_message(f"{E_CHECK} Feedback enviado. ¡Gracias!", ephemeral=True)
    except:
        await interaction.response.send_message(f"{E_WARN} No se pudo enviar el feedback.", ephemeral=True)

@bot.tree.command(name="report", description="Reporta un usuario al staff")
@app_commands.describe(usuario="Usuario reportado", razon="Motivo")
async def cmd_report(interaction: discord.Interaction, usuario: discord.Member, razon: str):
    owner = bot.get_user(1525040833814855710)
    if owner:
        try:
            await owner.send(f"Reporte de {interaction.user} contra {usuario} en {interaction.guild.name}:\n{razon}")
        except: pass
    await interaction.response.send_message(f"{E_CHECK} Reporte enviado. El staff lo revisará.", ephemeral=True)

@bot.tree.command(name="suggest", description="Envía una sugerencia al staff")
@app_commands.describe(sugerencia="Tu sugerencia")
async def cmd_suggest(interaction: discord.Interaction, sugerencia: str):
    owner = bot.get_user(1525040833814855710)
    if owner:
        try:
            await owner.send(f"Sugerencia de {interaction.user} en {interaction.guild.name}:\n{sugerencia}")
        except: pass
    await interaction.response.send_message(f"{E_CHECK} Sugerencia enviada. ¡Gracias!", ephemeral=True)

@bot.tree.command(name="quote", description="Frase célebre aleatoria")
async def cmd_quote(interaction: discord.Interaction):
    quotes = [
        "El éxito es la capacidad de ir de fracaso en fracaso sin perder el entusiasmo. — Churchill",
        "La vida es lo que pasa mientras estás ocupado haciendo otros planes. — Lennon",
        "El único modo de hacer un gran trabajo es amar lo que haces. — Jobs",
        "No cuentes los días, haz que los días cuenten. — Muhammad Ali",
        "La imaginación es más importante que el conocimiento. — Einstein",
    ]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 📜 Quote", icon_url=URL_CROWN)
    e.description = f"“{random.choice(quotes)}”"
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="fact", description="Dato curioso aleatorio")
async def cmd_fact(interaction: discord.Interaction):
    facts = [
        "Los pulpos tienen tres corazones.",
        "Las abejas pueden reconocer rostros humanos.",
        "El color favorito de la mayoría de la gente es el azul.",
        "Un día en Venus dura más que un año en Venus.",
        "Los humanos compartimos el 60% de nuestro ADN con las bananas.",
    ]
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — 🧠 Fact", icon_url=URL_CROWN)
    e.description = random.choice(facts)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ── SISTEMA DE TICKETS ──────────────────────────────────────────────

def _guild_ticket_cfg(guild_id: int) -> dict:
    return ticket_config.get(str(guild_id), {})

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", emoji="🎫",
                        style=discord.ButtonStyle.danger,
                        custom_id="king_ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, _):
        await _create_ticket(interaction)

class TicketCloseView(View):
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

def embed_giveaway(prize: str, winners: int, end_ts: float, host_id: int, entries: int, msg_id: int) -> discord.Embed:
    e = discord.Embed(color=C_RED, description=(
        f"{E_RDIAM} **Premio:** {prize}\n"
        f"{E_CROWN} **Ganadores:** {winners}\n"
        f"{E_USER} **Organiza:** <@{host_id}>\n"
        f"{E_ARROW} **Termina:** <t:{int(end_ts)}:R>\n"
        f"{E_TICKET} **Participantes:** {entries}\n"
        f"{E_INFO} **ID del mensaje:** `{msg_id}`\n\n"
        f"Pulsa el botón 🎉 para participar."
    ))
    e.set_author(name=f"{BOT_NAME} — 🎉 Giveaway", icon_url=URL_CROWN)
    e.set_footer(text=_footer())
    return e

class GiveawayView(View):
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
            end_embed = embed_giveaway(gw["prize"], gw["winners"], gw["end_ts"], gw["host_id"], len(entries), msg.id)
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

    msg = await target.send(embed=embed_giveaway(premio, ganadores, end_ts, interaction.user.id, 0, 0),
                             view=GiveawayView())
    # Actualizar el embed con el ID real del mensaje
    await msg.edit(embed=embed_giveaway(premio, ganadores, end_ts, interaction.user.id, 0, msg.id))
    
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


# ── SLASH — MODERACIÓN (ya existentes) ───────────────────────────────

WARNS_FILE = "warns.json"
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


# ── SLASH — EXTRAS (ya existentes) ────────────────────────────────────

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


_afk_users: dict = {}

@bot.tree.command(name="afk", description="Marca que estás AFK (ausente)")
@app_commands.describe(mensaje="Motivo (opcional)")
async def cmd_afk(interaction: discord.Interaction, mensaje: str = "AFK"):
    _afk_users[interaction.user.id] = mensaje
    e = discord.Embed(description=f"{E_CHECK} Te marqué como AFK: {mensaje}", color=C_RED)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


# ── SLASH — UTILIDAD (ya existentes) ──────────────────────────────────

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


# ── HELP ──────────────────────────────────────────────────────────

@bot.tree.command(name="help", description="Ver todos los comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Comandos", icon_url=URL_CROWN)
    e.set_thumbnail(url=URL_CROWN)
    e.add_field(
        name=f"{E_RDIAM} Bypass",
        value=f"`/bypass` — Bypassea un enlace\n`/setautobypass` — Auto-bypass en canal *(Admin)*",
        inline=False)
    e.add_field(
        name=f"{E_CROWN} Diversión",
        value=(f"`/8ball` — Bola mágica\n`/joke` — Chiste\n`/coinflip` — Cara o cruz\n"
               f"`/roll [lados]` — Dado\n`/roast <user>` — Insulto\n`/rps` — Piedra papel tijeras\n"
               f"`/rate <cosa>` — Califica 1-10\n`/choose <op1,op2,...>` — Elige\n"
               f"`/math <exp>` — Calculadora\n`/slot` — Tragaperras\n`/truth` — Verdad\n`/dare` — Reto"),
        inline=False)
    e.add_field(
        name=f"🤗 Interacción",
        value=(f"`/hug`, `/kiss`, `/slap`, `/pat`, `/punch`, `/highfive` — Interactúa con un usuario (con GIFs de Nekos.life)\n"
               f"`/ship <user1> [user2]` — Compatibilidad"),
        inline=False)
    e.add_field(
        name=f"💰 Economía",
        value=(f"`/balance` — Saldo\n`/daily` — Diario\n`/work` — Trabajar\n`/beg` — Pedir\n"
               f"`/gamble <cantidad>` — Apostar\n`/transfer <user> <cant>` — Transferir\n"
               f"`/inventory` — Inventario\n`/leaderboard` — Ránking"),
        inline=False)
    e.add_field(
        name=f"🛠️ Utilidad",
        value=(f"`/ping` — Latencia\n`/avatar [user]` — Avatar\n`/banner [user]` — Banner\n"
               f"`/userinfo [user]` — Info usuario\n`/serverinfo` — Info servidor\n"
               f"`/servericon` — Icono servidor\n`/serverbanner` — Banner servidor\n"
               f"`/roleinfo <rol>` — Info rol\n`/channelinfo` — Info canal\n"
               f"`/emojiinfo <emoji>` — Info emoji\n`/invite` — Invitación\n`/botinfo` — Info bot"),
        inline=False)
    e.add_field(
        name=f"🛡️ Moderación",
        value=(f"`/kick`, `/ban`, `/unban`, `/softban` — Gestión de miembros\n"
               f"`/timeout`, `/untimeout` — Silenciar\n`/warn`, `/warnings`, `/clear-warnings` — Advertencias\n"
               f"`/clear <cant>` — Borrar mensajes\n`/lock`, `/unlock` — Bloquear canal\n"
               f"`/slowmode <seg>` — Slowmode\n`/topic <texto>` — Tema del canal\n"
               f"`/addrole`, `/removerole` — Roles\n`/nick` — Apodo"),
        inline=False)
    e.add_field(
        name=f"🎫 Tickets",
        value=(f"`/ticket-setup` — Configurar (Admin)\n`/ticket-panel` — Publicar panel\n"
               f"`/ticket-close` — Cerrar ticket"),
        inline=False)
    e.add_field(
        name=f"🎉 Giveaways",
        value=(f"`/giveaway-start` — Iniciar (muestra ID del mensaje)\n`/giveaway-end` — Terminar\n`/giveaway-reroll` — Reroll"),
        inline=False)
    e.add_field(
        name=f"📝 Otros",
        value=(f"`/poll` — Encuesta\n`/remind` — Recordatorio\n`/afk` — AFK\n"
               f"`/say <msg>` — Decir\n`/embed` — Enviar embed\n`/dm <user> <msg>` — Enviar DM\n"
               f"`/feedback` — Feedback\n`/report` — Reportar\n`/suggest` — Sugerir\n"
               f"`/quote` — Frase célebre\n`/fact` — Dato curioso"),
        inline=False)
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=_footer())
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
