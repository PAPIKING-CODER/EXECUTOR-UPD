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

# Endpoint de GIFs (público, sin API key). Si tienes una API propia,
# solo reemplaza GIF_API_BASE y ajusta _fetch_gif().
GIF_API_BASE = "https://nekos.best/api/v2"

# ── NUEVOS EMOJIS PERSONALIZADOS (SIN UNICODE, EXCEPTO 📱) ────
# Formato Normal: <:Nombre:ID>
# Formato Animado: <a:Nombre:ID>

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
EMOJI_PC_OBJ      = discord.PartialEmoji(name="fmd_pc", id=1526858555544572035)

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
            return "📱"  # Excepción explícita permitida para móvil
        else:
            return "PC"
    except Exception:
        return "PC"

def _e(title: str, description: str = "", color: int = C_GREEN) -> discord.Embed:
    """Embed base reutilizable para todos los comandos nuevos."""
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
                last_error = "Respuesta inválida de la API"
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
                last_error = str(err_msg or "La API reportó un error.")
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            return None, "No se encontró resultado en la API."

        except requests.exceptions.Timeout:
            last_error = f"Tiempo de espera agotado ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
        except Exception as e:
            last_error = str(e)[:100]
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)

    return None, last_error

# ── ARCHIVOS JSON (Auto-Bypass: guarda un set de IDs) ───────────
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

# ── ARCHIVOS JSON (Datos generales: economía, niveles, etc) ────
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

# ── EMBEDS (Diseño Premium Verde) ──────────────────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS")
    e.title = f"{EMOJI_LOADER} Generating Bypass..."
    e.description = "Processing your link...\nPlease wait..."
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif") # Loader
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform: str) -> discord.Embed:
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.description = "Generated successfully.\n\n🕒 Auto delete in 120s"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif") # Corona obligatoria

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

# ── VIEW (SOLO 3 BOTONES) ──────────────────────────────────────
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

# ── CUENTA REGRESIVA EN VIVO Y AUTO ELIMINACIÓN ────────────────
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

# ── BOT CLIENT ──────────────────────────────────────────────────
class FmdBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Comandos globales sincronizados.")

    async def on_ready(self):
        logger.info("=========================================")
        logger.info(f"✅ {self.user.name} Online!")
        logger.info(f"📡 Servidores: {len(self.guilds)}")
        logger.info(f"⚙️ Comandos registrados: {len(self.tree.get_commands())}")
        logger.info("=========================================")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # XP por mensaje
        lvl = get_level(message.guild.id, message.author.id)
        lvl["xp"] += random.randint(5, 15)
        needed = xp_needed(lvl["level"])
        if lvl["xp"] >= needed:
            lvl["xp"] -= needed
            lvl["level"] += 1
            try:
                await message.channel.send(embed=_e("¡Subiste de Nivel!", f"{message.author.mention} ahora es nivel **{lvl['level']}**"))
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
#  SLASH COMMANDS — SISTEMA DE BYPASS (NO TOCAR)
# ══════════════════════════════════════════════════════════════

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

@bot.tree.command(name="ping", description="🏓 Ver la latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name="FMD BOT • BYPASS", icon_url="")
    e.add_field(name="Latencia", value=f"`{ms}ms`", inline=True)
    e.add_field(name="Uptime", value=f"`{_uptime()}`", inline=True)
    e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


def _perm_error_handler(cmd):
    @cmd.error
    async def _handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("🚫 Necesitas permiso de Administrador!", ephemeral=True)
        else:
            await _send_error(interaction, f"```\n{str(error)[:200]}\n```")
    return _handler


# ══════════════════════════════════════════════════════════════
#  MODERACIÓN
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="kick", description="👢 [Admin] Expulsar a un miembro del servidor")
@app_commands.describe(usuario="Usuario a expulsar", razon="Razón de la expulsión")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    if usuario.id == interaction.user.id:
        return await _send_error(interaction, "No puedes expulsarte a ti mismo.")
    try:
        await usuario.kick(reason=razon)
        e = _e("Miembro Expulsado")
        e.add_field(name="Usuario", value=f"`{usuario}`", inline=True)
        e.add_field(name="Moderador", value=f"`{interaction.user}`", inline=True)
        e.add_field(name="Razón", value=f"`{razon}`", inline=False)
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await _send_error(interaction, "No tengo permisos suficientes para expulsar a este usuario.")
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_kick)

@bot.tree.command(name="ban", description="🔨 [Admin] Banear a un miembro del servidor")
@app_commands.describe(usuario="Usuario a banear", razon="Razón del baneo")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_ban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    if usuario.id == interaction.user.id:
        return await _send_error(interaction, "No puedes banearte a ti mismo.")
    try:
        await usuario.ban(reason=razon)
        e = _e("Miembro Baneado")
        e.add_field(name="Usuario", value=f"`{usuario}`", inline=True)
        e.add_field(name="Moderador", value=f"`{interaction.user}`", inline=True)
        e.add_field(name="Razón", value=f"`{razon}`", inline=False)
        await interaction.response.send_message(embed=e)
    except discord.Forbidden:
        await _send_error(interaction, "No tengo permisos suficientes para banear a este usuario.")
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_ban)

@bot.tree.command(name="unban", description="🔓 [Admin] Desbanear a un usuario por su ID")
@app_commands.describe(user_id="ID del usuario a desbanear")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=_e("Usuario Desbaneado", f"`{user}` fue desbaneado."))
    except ValueError:
        await _send_error(interaction, "El ID proporcionado no es válido.")
    except discord.NotFound:
        await _send_error(interaction, "Ese usuario no está baneado.")
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_unban)

