"""
KING BOT — Bypass + Fun Commands
"""
import sys, types

try:
    import audioop
except ImportError:
    sys.modules["audioop"] = types.ModuleType("audioop")

import os, re, json, time, asyncio, logging, threading, random
from datetime import datetime, timezone
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

BOT_NAME   = "KING BOT"
BOT_CREDIT = "BY KING"

BYPASS_API_URL = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT = 30
BYPASS_RETRIES = 3
BYPASS_DELAY   = 3

AUTOBYPASS_FILE = "autobypass_channels.json"

# ── COLORES ──────────────────────────────────────────────────────
C_RED   = 0xC80000   # rojo oscuro principal
C_DARK  = 0x1A0000   # casi negro con tono rojo
C_WARN  = 0xFF4500   # rojo-naranja para loading
C_INFO  = 0x8B0000   # rojo profundo

# ── IMAGEN PRINCIPAL ─────────────────────────────────────────────
IMG_MAIN = "https://cdn.discordapp.com/attachments/1525427252400099381/1525750876155805847/ezgif-37d313baab956afc.gif?ex=6a5485bb&is=6a53343b&hm=f6df69c459c7bad9ed031d12eee35f42ab4adbb7290fe08a3707046eb3bf7200&"

# ── TUS EMOJIS ───────────────────────────────────────────────────
E_CHECK   = "<a:_:1511381303872716820>"   # ✅ check mark
E_REDPT   = "<a:_:1463164698353733725>"   # 🔴 red point
E_WARN    = "<:_:1495901573476520106>"    # ⚠️ warning
E_RDIAM   = "<a:_:1469195655762153502>"   # 💎 red diamond
E_ARROW   = "<a:_:1401389285042684035>"   # ➡️ arrow
E_CROWN   = "<a:_:1461735621985833061>"   # 👑 red crown
E_NO      = "<a:_:606562703917449226>"    # ❌ no
E_LOAD    = "<a:_:1463540610379022429>"   # ⏳ load
E_USER    = "👤"  # persona

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
    e.set_author(name=f"BYPASSED SUCCESSFULLY", icon_url=URL_CHECK)
    e.set_thumbnail(url=URL_CHECK)
    e.add_field(
        name=f"{E_RDIAM} ─ RESULT",
        value=f"```\n{result[:900]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{E_USER} ─ REQUEST BY",
        value=user.mention,
        inline=False
    )
    e.add_field(
        name=f"{E_ARROW} ─ URL",
        value=f"```\n{url[:200]}\n```",
        inline=False
    )
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"SYSTEM MADE WITH 🔥  |  {_footer()}")
    return e

def embed_fail(error: str, url: str, elapsed: float, user: discord.User) -> discord.Embed:
    e = discord.Embed(color=C_RED, timestamp=datetime.now(timezone.utc))
    e.set_author(name="BYPASS FAILED", icon_url=URL_NO)
    e.set_thumbnail(url=URL_NO)
    e.add_field(
        name=f"{E_RDIAM} ─ URL",
        value=f"```\n{url[:200]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{E_WARN} ─ ERROR",
        value=f"```\n{error or '?'}\n```",
        inline=False
    )
    e.add_field(
        name=f"{E_USER} ─ REQUEST BY",
        value=user.mention,
        inline=False
    )
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"SYSTEM MADE WITH 🔥  |  {_footer()}")
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

    @discord.ui.button(label="📋  Copiar RESURTADO",
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

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online como {self.user} | {len(self.guilds)} servidor(es)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"/help • {BOT_NAME}"))

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
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
        name=f"{E_ARROW} Utilidad",
        value="`/ping` — Latencia\n`/help` — Esta lista",
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