@bot.tree.command(name="softban", description="🔨 [Admin] Banea y desbanea para limpiar mensajes del usuario")
@app_commands.describe(usuario="Usuario a softbanear", razon="Razón")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_softban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    try:
        await usuario.ban(reason=razon, delete_message_days=1)
        await interaction.guild.unban(usuario)
        await interaction.response.send_message(embed=_e("Softban Aplicado", f"`{usuario}` fue softbaneado (sus mensajes recientes fueron eliminados)."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_softban)

@bot.tree.command(name="mute", description="🔇 [Admin] Silenciar a un usuario (timeout)")
@app_commands.describe(usuario="Usuario a silenciar", minutos="Duración en minutos")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_mute(interaction: discord.Interaction, usuario: discord.Member, minutos: int = 10):
    if minutos < 1 or minutos > 40320:
        return await _send_error(interaction, "La duración debe estar entre `1` y `40320` minutos (28 días).")
    try:
        await usuario.timeout(discord.utils.utcnow() + timedelta(minutes=minutos), reason=f"Mute por {interaction.user}")
        await interaction.response.send_message(embed=_e("Usuario Silenciado", f"{usuario.mention} fue silenciado por `{minutos}` min."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_mute)

@bot.tree.command(name="unmute", description="🔊 [Admin] Quitar el silencio a un usuario")
@app_commands.describe(usuario="Usuario a des-silenciar")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unmute(interaction: discord.Interaction, usuario: discord.Member):
    try:
        await usuario.timeout(None, reason=f"Unmute por {interaction.user}")
        await interaction.response.send_message(embed=_e("Silencio Removido", f"{usuario.mention} ya no está silenciado."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_unmute)

@bot.tree.command(name="warn", description="⚠️ [Admin] Advertir a un usuario")
@app_commands.describe(usuario="Usuario a advertir", razon="Razón de la advertencia")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_warn(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warnings_data.setdefault(gid, {}).setdefault(uid, [])
    warnings_data[gid][uid].append({"mod": str(interaction.user.id), "reason": razon, "ts": int(time.time())})
    save_data("warnings", warnings_data)
    await interaction.response.send_message(embed=_e("Advertencia Añadida", f"{usuario.mention} fue advertido.\nTotal: `{len(warnings_data[gid][uid])}`"))
_perm_error_handler(cmd_warn)

@bot.tree.command(name="unwarn", description="✅ [Admin] Quitar una advertencia a un usuario")
@app_commands.describe(usuario="Usuario", indice="Número de advertencia a remover (empieza en 1)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unwarn(interaction: discord.Interaction, usuario: discord.Member, indice: int = 1):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warns = warnings_data.get(gid, {}).get(uid, [])
    if not warns or len(warns) < indice or indice < 1:
        return await _send_error(interaction, "No existe una advertencia en ese índice.")
    warns.pop(indice - 1)
    save_data("warnings", warnings_data)
    await interaction.response.send_message(embed=_e("Advertencia Removida", f"Advertencia #{indice} removida de {usuario.mention}."))
_perm_error_handler(cmd_unwarn)

@bot.tree.command(name="warnings", description="📋 Ver las advertencias de un usuario")
@app_commands.describe(usuario="Usuario a consultar")
async def cmd_warnings(interaction: discord.Interaction, usuario: discord.Member):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warns = warnings_data.get(gid, {}).get(uid, [])
    if not warns:
        return await interaction.response.send_message(embed=_e("Advertencias", f"{usuario.mention} no tiene advertencias."))
    desc = "\n".join(f"`{i+1}.` {w['reason']} — <t:{w['ts']}:R>" for i, w in enumerate(warns))
    await interaction.response.send_message(embed=_e(f"Advertencias de {usuario.display_name}", desc))

@bot.tree.command(name="clear", description="🧹 [Admin] Eliminar mensajes masivamente")
@app_commands.describe(cantidad="Cantidad de mensajes a eliminar (1-100)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_clear(interaction: discord.Interaction, cantidad: int):
    if cantidad < 1 or cantidad > 100:
        return await interaction.response.send_message(embed=_e("Cantidad Inválida", "La cantidad debe estar entre `1` y `100`.", C_WARN), ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=cantidad)
        await interaction.followup.send(embed=_e("Mensajes Eliminados", f"Se eliminaron `{len(deleted)}` mensajes de {interaction.channel.mention}."), ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(embed=_e("Error de Permisos", "No tengo permisos suficientes para eliminar mensajes.", C_ERROR), ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(embed=_e("Error", f"```\n{str(ex)[:200]}\n```", C_ERROR), ephemeral=True)
_perm_error_handler(cmd_clear)

@bot.tree.command(name="purgeuser", description="🧹 [Admin] Eliminar mensajes de un usuario específico")
@app_commands.describe(usuario="Usuario cuyos mensajes se eliminarán", cantidad="Cantidad de mensajes a revisar (máx 200)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_purgeuser(interaction: discord.Interaction, usuario: discord.Member, cantidad: int = 50):
    cantidad = max(1, min(cantidad, 200))
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=cantidad, check=lambda m: m.author.id == usuario.id)
        await interaction.followup.send(embed=_e("Mensajes Eliminados", f"Se eliminaron `{len(deleted)}` mensajes de {usuario.mention}."), ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(embed=_e("Error", f"```\n{str(ex)[:200]}\n```", C_ERROR), ephemeral=True)
_perm_error_handler(cmd_purgeuser)

@bot.tree.command(name="lock", description="🔒 [Admin] Bloquear el canal actual")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(embed=_e("Canal Bloqueado", f"{interaction.channel.mention} fue bloqueado."))
_perm_error_handler(cmd_lock)

@bot.tree.command(name="unlock", description="🔓 [Admin] Desbloquear el canal actual")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
    await interaction.response.send_message(embed=_e("Canal Desbloqueado", f"{interaction.channel.mention} fue desbloqueado."))
_perm_error_handler(cmd_unlock)

@bot.tree.command(name="slowmode", description="🐌 [Admin] Configurar el modo lento del canal")
@app_commands.describe(segundos="Segundos entre mensajes (0 para desactivar, máx 21600)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_slowmode(interaction: discord.Interaction, segundos: int):
    segundos = max(0, min(segundos, 21600))
    await interaction.channel.edit(slowmode_delay=segundos)
    if segundos == 0:
        await interaction.response.send_message(embed=_e("Modo Lento Desactivado", f"{interaction.channel.mention} ya no tiene modo lento."))
    else:
        await interaction.response.send_message(embed=_e("Modo Lento Activado", f"{interaction.channel.mention} ahora tiene `{segundos}s` de espera entre mensajes."))
_perm_error_handler(cmd_slowmode)

@bot.tree.command(name="nickname", description="✏️ [Admin] Cambiar el apodo de un usuario")
@app_commands.describe(usuario="Usuario", apodo="Nuevo apodo (vacío para quitarlo)")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_nickname(interaction: discord.Interaction, usuario: discord.Member, apodo: str = None):
    try:
        await usuario.edit(nick=apodo)
        desc = f"El apodo de {usuario.mention} fue cambiado a `{apodo}`." if apodo else f"El apodo de {usuario.mention} fue removido."
        await interaction.response.send_message(embed=_e("Apodo Actualizado", desc))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_nickname)


# ══════════════════════════════════════════════════════════════
#  DIVERSIÓN
# ══════════════════════════════════════════════════════════════

_8BALL_RESPONSES = [
    "Sí, definitivamente.", "Es cierto.", "Sin duda alguna.", "Sí, puedes confiar en ello.",
    "Muy probable.", "Las señales apuntan a que sí.", "Respuesta dudosa, intenta de nuevo.",
    "Pregunta de nuevo más tarde.", "Mejor no decirte ahora.", "No puedo predecirlo ahora.",
    "Concéntrate y pregunta de nuevo.", "No cuentes con ello.", "Mi respuesta es no.",
    "Mis fuentes dicen que no.", "Muy dudoso.",
]

@bot.tree.command(name="8ball", description="🎱 Pregúntale algo a la bola mágica")
@app_commands.describe(pregunta="Tu pregunta para la bola mágica")
async def cmd_8ball(interaction: discord.Interaction, pregunta: str):
    respuesta = random.choice(_8BALL_RESPONSES)
    e = _e("Bola Mágica")
    e.add_field(name="Pregunta", value=f"`{pregunta}`", inline=False)
    e.add_field(name="Respuesta", value=f"`{respuesta}`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="coinflip", description="🪙 Lanzar una moneda")
async def cmd_coinflip(interaction: discord.Interaction):
    resultado = random.choice(["Cara", "Cruz"])
    await interaction.response.send_message(embed=_e("Lanzamiento de Moneda", f"La moneda cayó en: `{resultado}`"))

@bot.tree.command(name="dice", description="🎲 Lanzar un dado")
@app_commands.describe(caras="Cantidad de caras del dado (default 6, máx 100)")
async def cmd_dice(interaction: discord.Interaction, caras: int = 6):
    if caras < 2 or caras > 100:
        return await interaction.response.send_message(embed=_e("Valor Inválido", "El dado debe tener entre `2` y `100` caras.", C_WARN), ephemeral=True)
    resultado = random.randint(1, caras)
    await interaction.response.send_message(embed=_e("Lanzamiento de Dado", f"Dado de `{caras}` caras — Resultado: `{resultado}`"))

@bot.tree.command(name="rps", description="✊ Piedra, papel o tijera contra el bot")
@app_commands.describe(eleccion="Tu elección")
@app_commands.choices(eleccion=[
    app_commands.Choice(name="Piedra", value="piedra"),
    app_commands.Choice(name="Papel", value="papel"),
    app_commands.Choice(name="Tijera", value="tijera"),
])
async def cmd_rps(interaction: discord.Interaction, eleccion: app_commands.Choice[str]):
    opciones = ["piedra", "papel", "tijera"]
    bot_choice = random.choice(opciones)
    user_choice = eleccion.value
    if user_choice == bot_choice:
        resultado, color = "Empate", C_WARN
    elif (user_choice, bot_choice) in [("piedra", "tijera"), ("papel", "piedra"), ("tijera", "papel")]:
        resultado, color = "¡Ganaste!", C_GREEN
    else:
        resultado, color = "Perdiste.", C_ERROR
    e = _e("Piedra, Papel o Tijera", color=color)
    e.add_field(name="Tu elección", value=f"`{user_choice}`", inline=True)
    e.add_field(name="Bot", value=f"`{bot_choice}`", inline=True)
    e.add_field(name="Resultado", value=f"`{resultado}`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ship", description="❤️ Calcula la compatibilidad entre dos personas")
@app_commands.describe(usuario1="Primera persona", usuario2="Segunda persona")
async def cmd_ship(interaction: discord.Interaction, usuario1: discord.Member, usuario2: discord.Member):
    amor = random.randint(0, 100)
    barra = "🟩" * (amor // 10) + "⬛" * (10 - amor // 10)
    e = _e("Calculadora de Amor", f"{usuario1.mention} + {usuario2.mention}\n\n{barra}\n`{amor}%`")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="choose", description="🎯 Elige una opción al azar entre varias")
@app_commands.describe(opciones="Opciones separadas por coma")
async def cmd_choose(interaction: discord.Interaction, opciones: str):
    lista = [o.strip() for o in opciones.split(",") if o.strip()]
    if len(lista) < 2:
        return await _send_error(interaction, "Necesitas al menos 2 opciones separadas por coma.")
    elegido = random.choice(lista)
    await interaction.response.send_message(embed=_e("Elección Aleatoria", f"De entre: `{', '.join(lista)}`\n\nElegí: **{elegido}**"))

@bot.tree.command(name="reverse", description="🔁 Invierte un texto")
@app_commands.describe(texto="Texto a invertir")
async def cmd_reverse(interaction: discord.Interaction, texto: str):
    await interaction.response.send_message(embed=_e("Texto Invertido", f"`{texto[::-1]}`"))

@bot.tree.command(name="say", description="📢 [Admin] Hacer que el bot repita un mensaje")
@app_commands.describe(mensaje="Mensaje a enviar")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_say(interaction: discord.Interaction, mensaje: str):
    await interaction.response.send_message(embed=_e("Mensaje Enviado", "Listo."), ephemeral=True)
    await interaction.channel.send(mensaje)
_perm_error_handler(cmd_say)

@bot.tree.command(name="meme", description="😂 Meme aleatorio de Reddit")
async def cmd_meme(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        e = discord.Embed(title=f"{EMOJI_GREEN_DOT} {r['title'][:250]}", color=C_GREEN, timestamp=datetime.now(timezone.utc))
        e.set_image(url=r["url"])
        e.set_footer(text=f"r/{r['subreddit']} • {_footer()}")
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=_e("Error", "No se pudo obtener un meme en este momento.", C_ERROR))

@bot.tree.command(name="joke", description="😄 Chiste aleatorio")
async def cmd_joke(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://v2.jokeapi.dev/joke/Any?lang=es&safe-mode", timeout=10).json()
        txt = r["joke"] if r["type"] == "single" else f"{r['setup']}\n\n{r['delivery']}"
        await interaction.followup.send(embed=_e("Chiste Aleatorio", txt))
    except Exception:
        await interaction.followup.send(embed=_e("Error", "No se pudo obtener un chiste en este momento.", C_ERROR))

@bot.tree.command(name="fact", description="🧠 Dato curioso aleatorio")
async def cmd_fact(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=10).json()
        await interaction.followup.send(embed=_e("Dato Curioso", r.get("text", "N/A")))
    except Exception:
        await interaction.followup.send(embed=_e("Error", "No se pudo obtener un dato curioso.", C_ERROR))


# ── COMANDOS DE GIF (nekos.best — público, sin API key) ─────────
async def _send_gif_action(interaction: discord.Interaction, action: str, verbo: str, usuario: discord.Member = None):
    await interaction.response.defer()
    gif_url = None
    try:
        r = requests.get(f"{GIF_API_BASE}/{action}", timeout=10).json()
        gif_url = r["results"][0]["url"]
    except Exception:
        pass
    desc = f"{interaction.user.mention} {verbo} a {usuario.mention}" if usuario else f"{interaction.user.mention} {verbo}"
    e = _e(verbo.capitalize(), desc)
    if gif_url:
        e.set_image(url=gif_url)
    else:
        e.description += "\n\n⚠️ No se pudo cargar el GIF en este momento."
    await interaction.followup.send(embed=e)

@bot.tree.command(name="hug", description="🤗 Abraza a alguien")
@app_commands.describe(usuario="A quién abrazar")
async def cmd_hug(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "hug", "abraza", usuario)

@bot.tree.command(name="kiss", description="😘 Besa a alguien")
@app_commands.describe(usuario="A quién besar")
async def cmd_kiss(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "kiss", "besa", usuario)

@bot.tree.command(name="pat", description="🖐️ Acaricia la cabeza de alguien")
@app_commands.describe(usuario="A quién acariciar")
async def cmd_pat(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "pat", "acaricia", usuario)

@bot.tree.command(name="slap", description="👋 Abofetea a alguien")
@app_commands.describe(usuario="A quién abofetear")
async def cmd_slap(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "slap", "abofetea", usuario)

@bot.tree.command(name="cry", description="😢 Llora")
async def cmd_cry(interaction: discord.Interaction):
    await _send_gif_action(interaction, "cry", "llora")

@bot.tree.command(name="dance", description="💃 Baila")
async def cmd_dance(interaction: discord.Interaction):
    await _send_gif_action(interaction, "dance", "baila")

@bot.tree.command(name="poke", description="👉 Pica a alguien")
@app_commands.describe(usuario="A quién picar")
async def cmd_poke(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "poke", "pica", usuario)

@bot.tree.command(name="tickle", description="🤣 Hace cosquillas a alguien")
@app_commands.describe(usuario="A quién hacer cosquillas")
async def cmd_tickle(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "tickle", "le hace cosquillas", usuario)

@bot.tree.command(name="blush", description="😳 Se sonroja")
async def cmd_blush(interaction: discord.Interaction):
    await _send_gif_action(interaction, "blush", "se sonroja")

@bot.tree.command(name="highfive", description="🙏 Choca los cinco con alguien")
@app_commands.describe(usuario="Con quién chocar los cinco")
async def cmd_highfive(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "highfive", "choca los cinco con", usuario)

@bot.tree.command(name="bite", description="😬 Muerde a alguien")
@app_commands.describe(usuario="A quién morder")
async def cmd_bite(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "bite", "muerde a", usuario)

@bot.tree.command(name="cuddle", description="🥰 Acurruca a alguien")
@app_commands.describe(usuario="A quién acurrucar")
async def cmd_cuddle(interaction: discord.Interaction, usuario: discord.Member = None):
    await _send_gif_action(interaction, "cuddle", "acurruca a", usuario)

@bot.tree.command(name="wave", description="👋 Saluda")
async def cmd_wave(interaction: discord.Interaction):
    await _send_gif_action(interaction, "wave", "saluda")

@bot.tree.command(name="smile", description="😄 Sonríe")
async def cmd_smile(interaction: discord.Interaction):
    await _send_gif_action(interaction, "smile", "sonríe")


# ══════════════════════════════════════════════════════════════
#  UTILIDAD
# ══════════════════════════════════════════════════════════════

class AvatarView(View):
    def __init__(self, avatar_url: str):
        super().__init__(timeout=None)
        self.add_item(Button(label="Abrir en navegador", url=avatar_url, style=discord.ButtonStyle.link))

@bot.tree.command(name="avatar", description="🖼️ Muestra el avatar de un usuario")
@app_commands.describe(usuario="Usuario del que quieres ver el avatar")
async def cmd_avatar(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    avatar_url = usuario.display_avatar.url
    e = _e(f"Avatar de {usuario.display_name}")
    e.set_image(url=avatar_url)
    await interaction.response.send_message(embed=e, view=AvatarView(avatar_url))

@bot.tree.command(name="banner", description="🎴 Muestra el banner de un usuario")
@app_commands.describe(usuario="Usuario del que quieres ver el banner")
async def cmd_banner(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    try:
        full_user = await bot.fetch_user(usuario.id)
        if not full_user.banner:
            return await interaction.response.send_message(embed=_e("Sin Banner", f"{usuario.mention} no tiene un banner configurado.", C_WARN))
        e = _e(f"Banner de {usuario.display_name}")
        e.set_image(url=full_user.banner.url)
        await interaction.response.send_message(embed=e)
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")

@bot.tree.command(name="userinfo", description="👤 Muestra información detallada de un usuario")
@app_commands.describe(usuario="Usuario del que quieres ver la información")
async def cmd_userinfo(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    roles = [r.mention for r in reversed(usuario.roles) if r.name != "@everyone"]
    e = _e(f"Información de {usuario.display_name}")
    e.set_thumbnail(url=usuario.display_avatar.url)
    e.add_field(name="Usuario", value=f"`{usuario}`", inline=True)
    e.add_field(name="ID", value=f"`{usuario.id}`", inline=True)
    e.add_field(name="Bot", value=f"`{'Sí' if usuario.bot else 'No'}`", inline=True)
    e.add_field(name="Cuenta creada", value=f"<t:{int(usuario.created_at.timestamp())}:R>", inline=True)
    e.add_field(name="Se unió", value=f"<t:{int(usuario.joined_at.timestamp())}:R>" if usuario.joined_at else "`N/A`", inline=True)
    e.add_field(name="Rol más alto", value=usuario.top_role.mention if usuario.top_role else "`N/A`", inline=True)
    e.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles[:15]) if roles else "`Ninguno`", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverinfo", description="📋 Muestra información del servidor")
async def cmd_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    if g is None:
        return await _send_error(interaction, "Este comando solo funciona dentro de un servidor.")
    e = _e(g.name)
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="ID", value=f"`{g.id}`", inline=True)
    e.add_field(name="Dueño", value=g.owner.mention if g.owner else "`Desconocido`", inline=True)
    e.add_field(name="Miembros", value=f"`{g.member_count}`", inline=True)
    e.add_field(name="Canales", value=f"`{len(g.channels)}`", inline=True)
    e.add_field(name="Roles", value=f"`{len(g.roles)}`", inline=True)
    e.add_field(name="Boosts", value=f"`{g.premium_subscription_count}`", inline=True)
    e.add_field(name="Creado", value=f"<t:{int(g.created_at.timestamp())}:R>", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="servericon", description="🖼️ Muestra el ícono del servidor")
async def cmd_servericon(interaction: discord.Interaction):
    g = interaction.guild
    if not g.icon:
        return await interaction.response.send_message(embed=_e("Sin Ícono", "Este servidor no tiene un ícono configurado.", C_WARN))
    e = _e(f"Ícono de {g.name}")
    e.set_image(url=g.icon.url)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverbanner", description="🎴 Muestra el banner del servidor")
async def cmd_serverbanner(interaction: discord.Interaction):
    g = interaction.guild
    if not g.banner:
        return await interaction.response.send_message(embed=_e("Sin Banner", "Este servidor no tiene un banner configurado.", C_WARN))
    e = _e(f"Banner de {g.name}")
    e.set_image(url=g.banner.url)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="roleinfo", description="🎭 Muestra información de un rol específico")
@app_commands.describe(rol="Rol del que quieres ver la información")
async def cmd_roleinfo(interaction: discord.Interaction, rol: discord.Role):
    e = discord.Embed(title=f"{EMOJI_GREEN_DOT} Información del Rol", color=rol.color if rol.color.value else C_GREEN, timestamp=datetime.now(timezone.utc))
    e.add_field(name="Nombre", value=f"`{rol.name}`", inline=True)
    e.add_field(name="ID", value=f"`{rol.id}`", inline=True)
    e.add_field(name="Color", value=f"`{str(rol.color)}`", inline=True)
    e.add_field(name="Miembros con este rol", value=f"`{len(rol.members)}`", inline=True)
    e.add_field(name="Posición", value=f"`{rol.position}`", inline=True)
    e.add_field(name="Mencionable", value=f"`{'Sí' if rol.mentionable else 'No'}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="channelinfo", description="📂 Muestra información del canal actual")
async def cmd_channelinfo(interaction: discord.Interaction):
    ch = interaction.channel
    e = _e(f"Información de #{ch.name}")
    e.add_field(name="ID", value=f"`{ch.id}`", inline=True)
    e.add_field(name="Tipo", value=f"`{ch.type}`", inline=True)
    e.add_field(name="Creado", value=f"<t:{int(ch.created_at.timestamp())}:R>", inline=True)
    if isinstance(ch, discord.TextChannel):
        e.add_field(name="Categoría", value=f"`{ch.category.name if ch.category else 'Ninguna'}`", inline=True)
        e.add_field(name="Modo Lento", value=f"`{ch.slowmode_delay}s`", inline=True)
        e.add_field(name="NSFW", value=f"`{'Sí' if ch.is_nsfw() else 'No'}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="membercount", description="👥 Muestra la cantidad de miembros del servidor")
async def cmd_membercount(interaction: discord.Interaction):
    g = interaction.guild
    humanos = sum(1 for m in g.members if not m.bot)
    bots = sum(1 for m in g.members if m.bot)
    e = _e("Miembros del Servidor")
    e.add_field(name="Humanos", value=f"`{humanos}`", inline=True)
    e.add_field(name="Bots", value=f"`{bots}`", inline=True)
    e.add_field(name="Total", value=f"`{g.member_count}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="emojicount", description="😃 Muestra la cantidad de emojis del servidor")
async def cmd_emojicount(interaction: discord.Interaction):
    g = interaction.guild
    estaticos = sum(1 for em in g.emojis if not em.animated)
    animados = sum(1 for em in g.emojis if em.animated)
    e = _e("Emojis del Servidor")
    e.add_field(name="Estáticos", value=f"`{estaticos}`", inline=True)
    e.add_field(name="Animados", value=f"`{animados}`", inline=True)
    e.add_field(name="Total", value=f"`{len(g.emojis)}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="botpermissions", description="🔐 Muestra los permisos del bot en este canal")
async def cmd_botpermissions(interaction: discord.Interaction):
    perms = interaction.channel.permissions_for(interaction.guild.me)
    activos = [p.replace("_", " ").title() for p, v in perms if v]
    desc = ", ".join(f"`{p}`" for p in activos[:25])
    await interaction.response.send_message(embed=_e("Permisos del Bot", desc or "Ninguno"))

@bot.tree.command(name="poll", description="📊 Crear una encuesta rápida")
@app_commands.describe(pregunta="Pregunta de la encuesta")
async def cmd_poll(interaction: discord.Interaction, pregunta: str):
    e = _e("Nueva Encuesta", pregunta)
    e.set_footer(text=f"Encuesta por {interaction.user.display_name} • {_footer()}")
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")

@bot.tree.command(name="calc", description="🧮 Calculadora simple")
@app_commands.describe(expresion="Expresión matemática, ej: (5+3)*2")
async def cmd_calc(interaction: discord.Interaction, expresion: str):
    if not re.match(r"^[0-9+\-*/().\s%]+$", expresion):
        return await _send_error(interaction, "Solo se permiten números y operadores matemáticos (+ - * / % ( )).")
    try:
        resultado = eval(expresion, {"__builtins__": {}}, {})
        await interaction.response.send_message(embed=_e("Calculadora", f"`{expresion}` = `{resultado}`"))
    except Exception:
        await _send_error(interaction, "No se pudo calcular esa expresión.")

@bot.tree.command(name="timestamp", description="🕒 Convierte una fecha a timestamp de Discord")
@app_commands.describe(fecha="Formato: AAAA-MM-DD HH:MM (24h)")
async def cmd_timestamp(interaction: discord.Interaction, fecha: str):
    try:
        dt = datetime.strptime(fecha, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        ts = int(dt.timestamp())
        desc = f"`<t:{ts}:F>` → <t:{ts}:F>\n`<t:{ts}:R>` → <t:{ts}:R>"
        await interaction.response.send_message(embed=_e("Timestamp Generado", desc))
    except ValueError:
        await _send_error(interaction, "Formato inválido. Usa: `AAAA-MM-DD HH:MM` (ej: `2026-12-25 18:00`).")

@bot.tree.command(name="remindme", description="⏰ Crear un recordatorio personal")
@app_commands.describe(minutos="En cuántos minutos recordarte", mensaje="Qué quieres que te recuerde")
async def cmd_remindme(interaction: discord.Interaction, minutos: int, mensaje: str):
    if minutos < 1 or minutos > 10080:
        return await _send_error(interaction, "Los minutos deben estar entre `1` y `10080` (7 días).")
    await interaction.response.send_message(embed=_e("Recordatorio Creado", f"Te recordaré en `{minutos}` min: {mensaje}"))

    async def remind_later():
        await asyncio.sleep(minutos * 60)
        try:
            await interaction.user.send(embed=_e("⏰ Recordatorio", mensaje))
        except Exception:
            try:
                await interaction.channel.send(f"{interaction.user.mention} ⏰ Recordatorio: {mensaje}")
            except Exception:
                pass

    asyncio.create_task(remind_later())


# ══════════════════════════════════════════════════════════════
#  BÚSQUEDA
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="wikipedia", description="📚 Buscar en Wikipedia")
@app_commands.describe(busqueda="Qué quieres buscar")
async def cmd_wikipedia(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    try:
        r = requests.get(f"https://es.wikipedia.org/api/rest_v1/page/summary/{quote(busqueda)}", timeout=10)
        if r.status_code != 200:
            return await interaction.followup.send(embed=_e("Sin Resultados", "No se encontró el artículo.", C_WARN))
        data = r.json()
        e = _e(data.get("title", busqueda), data.get("extract", "")[:1500])
        if data.get("thumbnail"):
            e.set_thumbnail(url=data["thumbnail"]["source"])
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Error al buscar en Wikipedia.", C_ERROR))

@bot.tree.command(name="youtube", description="▶️ Buscar en YouTube")
@app_commands.describe(busqueda="Qué quieres buscar")
async def cmd_youtube(interaction: discord.Interaction, busqueda: str):
    url = f"https://www.youtube.com/results?search_query={quote(busqueda)}"
    await interaction.response.send_message(embed=_e("Resultado de YouTube", f"[Buscar: {busqueda}]({url})"))

@bot.tree.command(name="google", description="🔍 Buscar en Google")
@app_commands.describe(busqueda="Qué quieres buscar")
async def cmd_google(interaction: discord.Interaction, busqueda: str):
    url = f"https://www.google.com/search?q={quote(busqueda)}"
    await interaction.response.send_message(embed=_e("Resultado de Google", f"[Buscar: {busqueda}]({url})"))

@bot.tree.command(name="translate", description="🌐 Traducir un texto")
@app_commands.describe(texto="Texto a traducir", idioma="Código de idioma destino (ej: en, es, fr)")
async def cmd_translate(interaction: discord.Interaction, texto: str, idioma: str = "en"):
    await interaction.response.defer()
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": texto, "langpair": f"auto|{idioma}"}, timeout=10).json()
        traduccion = r["responseData"]["translatedText"]
        await interaction.followup.send(embed=_e("Traducción", f"**Original:** {texto}\n**Traducido ({idioma}):** {traduccion}"))
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Error al traducir el texto.", C_ERROR))

@bot.tree.command(name="weather", description="⛅ Ver el clima de una ciudad")
@app_commands.describe(ciudad="Nombre de la ciudad")
async def cmd_weather(interaction: discord.Interaction, ciudad: str):
    await interaction.response.defer()
    try:
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": ciudad, "count": 1}, timeout=10).json()
        if not geo.get("results"):
            return await interaction.followup.send(embed=_e("Ciudad No Encontrada", "Verifica el nombre e intenta de nuevo.", C_WARN))
        loc = geo["results"][0]
        w = requests.get("https://api.open-meteo.com/v1/forecast", params={"latitude": loc["latitude"], "longitude": loc["longitude"], "current_weather": True}, timeout=10).json()
        cw = w.get("current_weather", {})
        e = _e(f"Clima en {loc['name']}", f"🌡️ Temperatura: `{cw.get('temperature')}°C`\n💨 Viento: `{cw.get('windspeed')} km/h`")
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send(embed=_e("Error", "Error al obtener el clima.", C_ERROR))


# ══════════════════════════════════════════════════════════════
#  ECONOMÍA
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="balance", description="💰 Ver tu saldo o el de otro usuario")
@app_commands.describe(usuario="Usuario a consultar")
async def cmd_balance(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    data = get_eco(u.id)
    await interaction.response.send_message(embed=_e(f"Saldo de {u.display_name}", f"`{data['bal']}` monedas."))

@bot.tree.command(name="daily", description="🎁 Reclamar tu recompensa diaria")
async def cmd_daily(interaction: discord.Interaction):
    data = get_eco(interaction.user.id)
    now = int(time.time())
    if now - data["daily"] < 86400:
        restante = 86400 - (now - data["daily"])
        return await interaction.response.send_message(embed=_e("Espera un Poco", f"Ya reclamaste tu daily. Vuelve en `{restante // 3600}h {(restante % 3600) // 60}m`.", C_WARN), ephemeral=True)
    data["bal"] += 100
    data["daily"] = now
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Recompensa Diaria", f"Recibiste `100` monedas. Saldo: `{data['bal']}`"))

@bot.tree.command(name="work", description="💼 Trabajar y ganar monedas")
async def cmd_work(interaction: discord.Interaction):
    data = get_eco(interaction.user.id)
    now = int(time.time())
    if now - data.get("work", 0) < 3600:
        restante = 3600 - (now - data.get("work", 0))
        return await interaction.response.send_message(embed=_e("Aún Cansado", f"Debes esperar `{restante // 60}m` para trabajar de nuevo.", C_WARN), ephemeral=True)
    earned = random.randint(20, 50)
    data["bal"] += earned
    data["work"] = now
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Trabajo Completado", f"Ganaste `{earned}` monedas."))

@bot.tree.command(name="beg", description="🙏 Pedir monedas (a veces funciona)")
async def cmd_beg(interaction: discord.Interaction):
    data = get_eco(interaction.user.id)
    if random.random() < 0.5:
        earned = random.randint(1, 30)
        data["bal"] += earned
        save_data("economy", economy_data)
        await interaction.response.send_message(embed=_e("¡Alguien te ayudó!", f"Recibiste `{earned}` monedas."))
    else:
        await interaction.response.send_message(embed=_e("Nadie te ayudó", "Intenta de nuevo más tarde.", C_WARN))

@bot.tree.command(name="pay", description="💸 Pagar a otro usuario")
@app_commands.describe(usuario="A quién pagar", cantidad="Cantidad de monedas")
async def cmd_pay(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        return await _send_error(interaction, "La cantidad debe ser mayor a 0.")
    if usuario.id == interaction.user.id:
        return await _send_error(interaction, "No puedes pagarte a ti mismo.")
    d1 = get_eco(interaction.user.id)
    d2 = get_eco(usuario.id)
    if d1["bal"] < cantidad:
        return await _send_error(interaction, "Saldo insuficiente.")
    d1["bal"] -= cantidad
    d2["bal"] += cantidad
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Pago Realizado", f"{interaction.user.mention} pagó `{cantidad}` monedas a {usuario.mention}."))

@bot.tree.command(name="rob", description="🥷 Intentar robar monedas a otro usuario")
@app_commands.describe(usuario="A quién robar")
async def cmd_rob(interaction: discord.Interaction, usuario: discord.Member):
    if usuario.id == interaction.user.id:
        return await _send_error(interaction, "No puedes robarte a ti mismo.")
    robber = get_eco(interaction.user.id)
    victim = get_eco(usuario.id)
    now = int(time.time())
    if now - robber.get("rob", 0) < 1800:
        restante = 1800 - (now - robber.get("rob", 0))
        return await interaction.response.send_message(embed=_e("Cuidado", f"Debes esperar `{restante // 60}m` para volver a robar.", C_WARN), ephemeral=True)
    robber["rob"] = now
    if victim["bal"] < 20:
        save_data("economy", economy_data)
        return await interaction.response.send_message(embed=_e("Robo Fallido", f"{usuario.mention} no tiene suficientes monedas para robar."))
    if random.random() < 0.5:
        cantidad = random.randint(10, min(100, victim["bal"]))
        victim["bal"] -= cantidad
        robber["bal"] += cantidad
        save_data("economy", economy_data)
        await interaction.response.send_message(embed=_e("¡Robo Exitoso!", f"Robaste `{cantidad}` monedas a {usuario.mention}."))
    else:
        multa = min(30, robber["bal"])
        robber["bal"] -= multa
        save_data("economy", economy_data)
        await interaction.response.send_message(embed=_e("Robo Fallido", f"Te atraparon y perdiste `{multa}` monedas.", C_ERROR))

@bot.tree.command(name="slots", description="🎰 Jugar a la tragamonedas")
@app_commands.describe(apuesta="Cantidad de monedas a apostar")
async def cmd_slots(interaction: discord.Interaction, apuesta: int):
    data = get_eco(interaction.user.id)
    if apuesta <= 0:
        return await _send_error(interaction, "La apuesta debe ser mayor a 0.")
    if data["bal"] < apuesta:
        return await _send_error(interaction, "Saldo insuficiente.")
    simbolos = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]
    resultado = [random.choice(simbolos) for _ in range(3)]
    linea = " | ".join(resultado)
    if resultado[0] == resultado[1] == resultado[2]:
        ganancia = apuesta * 5
        data["bal"] += ganancia
        desc = f"{linea}\n\n¡Jackpot! Ganaste `{ganancia}` monedas."
        color = C_GREEN
    elif len(set(resultado)) == 2:
        ganancia = apuesta * 2
        data["bal"] += ganancia
        desc = f"{linea}\n\nGanaste `{ganancia}` monedas."
        color = C_GREEN
    else:
        data["bal"] -= apuesta
        desc = f"{linea}\n\nPerdiste `{apuesta}` monedas."
        color = C_ERROR
    save_data("economy", economy_data)
    await interaction.response.send_message(embed=_e("Tragamonedas", desc, color))

@bot.tree.command(name="baltop", description="🏆 Top de usuarios más ricos del servidor")
async def cmd_baltop(interaction: discord.Interaction):
    ranked = sorted(economy_data.items(), key=lambda x: x[1]["bal"], reverse=True)[:10]
    if not ranked:
        return await interaction.response.send_message(embed=_e("Top de Riqueza", "No hay datos aún."))
    desc = ""
    for i, (uid, info) in enumerate(ranked, start=1):
        member = interaction.guild.get_member(int(uid)) if interaction.guild else None
        name = member.display_name if member else f"Usuario {uid}"
        desc += f"**{i}.** {name} — `{info['bal']}` monedas\n"
    await interaction.response.send_message(embed=_e("Top de Riqueza", desc))


# ══════════════════════════════════════════════════════════════
#  NIVELES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="rank", description="📈 Ver tu rango de nivel")
@app_commands.describe(usuario="Usuario a consultar")
async def cmd_rank(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    lvl = get_level(interaction.guild_id, u.id)
    needed = xp_needed(lvl["level"])
    await interaction.response.send_message(embed=_e(f"Rango de {u.display_name}", f"Nivel: `{lvl['level']}`\nXP: `{lvl['xp']}/{needed}`"))

@bot.tree.command(name="level", description="📊 Ver tu nivel actual")
@app_commands.describe(usuario="Usuario a consultar")
async def cmd_level(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    lvl = get_level(interaction.guild_id, u.id)
    await interaction.response.send_message(embed=_e(f"Nivel de {u.display_name}", f"Nivel: `{lvl['level']}`"))

@bot.tree.command(name="xptop", description="🏆 Tabla de líderes por XP del servidor")
async def cmd_xptop(interaction: discord.Interaction):
    gid = str(interaction.guild_id)
    data = levels_data.get(gid, {})
    ranked = sorted(data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    if not ranked:
        return await interaction.response.send_message(embed=_e("Tabla de Líderes", "No hay datos de niveles aún."))
    desc = ""
    for i, (uid, info) in enumerate(ranked, start=1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"Usuario {uid}"
        desc += f"**{i}.** {name} — Nivel `{info['level']}` (`{info['xp']}` XP)\n"
    await interaction.response.send_message(embed=_e("Tabla de Líderes", desc))

@bot.tree.command(name="setlevel", description="🔧 [Admin] Establecer el nivel de un usuario")
@app_commands.describe(usuario="Usuario", nivel="Nuevo nivel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlevel(interaction: discord.Interaction, usuario: discord.Member, nivel: int):
    lvl = get_level(interaction.guild_id, usuario.id)
    lvl["level"] = max(0, nivel)
    lvl["xp"] = 0
    save_data("levels", levels_data)
    await interaction.response.send_message(embed=_e("Nivel Establecido", f"{usuario.mention} ahora es nivel `{nivel}`."))
_perm_error_handler(cmd_setlevel)


# ══════════════════════════════════════════════════════════════
#  GIVEAWAYS
# ══════════════════════════════════════════════════════════════

class GiveawayView(View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        btn = Button(label="Participar", emoji="🎉", style=discord.ButtonStyle.success, custom_id=f"ga_join_{giveaway_id}")
        btn.callback = self.join_callback
        self.add_item(btn)

    async def join_callback(self, interaction: discord.Interaction):
        ga = giveaways_data.get(self.giveaway_id)
        if not ga or ga.get("ended"):
            return await interaction.response.send_message("❌ Este sorteo ya finalizó.", ephemeral=True)
        uid = str(interaction.user.id)
        if uid in ga["participants"]:
            ga["participants"].remove(uid)
            msg = "❌ Saliste del sorteo."
        else:
            ga["participants"].append(uid)
            msg = "🎉 ¡Ahora participas en el sorteo!"
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
    desc = f"Premio: **{ga['prize']}**\n"
    desc += f"Ganadores: {', '.join(f'<@{w}>' for w in winners)}" if winners else "Nadie participó."
    await channel.send(embed=_e("Sorteo Finalizado", desc))

@bot.tree.command(name="giveawaystart", description="🎉 [Admin] Crear un sorteo")
@app_commands.describe(premio="Premio del sorteo", minutos="Duración en minutos", ganadores="Cantidad de ganadores")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_giveawaystart(interaction: discord.Interaction, premio: str, minutos: int, ganadores: int = 1):
    giveaway_id = str(int(time.time() * 1000))
    end_ts = int(time.time()) + minutos * 60
    e = _e("¡Sorteo Activo!", f"Premio: **{premio}**\nGanadores: `{ganadores}`\nTermina: <t:{end_ts}:R>")
    view = GiveawayView(giveaway_id)
    await interaction.response.send_message(embed=e, view=view)
    giveaways_data[giveaway_id] = {
        "guild_id": interaction.guild_id, "prize": premio, "winners": ganadores,
        "participants": [], "end_ts": end_ts, "ended": False, "host": str(interaction.user.id),
    }
    save_data("giveaways", giveaways_data)

    async def auto_end():
        await asyncio.sleep(minutos * 60)
        await _end_giveaway(giveaway_id, interaction.channel)

    asyncio.create_task(auto_end())
_perm_error_handler(cmd_giveawaystart)

@bot.tree.command(name="giveawayend", description="🏁 [Admin] Terminar un sorteo manualmente")
@app_commands.describe(giveaway_id="ID del sorteo")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_giveawayend(interaction: discord.Interaction, giveaway_id: str):
    if giveaway_id not in giveaways_data:
        return await _send_error(interaction, "Sorteo no encontrado.")
    await interaction.response.send_message(embed=_e("Finalizando", "Procesando sorteo..."), ephemeral=True)
    await _end_giveaway(giveaway_id, interaction.channel)
_perm_error_handler(cmd_giveawayend)

@bot.tree.command(name="giveawayreroll", description="🔁 [Admin] Elegir un nuevo ganador")
@app_commands.describe(giveaway_id="ID del sorteo")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_giveawayreroll(interaction: discord.Interaction, giveaway_id: str):
    ga = giveaways_data.get(giveaway_id)
    if not ga:
        return await _send_error(interaction, "Sorteo no encontrado.")
    if not ga["participants"]:
        return await _send_error(interaction, "No hay participantes para el reroll.")
    winner = random.choice(ga["participants"])
    await interaction.response.send_message(embed=_e("Nuevo Ganador", f"🎉 El nuevo ganador es <@{winner}>!"))
_perm_error_handler(cmd_giveawayreroll)


# ══════════════════════════════════════════════════════════════
#  TICKETS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="ticketopen", description="🎫 Abrir un ticket de soporte")
async def cmd_ticketopen(interaction: discord.Interaction):
    guild = interaction.guild
    name = f"ticket-{interaction.user.name}".lower()[:90]
    if discord.utils.get(guild.text_channels, name=name):
        return await _send_error(interaction, "Ya tienes un ticket abierto.")
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    ch = await guild.create_text_channel(name, overwrites=overwrites)
    await interaction.response.send_message(embed=_e("Ticket Creado", f"Tu ticket: {ch.mention}"), ephemeral=True)
    await ch.send(f"{interaction.user.mention}", embed=_e("Ticket de Soporte", "Describe tu problema. Un staff te atenderá pronto."))

@bot.tree.command(name="ticketclose", description="🔒 Cerrar el ticket actual")
async def cmd_ticketclose(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await _send_error(interaction, "Este canal no es un ticket.")
    await interaction.response.send_message(embed=_e("Cerrando Ticket", "Este ticket se cerrará en 5 segundos..."))
    await asyncio.sleep(5)
    await interaction.channel.delete()


# ══════════════════════════════════════════════════════════════
#  ROLES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="addrole", description="➕ [Admin] Añadir un rol a un usuario")
@app_commands.describe(usuario="Usuario", rol="Rol a añadir")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_addrole(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    try:
        await usuario.add_roles(rol)
        await interaction.response.send_message(embed=_e("Rol Añadido", f"{rol.mention} fue añadido a {usuario.mention}."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_addrole)

@bot.tree.command(name="removerole", description="➖ [Admin] Quitar un rol a un usuario")
@app_commands.describe(usuario="Usuario", rol="Rol a quitar")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_removerole(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    try:
        await usuario.remove_roles(rol)
        await interaction.response.send_message(embed=_e("Rol Removido", f"{rol.mention} fue removido de {usuario.mention}."))
    except Exception as ex:
        await _send_error(interaction, f"```\n{str(ex)[:200]}\n```")
_perm_error_handler(cmd_removerole)

@bot.tree.command(name="autorole", description="🎭 [Admin] Configurar el rol automático para nuevos miembros")
@app_commands.describe(rol="Rol a asignar automáticamente")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_autorole(interaction: discord.Interaction, rol: discord.Role):
    cfg = get_config(interaction.guild_id)
    cfg["autorole"] = rol.id
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Autorol Configurado", f"Nuevos miembros recibirán: {rol.mention}"))
_perm_error_handler(cmd_autorole)


# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="setwelcome", description="👋 [Admin] Configurar el canal de bienvenida")
@app_commands.describe(canal="Canal de bienvenida")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setwelcome(interaction: discord.Interaction, canal: discord.TextChannel):
    cfg = get_config(interaction.guild_id)
    cfg["welcome_channel"] = canal.id
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Bienvenida Configurada", f"Canal establecido: {canal.mention}"))
_perm_error_handler(cmd_setwelcome)

@bot.tree.command(name="setlogs", description="📜 [Admin] Configurar el canal de logs")
@app_commands.describe(canal="Canal de logs")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlogs(interaction: discord.Interaction, canal: discord.TextChannel):
    cfg = get_config(interaction.guild_id)
    cfg["log_channel"] = canal.id
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Logs Configurados", f"Canal establecido: {canal.mention}"))
_perm_error_handler(cmd_setlogs)

@bot.tree.command(name="setprefix", description="🔤 [Admin] Configurar el prefijo del bot")
@app_commands.describe(prefijo="Nuevo prefijo")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setprefix(interaction: discord.Interaction, prefijo: str):
    cfg = get_config(interaction.guild_id)
    cfg["prefix"] = prefijo
    save_data("configs", configs_data)
    await interaction.response.send_message(embed=_e("Prefijo Configurado", f"Nuevo prefijo: `{prefijo}`"))
_perm_error_handler(cmd_setprefix)

@bot.tree.command(name="settings", description="⚙️ Ver la configuración actual del servidor")
async def cmd_settings(interaction: discord.Interaction):
    cfg = get_config(interaction.guild_id)
    e = _e("Configuración del Servidor")
    e.add_field(name="Canal Bienvenida", value=f"<#{cfg['welcome_channel']}>" if cfg.get("welcome_channel") else "`No configurado`", inline=False)
    e.add_field(name="Canal Logs", value=f"<#{cfg['log_channel']}>" if cfg.get("log_channel") else "`No configurado`", inline=False)
    e.add_field(name="Autorol", value=f"<@&{cfg['autorole']}>" if cfg.get("autorole") else "`No configurado`", inline=False)
    e.add_field(name="Prefijo", value=f"`{cfg.get('prefix', '!')}`", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)


# ══════════════════════════════════════════════════════════════
#  INFORMACIÓN DEL BOT
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="botinfo", description="🤖 Información general del bot")
async def cmd_botinfo(interaction: discord.Interaction):
    e = _e("FMD BOT", "Bot multifuncional con sistema de bypass premium.")
    e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="Latencia", value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.add_field(name="Uptime", value=f"`{_uptime()}`", inline=True)
    e.add_field(name="Comandos", value=f"`{len(bot.tree.get_commands())}`", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="invite", description="🔗 Invita al bot a tu servidor")
async def cmd_invite(interaction: discord.Interaction):
    await interaction.response.send_message(embed=_e("Invitar al Bot", f"[Haz clic aquí para invitarme]({BOT_INVITE_URL})"))

@bot.tree.command(name="uptime", description="⏱️ Ver el tiempo activo del bot")
async def cmd_uptime(interaction: discord.Interaction):
    await interaction.response.send_message(embed=_e("Uptime", f"`{_uptime()}`"))

@bot.tree.command(name="support", description="🆘 Enlace al servidor de soporte")
async def cmd_support(interaction: discord.Interaction):
    await interaction.response.send_message(embed=_e("Servidor de Soporte", f"[Únete aquí]({SUPPORT_SERVER_URL})"))


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
