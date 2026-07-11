"""
KOD BOT — Executor Tracker · Bypass Engine · Groq IA
Render Web Service compatible (binds PORT for health check).
"""
import os
import re
import json
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
from discord.ext import tasks
import aiohttp
import requests

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ══════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════
logger = logging.getLogger("KodBot")
logger.setLevel(logging.INFO)
_fh = RotatingFileHandler("bot.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
_ch = logging.StreamHandler()
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_fh.setFormatter(_fmt)
_ch.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_ch)

# ══════════════════════════════════════════════════════════════════
#  ENV CONFIG
# ══════════════════════════════════════════════════════════════════
DISCORD_TOKEN  = os.environ.get("DISCORD_TOKEN", "")
OWNER_ID       = int(os.environ.get("OWNER_ID", "0"))
PORT           = int(os.environ.get("PORT", "8080"))
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL     = "llama3-8b-8192"

BOT_NAME           = "KOD BOT"
BOT_CREDIT         = "By king"
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525040833814855710")

# ── Bypass ──────────────────────────────────────────────────────
BYPASS_API_URL   = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT   = 30
BYPASS_RETRIES   = 3
BYPASS_DELAY     = 3
BYPASS_BANNER    = "https://cdn.discordapp.com/attachments/1509409338354303157/1525397585458888855/ezgif-2225e2913bbda08b.gif"
BYPASS_FOOTER    = "KING"

# ── WEAO ─────────────────────────────────────────────────────────
WEAO_API         = "https://api.weao.xyz/v1/exploits"
CHECK_INTERVAL   = 90   # seconds

# ── Files ────────────────────────────────────────────────────────
CONFIG_FILE    = "config.json"
STATE_FILE     = "estado_anterior.json"
AUTOBYPASS_FILE = "autobypass_channels.json"
IA_CHANNELS_FILE = "ia_channels.json"

# ── Colors ───────────────────────────────────────────────────────
C_BYPASS  = 0x00D9FF
C_SUCCESS = 0x57F287
C_ERROR   = 0xED4245
C_WARN    = 0xFEE75C
C_INFO    = 0x5865F2

# ── Emojis / assets ──────────────────────────────────────────────
EMOJI_SUCCESS = "<:greendot:1525383175889485848>"
EMOJI_KEY     = "<:goldenkey:1525381310200414310>"
EMOJI_CLOCK   = "<a:clock:1525380296852377711>"
EMOJI_COPY    = "<:copy:1525379105111932958>"
EMOJI_LINK    = "<:link:1525379856034959422>"
GIF_LOADING   = "https://media.tenor.com/wpSo-8CrXqUAAAAi/loading-loading-forever.gif"
GIF_ERROR     = "https://media.tenor.com/0LF_JKlnPsgAAAAi/error-warning.gif"
DOT_GREEN     = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
DOT_RED       = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"

# ── Default exploit list ──────────────────────────────────────────
DEFAULT_EXPLOITS = [
    "Solara","Wave","AWP","Vega X","Delta","Hydrogen","Fluxus",
    "Electron","Nihon","Celestial","Velocity","Oxygen U","Comet",
    "Zypher","Krnl","Synapse X","Script-Ware","Evon","JJSploit",
    "Coco","Zen","Borealis","Sirius","Xeno","Rise","Valyse",
    "Elysian","Novus","Vynixius","Seliware","Exoliner","Neo",
    "Trigon","Eclipse","Arceus X","Mystic","Aurora","Nexus",
    "Quantum","Phantom","Carbon","Skrypt","Vortex","Genesis",
]

BOT_START = datetime.now(timezone.utc)

# ══════════════════════════════════════════════════════════════════
#  JSON HELPERS
# ══════════════════════════════════════════════════════════════════

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"save_json({path}): {e}")

# ── In-memory state ───────────────────────────────────────────────
autobypass_channels: set = set(load_json(AUTOBYPASS_FILE, []))
ia_channels:         set = set(load_json(IA_CHANNELS_FILE, []))

def _save_ab(): save_json(AUTOBYPASS_FILE, list(autobypass_channels))
def _save_ia(): save_json(IA_CHANNELS_FILE, list(ia_channels))

# ══════════════════════════════════════════════════════════════════
#  MISC HELPERS
# ══════════════════════════════════════════════════════════════════
_URL_RE = re.compile(r"https?://[^\s<>\"']{6,}")

def _is_url(u: str) -> bool:
    return bool(re.match(r"^https?://\S{6,}", u))

def _footer(extra: str = "") -> str:
    b = f"{BOT_NAME} • {BOT_CREDIT}"
    return f"{b} • {extra}" if extra else b

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START
    t = int(d.total_seconds())
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _status_emoji(s: str) -> str:
    s = (s or "").lower()
    if s == "online":  return "🟢"
    if s == "patched": return "🔴"
    return "🟡"

def _bypass_emoji(v) -> str:
    return "✅" if v else "❌"

# ══════════════════════════════════════════════════════════════════
#  BYPASS ENGINE  (4PI API)
# ══════════════════════════════════════════════════════════════════
_RESULT_KEYS = (
    "content","result","loadstring","bypassed","bypassed_link",
    "bypassed_url","final_url","destination","url","link","key","output"
)
_http = requests.Session()
_http.headers.update({"User-Agent": "KodBot/3.0"})

def _extract(data) -> str | None:
    if isinstance(data, dict):
        for k in _RESULT_KEYS:
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

def _bypass_sync(url: str) -> tuple[str | None, str | None]:
    """Runs synchronously — call via run_in_executor."""
    last_err = "Error desconocido"
    for attempt in range(1, BYPASS_RETRIES + 1):
        try:
            full = BYPASS_API_URL + quote(url, safe="")
            resp = _http.get(full, timeout=BYPASS_TIMEOUT)
            if resp.status_code in (502, 503, 504):
                last_err = f"4PI sobrecargada (HTTP {resp.status_code})"
                if attempt < BYPASS_RETRIES:
                    time.sleep(BYPASS_DELAY)
                    continue
                return None, last_err
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                if attempt < BYPASS_RETRIES:
                    time.sleep(BYPASS_DELAY)
                    continue
                return None, last_err
            # Try JSON first
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"):
                    return txt, None
                last_err = "Respuesta no válida de 4PI"
                if attempt < BYPASS_RETRIES:
                    time.sleep(BYPASS_DELAY)
                    continue
                return None, last_err
            # Check API error flags
            api_error = False
            if isinstance(data, dict):
                if (data.get("success") is False
                        or data.get("error")
                        or str(data.get("status", "")).lower() == "error"):
                    api_error = True
            result = _extract(data)
            if result and not api_error:
                return result, None
            if api_error:
                msg = None
                if isinstance(data, dict):
                    msg = data.get("message") or data.get("error")
                last_err = str(msg or "4PI reportó un error")
                if attempt < BYPASS_RETRIES:
                    time.sleep(BYPASS_DELAY)
                    continue
                return None, last_err
            return None, "No se encontró resultado en la respuesta"
        except requests.exceptions.Timeout:
            last_err = f"Timeout ({BYPASS_TIMEOUT}s)"
            if attempt < BYPASS_RETRIES:
                time.sleep(BYPASS_DELAY)
                continue
        except requests.exceptions.ConnectionError as ex:
            last_err = f"Error de conexión: {str(ex)[:80]}"
            if attempt < BYPASS_RETRIES:
                time.sleep(BYPASS_DELAY)
                continue
        except Exception as ex:
            last_err = str(ex)[:120]
            if attempt < BYPASS_RETRIES:
                time.sleep(BYPASS_DELAY)
                continue
    return None, last_err

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

def _bypass_result_embed(result: str, elapsed: float) -> discord.Embed:
    embed = discord.Embed(color=0x00FF00, timestamp=datetime.now(timezone.utc))
    embed.description = f"{EMOJI_SUCCESS} **KOD BYPASS • Success**"
    embed.add_field(name=f"{EMOJI_KEY} Result:",      value=f"```txt\n{result[:1000]}\n```", inline=False)
    embed.add_field(name=f"{EMOJI_CLOCK} Velocidad:", value=f"`{elapsed:.2f}s`",             inline=False)
    if BYPASS_BANNER:
        embed.set_image(url=BYPASS_BANNER)
    embed.set_footer(text=f"Made by: {BYPASS_FOOTER} • {_ts()}")
    return embed

class BypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._r = result
        self.add_item(Button(label="Add Bot",  emoji=EMOJI_LINK, url=BOT_INVITE_URL,     style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Soporte",  emoji=EMOJI_LINK, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="Copy", emoji=EMOJI_COPY, style=discord.ButtonStyle.secondary, row=0)
    async def copy_btn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(f"```txt\n{self._r[:1000]}\n```", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  GROQ AI
# ══════════════════════════════════════════════════════════════════
_groq = AsyncGroq(api_key=GROQ_API_KEY) if (AsyncGroq and GROQ_API_KEY) else None

async def ask_groq(prompt: str, system: str = "Eres KOD BOT, un asistente de Discord amigable. Responde siempre en español de forma clara y concisa.") -> str:
    if not _groq:
        return "❌ **GROQ_API_KEY** no está configurada. Agrégala como variable de entorno en Render."
    try:
        resp = await _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"system","content":system},{"role":"user","content":prompt[:4000]}],
            max_tokens=800, temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as ex:
        logger.error(f"[Groq] {ex}")
        return f"❌ Error con Groq: `{str(ex)[:200]}`"

# ══════════════════════════════════════════════════════════════════
#  WEAO (executor data)
# ══════════════════════════════════════════════════════════════════

async def fetch_exploits() -> dict:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(WEAO_API, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    raw  = await r.json(content_type=None)
                    lst  = raw if isinstance(raw, list) else raw.get("exploits", raw.get("data", []))
                    return {item.get("name","").lower(): item for item in lst if item.get("name")}
    except Exception as ex:
        logger.warning(f"[WEAO] {ex}")
    return {}

def get_exploit(data: dict, name: str):
    return data.get(name.lower())

# ══════════════════════════════════════════════════════════════════
#  BOT CLIENT
# ══════════════════════════════════════════════════════════════════

class KodBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Slash commands sincronizados")

    async def on_ready(self):
        logger.info(f"✅ {self.user} online | {len(self.guilds)} servidor(es)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name="/help • KOD BOT"))
        if not exploit_check.is_running():
            exploit_check.start()

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        # Auto-bypass
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(_auto_bypass(message, urls))
                return
        # Auto-IA
        if message.channel.id in ia_channels and message.content.strip():
            asyncio.create_task(_auto_ia(message))

bot = KodBot()

# ══════════════════════════════════════════════════════════════════
#  AUTO-BYPASS HANDLER
# ══════════════════════════════════════════════════════════════════

async def _auto_bypass(message: discord.Message, urls: list):
    try:
        await message.delete()
    except Exception:
        pass
    loop = asyncio.get_running_loop()
    for url in urls[:3]:
        if not _is_url(url):
            continue
        loading_e = discord.Embed(
            title="[ Procesando ] KOD BYPASS",
            description="```fix\nConectando...\nEsto puede tardar segundos.\n```",
            color=C_WARN, timestamp=datetime.now(timezone.utc))
        loading_e.set_thumbnail(url=GIF_LOADING)
        loading_e.set_footer(text=_footer())
        msg = None
        try:
            msg = await message.channel.send(content=message.author.mention, embed=loading_e)
        except Exception:
            continue
        t0 = time.time()
        result, error = await loop.run_in_executor(None, _bypass_sync, url)
        elapsed = time.time() - t0
        try:
            if result:
                await msg.edit(content=message.author.mention,
                               embed=_bypass_result_embed(result, elapsed),
                               view=BypassView(result))
            else:
                err_e = discord.Embed(
                    title="[ Fallido ] Bypass",
                    description=f"```diff\n- {error}\n```",
                    color=C_ERROR, timestamp=datetime.now(timezone.utc))
                err_e.set_thumbnail(url=GIF_ERROR)
                err_e.set_footer(text=_footer())
                await msg.edit(content=message.author.mention, embed=err_e)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════
#  AUTO-IA HANDLER
# ══════════════════════════════════════════════════════════════════

async def _auto_ia(message: discord.Message):
    async with message.channel.typing():
        reply = await ask_groq(message.content)
    e = discord.Embed(description=reply[:2000], color=C_INFO, timestamp=datetime.now(timezone.utc))
    e.set_author(name="KOD BOT IA", icon_url=bot.user.display_avatar.url if bot.user else None)
    e.set_footer(text=_footer("Groq • llama3-8b"))
    try:
        await message.reply(embed=e, mention_author=False)
    except Exception as ex:
        logger.error(f"[auto_ia] {ex}")

# ══════════════════════════════════════════════════════════════════
#  EXPLOIT CHECK TASK
# ══════════════════════════════════════════════════════════════════

@tasks.loop(seconds=CHECK_INTERVAL)
async def exploit_check():
    config   = load_json(CONFIG_FILE, {})
    previous = load_json(STATE_FILE, {})
    api_data = await fetch_exploits()
    if not api_data:
        logger.warning("[exploit_check] API vacía o sin respuesta")
        return
    changed = False
    for guild_id, gcfg in config.items():
        if not gcfg.get("enabled"):
            continue
        ch_id = gcfg.get("channel_id")
        if not ch_id or ch_id == "none":
            continue
        guild = bot.get_guild(int(guild_id))
        if not guild:
            continue
        channel = guild.get_channel(int(ch_id))
        if not channel:
            continue
        role_id        = gcfg.get("role_id")
        exploits_list  = gcfg.get("exploits", DEFAULT_EXPLOITS)
        for exp_name in exploits_list:
            info = get_exploit(api_data, exp_name)
            if not info:
                continue
            real     = info.get("name", exp_name)
            key      = f"{guild_id}_{real.lower()}"
            cur_st   = info.get("status", "Unknown")
            cur_ver  = info.get("version", "N/A")
            prev     = previous.get(key, {})
            prev_st  = prev.get("status")
            prev_ver = prev.get("version")
            previous[key] = {"status": cur_st, "version": cur_ver}
            changed = True
            # Skip if nothing changed
            if prev_st == cur_st and prev_ver == cur_ver:
                continue
            # Build alert embed
            is_on   = cur_st.lower() == "online"
            color   = C_SUCCESS if is_on else (C_ERROR if cur_st.lower() == "patched" else C_WARN)
            platform = info.get("platform", "N/A")
            updated  = info.get("updated_at", info.get("last_updated", "N/A"))
            dl       = info.get("download", info.get("download_link", info.get("link", None)))
            embed = discord.Embed(
                title=f"🎉 Actualización — {real}",
                color=color, timestamp=datetime.now(timezone.utc))
            if prev_st and prev_st != cur_st:
                embed.add_field(name="🔄 Estado",  value=f"`{prev_st}` → `{cur_st}`",   inline=False)
            if prev_ver and prev_ver != cur_ver:
                embed.add_field(name="📦 Versión", value=f"`{prev_ver}` → `{cur_ver}`", inline=False)
            embed.add_field(name="Estado actual",  value=f"{_status_emoji(cur_st)} {cur_st}", inline=True)
            embed.add_field(name="Versión",        value=cur_ver,                             inline=True)
            embed.add_field(name="Plataforma",     value=platform,                            inline=True)
            embed.add_field(name="Última act.",    value=str(updated),                        inline=False)
            if dl:
                embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl})",         inline=False)
            embed.set_thumbnail(url=DOT_GREEN if is_on else DOT_RED)
            embed.set_footer(text="Datos: api.weao.xyz")
            mention = "@everyone"
            if role_id:
                role = guild.get_role(int(role_id))
                if role:
                    mention = role.mention
            try:
                await channel.send(content=mention, embed=embed)
                logger.info(f"[alert] {real}: {prev_st}→{cur_st} en {guild.name}")
            except discord.Forbidden:
                logger.warning(f"[alert] Sin permisos en {guild.name}#{channel.name}")
            except Exception as ex:
                logger.error(f"[alert] {ex}")
    if changed:
        save_json(STATE_FILE, previous)

@exploit_check.before_loop
async def _before_check():
    await bot.wait_until_ready()
    await asyncio.sleep(15)   # small delay after ready before first check

# ══════════════════════════════════════════════════════════════════
#  SETUP VIEW (executor alert config)
# ══════════════════════════════════════════════════════════════════

class SetupView(discord.ui.View):
    def __init__(self, guild: discord.Guild, cfg: dict):
        super().__init__(timeout=180)
        self.guild = guild
        self.cfg   = cfg.copy()
        # Channel select
        txt_chs = [c for c in guild.channels if isinstance(c, discord.TextChannel)][:25]
        ch_opts = [discord.SelectOption(label=f"#{c.name}", value=str(c.id),
                    default=(str(c.id) == str(cfg.get("channel_id","")))) for c in txt_chs]
        if not ch_opts:
            ch_opts = [discord.SelectOption(label="Sin canales", value="none")]
        ch_sel = discord.ui.Select(placeholder="📢 Canal de alertas", options=ch_opts, custom_id="ch", row=0)
        ch_sel.callback = self._ch_cb
        self.add_item(ch_sel)
        # Role select
        roles = [r for r in guild.roles if r.name != "@everyone"][:24]
        r_opts = [discord.SelectOption(label="@everyone (sin mención)", value="none",
                   default=not cfg.get("role_id"))]
        r_opts += [discord.SelectOption(label=f"@{r.name}", value=str(r.id),
                    default=(str(r.id)==str(cfg.get("role_id","")))) for r in roles]
        r_sel = discord.ui.Select(placeholder="👥 Rol a mencionar", options=r_opts[:25], custom_id="role", row=1)
        r_sel.callback = self._role_cb
        self.add_item(r_sel)

    async def _ch_cb(self, i: discord.Interaction):
        self.cfg["channel_id"] = i.data["values"][0]
        await i.response.defer()

    async def _role_cb(self, i: discord.Interaction):
        v = i.data["values"][0]
        self.cfg["role_id"] = None if v == "none" else v
        await i.response.defer()

    @discord.ui.button(label="✅ Activar alertas",    style=discord.ButtonStyle.success, row=2)
    async def enable(self, i: discord.Interaction, _):
        self.cfg["enabled"] = True
        await i.response.send_message("✅ Alertas activadas.", ephemeral=True)

    @discord.ui.button(label="🔕 Desactivar alertas", style=discord.ButtonStyle.danger,  row=2)
    async def disable(self, i: discord.Interaction, _):
        self.cfg["enabled"] = False
        await i.response.send_message("🔕 Alertas desactivadas.", ephemeral=True)

    @discord.ui.button(label="💾 Guardar", style=discord.ButtonStyle.primary, row=3)
    async def save(self, i: discord.Interaction, _):
        cfg = load_json(CONFIG_FILE, {})
        gid = str(self.guild.id)
        cfg.setdefault(gid, {}).update(self.cfg)
        cfg[gid].setdefault("exploits", DEFAULT_EXPLOITS)
        save_json(CONFIG_FILE, cfg)
        ch_id   = self.cfg.get("channel_id")
        role_id = self.cfg.get("role_id")
        enabled = self.cfg.get("enabled", False)
        ch   = self.guild.get_channel(int(ch_id))  if ch_id  and ch_id  != "none" else None
        role = self.guild.get_role(int(role_id))    if role_id else None
        embed = discord.Embed(title="✅ Configuración Guardada", color=C_SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="📢 Canal",    value=ch.mention   if ch   else "No configurado", inline=True)
        embed.add_field(name="👥 Rol",     value=role.mention if role else "@everyone",       inline=True)
        embed.add_field(name="🔔 Alertas", value="✅ Activas"  if enabled else "🔕 Desactivadas", inline=True)
        await i.response.edit_message(embed=embed, view=None)
        self.stop()

# ══════════════════════════════════════════════════════════════════
#  SLASH — BYPASS
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="bypass", description="🔓 Bypass un enlace y obtén el destino real")
@app_commands.describe(url="El enlace a bypasear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_url(url):
        return await interaction.response.send_message(
            embed=discord.Embed(description="⚠️ URL inválida. Usa un enlace `http://` o `https://`.", color=C_WARN),
            ephemeral=True)
    loading_e = discord.Embed(
        title="[ Procesando ] KOD BYPASS",
        description="```fix\nConectando con el servidor...\nEsto puede tardar segundos.\n```",
        color=C_WARN, timestamp=datetime.now(timezone.utc))
    loading_e.set_author(name="KOD BYPASS Engine", icon_url=bot.user.display_avatar.url if bot.user else None)
    loading_e.set_thumbnail(url=GIF_LOADING)
    loading_e.set_footer(text=_footer(f"Solicitado por {interaction.user.name}"))
    await interaction.response.send_message(embed=loading_e)
    t0 = time.time()
    loop = asyncio.get_running_loop()
    result, error = await loop.run_in_executor(None, _bypass_sync, url)
    elapsed = time.time() - t0
    if result:
        await interaction.edit_original_response(embed=_bypass_result_embed(result, elapsed), view=BypassView(result))
        logger.info(f"[bypass] ✅ {interaction.user} → {url[:60]}")
    else:
        err_e = discord.Embed(
            title="[ Fallido ] KOD BYPASS",
            description=f"```diff\n- {error or 'Error desconocido'}\n```",
            color=C_ERROR, timestamp=datetime.now(timezone.utc))
        err_e.set_author(name="KOD BYPASS Engine", icon_url=bot.user.display_avatar.url if bot.user else None)
        err_e.add_field(name="Enlace probado", value=f"```{url[:300]}```", inline=False)
        err_e.add_field(name="Tiempo",         value=f"`{int(elapsed*1000)}ms`", inline=True)
        err_e.set_thumbnail(url=GIF_ERROR)
        err_e.set_footer(text=_footer())
        v = View()
        v.add_item(Button(label="Soporte", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
        await interaction.edit_original_response(embed=err_e, view=v)
        logger.info(f"[bypass] ❌ {interaction.user} → {url[:60]} | {error}")


@bot.tree.command(name="setautobypass", description="⚙️ [Admin] Activar/desactivar auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        _save_ab()
        e = discord.Embed(title="🔴 Auto-Bypass DESACTIVADO",
                          description=f"{interaction.channel.mention} ya no bypaseará automáticamente.",
                          color=C_ERROR)
    else:
        autobypass_channels.add(cid)
        _save_ab()
        e = discord.Embed(title="🟢 Auto-Bypass ACTIVADO",
                          description=f"Cada enlace enviado en {interaction.channel.mention} será bypaseado automáticamente.",
                          color=C_SUCCESS)
    e.set_footer(text=_footer(f"Canales activos: {len(autobypass_channels)}"))
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ae(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso de **Administrador**.", ephemeral=True)

# ── bypass-info group ────────────────────────────────────────────
bypass_group = app_commands.Group(name="bypass-info", description="Información de bypass de exploits vía WEAO")

@bypass_group.command(name="check", description="Verifica el estado de bypass de un exploit")
@app_commands.describe(exploit="Nombre del exploit")
async def bi_check(interaction: discord.Interaction, exploit: str):
    await interaction.response.defer()
    data = await fetch_exploits()
    info = get_exploit(data, exploit)
    if not info:
        return await interaction.followup.send(f"❌ No se encontró **{exploit}**.", ephemeral=True)
    nombre  = info.get("name", exploit)
    estado  = info.get("status", "Unknown")
    version = info.get("version", "N/A")
    plat    = info.get("platform", "N/A")
    dl      = info.get("download", info.get("download_link", info.get("link", None)))
    is_on   = estado.lower() == "online"
    byfron  = info.get("byfron_bypass",  info.get("bypass",     is_on))
    hyp     = info.get("hyperion_bypass", info.get("anti_cheat", is_on))
    luau    = info.get("luau_support",    True)
    color   = C_SUCCESS if is_on else C_ERROR
    embed = discord.Embed(title=f"🛡️ Bypass Info — {nombre}", color=color, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Estado",          value=f"{_status_emoji(estado)} {estado}", inline=True)
    embed.add_field(name="Versión",         value=version,                              inline=True)
    embed.add_field(name="Plataforma",      value=plat,                                 inline=True)
    embed.add_field(name="Byfron Bypass",   value=_bypass_emoji(byfron),                inline=True)
    embed.add_field(name="Hyperion Bypass", value=_bypass_emoji(hyp),                   inline=True)
    embed.add_field(name="LuaU Support",    value=_bypass_emoji(luau),                  inline=True)
    if dl:
        embed.add_field(name="🔗 Descarga", value=f"[Descargar]({dl})", inline=False)
    embed.set_thumbnail(url=DOT_GREEN if is_on else DOT_RED)
    embed.set_footer(text="Datos: api.weao.xyz")
    await interaction.followup.send(embed=embed)

@bypass_group.command(name="working", description="Lista exploits con bypass activo ahora mismo")
async def bi_working(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await fetch_exploits()
    cfg  = load_json(CONFIG_FILE, {})
    lst  = cfg.get(str(interaction.guild_id), {}).get("exploits", DEFAULT_EXPLOITS)
    working = []
    for name in lst:
        info = get_exploit(data, name)
        if info and info.get("status","").lower() == "online":
            v = info.get("version","N/A")
            p = info.get("platform","N/A")
            working.append(f"🟢 **{info.get('name',name)}** — v`{v}` | {p}")
    if not working:
        embed = discord.Embed(title="🛡️ Exploits Working",
                              description="⚠️ Ningún exploit está online en este momento.",
                              color=C_ERROR, timestamp=datetime.now(timezone.utc))
    else:
        desc = "\n".join(working)
        embed = discord.Embed(title=f"🛡️ Exploits Working ({len(working)})",
                              description=desc[:4000], color=C_SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"{len(working)}/{len(lst)} exploits online • api.weao.xyz")
    await interaction.followup.send(embed=embed)

@bypass_group.command(name="compare", description="Compara el bypass de dos exploits")
@app_commands.describe(exploit1="Primer exploit", exploit2="Segundo exploit")
async def bi_compare(interaction: discord.Interaction, exploit1: str, exploit2: str):
    await interaction.response.defer()
    data = await fetch_exploits()
    def _fields(info, name) -> dict:
        if not info:
            return {"name":name,"estado":"N/A","ver":"N/A","byfron":False,"hyp":False,"luau":False}
        st = info.get("status","Unknown")
        on = st.lower()=="online"
        return {"name":info.get("name",name),"estado":st,"ver":info.get("version","N/A"),
                "byfron":info.get("byfron_bypass",on),"hyp":info.get("hyperion_bypass",on),"luau":info.get("luau_support",True)}
    d1 = _fields(get_exploit(data,exploit1), exploit1)
    d2 = _fields(get_exploit(data,exploit2), exploit2)
    embed = discord.Embed(title="⚔️ Comparación de Bypass", color=0x9B59B6, timestamp=datetime.now(timezone.utc))
    for d, icon in [(d1,"🔹"),(d2,"🔸")]:
        embed.add_field(name=f"{icon} {d['name']}",
                        value=(f"{_status_emoji(d['estado'])} {d['estado']}\n"
                               f"Version: `{d['ver']}`\n"
                               f"Byfron: {_bypass_emoji(d['byfron'])}\n"
                               f"Hyperion: {_bypass_emoji(d['hyp'])}\n"
                               f"LuaU: {_bypass_emoji(d['luau'])}"), inline=True)
    embed.set_footer(text="Datos: api.weao.xyz")
    await interaction.followup.send(embed=embed)

bot.tree.add_command(bypass_group)

# ══════════════════════════════════════════════════════════════════
#  SLASH — EXECUTOR TRACKER
# ══════════════════════════════════════════════════════════════════

executors_group = app_commands.Group(name="executors", description="Estado de exploits de Roblox vía WEAO")

@executors_group.command(name="stat", description="Estado de un exploit o de todos")
@app_commands.describe(nombre="Nombre del exploit (deja vacío para ver todos)")
async def ex_stat(interaction: discord.Interaction, nombre: str = None):
    await interaction.response.defer()
    data = await fetch_exploits()
    cfg  = load_json(CONFIG_FILE, {})
    lst  = cfg.get(str(interaction.guild_id), {}).get("exploits", DEFAULT_EXPLOITS)

    if not nombre:
        # All exploits
        lines = []
        for n in lst:
            info = get_exploit(data, n)
            if info:
                st = info.get("status","?")
                lines.append(f"{_status_emoji(st)} **{info.get('name',n)}** — {st}")
            else:
                lines.append(f"⚪ **{n}** — Sin datos de API")
        # Split into 4096-char chunks
        chunk, chunks = [], []
        for line in lines:
            chunk.append(line)
            if len("\n".join(chunk)) > 3800:
                chunks.append("\n".join(chunk[:-1]))
                chunk = [line]
        chunks.append("\n".join(chunk))
        embed = discord.Embed(title="📋 Estado de Exploits",
                              description=chunks[0] or "Sin datos.", color=C_INFO, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Total: {len(lst)} • WEAO API")
        await interaction.followup.send(embed=embed)
        for extra in chunks[1:]:
            await interaction.followup.send(embed=discord.Embed(description=extra, color=C_INFO))
        return

    info = get_exploit(data, nombre)
    if not info:
        return await interaction.followup.send(f"❌ No se encontró **{nombre}**. Verifica el nombre exacto.", ephemeral=True)
    estado   = info.get("status","Unknown")
    version  = info.get("version","N/A")
    platform = info.get("platform","N/A")
    updated  = info.get("updated_at", info.get("last_updated","N/A"))
    dl       = info.get("download", info.get("download_link", info.get("link",None)))
    is_on    = estado.lower() == "online"
    color    = C_SUCCESS if is_on else (C_ERROR if estado.lower()=="patched" else C_WARN)
    embed = discord.Embed(title=f"{_status_emoji(estado)} {info.get('name',nombre)}",
                          color=color, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Estado",    value=estado,   inline=True)
    embed.add_field(name="Versión",   value=version,  inline=True)
    embed.add_field(name="Plataforma",value=platform, inline=True)
    embed.add_field(name="Actualizado", value=str(updated), inline=False)
    if dl:
        embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl})", inline=False)
    embed.set_thumbnail(url=DOT_GREEN if is_on else DOT_RED)
    embed.set_footer(text="Datos: api.weao.xyz")
    await interaction.followup.send(embed=embed)

bot.tree.add_command(executors_group)


@bot.tree.command(name="supported", description="Lista de exploits vigilados en este servidor")
async def cmd_supported(interaction: discord.Interaction):
    cfg = load_json(CONFIG_FILE, {})
    lst = cfg.get(str(interaction.guild_id),{}).get("exploits", DEFAULT_EXPLOITS)
    text = "\n".join(f"• {e}" for e in lst)
    embed = discord.Embed(title="📋 Exploits Vigilados",
                          description=text[:4000] if text else "Sin exploits configurados.",
                          color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=_footer(f"Total: {len(lst)}"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="set", description="⚙️ Configura las alertas automáticas de exploits")
@app_commands.default_permissions(manage_guild=True)
async def cmd_set(interaction: discord.Interaction):
    cfg  = load_json(CONFIG_FILE, {})
    gcfg = cfg.get(str(interaction.guild_id), {})
    ch_v = f"<#{gcfg['channel_id']}>"  if gcfg.get("channel_id") else "No configurado"
    rl_v = f"<@&{gcfg['role_id']}>"   if gcfg.get("role_id")    else "@everyone"
    en_v = "✅ Activas" if gcfg.get("enabled") else "🔕 Desactivadas"
    embed = discord.Embed(title="⚙️ Configurar Alertas de Exploits",
                          description="Usa los menús para configurar y luego presiona **Guardar**.",
                          color=C_INFO)
    embed.add_field(name="Configuración actual",
                    value=f"Canal: {ch_v}\nRol: {rl_v}\nAlertas: {en_v}", inline=False)
    await interaction.response.send_message(embed=embed, view=SetupView(interaction.guild, gcfg), ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH — IA (Groq)
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="ai-chat", description="🤖 Chatea con la IA (Groq llama3)")
@app_commands.describe(mensaje="Tu mensaje")
async def cmd_ai_chat(interaction: discord.Interaction, mensaje: str):
    await interaction.response.defer()
    reply = await ask_groq(mensaje)
    embed = discord.Embed(title="〔 🤖 〕 KOD BOT IA", color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="💬 Tu mensaje", value=f"```{mensaje[:500]}```", inline=False)
    embed.add_field(name="🤖 Respuesta",  value=reply[:1000],             inline=False)
    embed.set_footer(text=_footer("Groq • llama3-8b"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="ask-ai", description="❓ Hazle una pregunta a la IA")
@app_commands.describe(pregunta="Tu pregunta")
async def cmd_ask_ai(interaction: discord.Interaction, pregunta: str):
    await interaction.response.defer()
    reply = await ask_groq(pregunta, system="Eres un asistente experto. Responde de forma precisa y concisa en español.")
    embed = discord.Embed(title="〔 ❓ 〕 Respuesta IA",
                          description=reply[:2000], color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=_footer(f"Pregunta de {interaction.user.name}"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="translate-text", description="🌐 Traduce texto a cualquier idioma")
@app_commands.describe(texto="Texto a traducir", idioma="Idioma destino (ej: inglés, francés, japonés)")
async def cmd_translate(interaction: discord.Interaction, texto: str, idioma: str = "inglés"):
    await interaction.response.defer()
    result = await ask_groq(texto, system=f"Eres un traductor experto. Traduce exactamente al {idioma} sin añadir comentarios ni explicaciones.")
    embed = discord.Embed(title="〔 🌐 〕 Traducción", color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="📝 Original",          value=f"```{texto[:400]}```",  inline=False)
    embed.add_field(name=f"🌐 {idioma.title()}", value=f"```{result[:400]}```", inline=False)
    embed.set_footer(text=_footer("Groq • llama3-8b"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="summarize-text", description="📋 Resume un texto largo")
@app_commands.describe(texto="Texto a resumir")
async def cmd_summarize(interaction: discord.Interaction, texto: str):
    await interaction.response.defer()
    result = await ask_groq(texto, system="Eres un experto en resúmenes. Resume en bullet points claros y concisos en español.")
    embed = discord.Embed(title="〔 📋 〕 Resumen IA", color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="📝 Resumen", value=result[:1900], inline=False)
    embed.set_footer(text=_footer(f"Original: {len(texto)} chars"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="set-ia-channel", description="🤖 [Admin] Activar/desactivar IA automática en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_set_ia(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in ia_channels:
        ia_channels.discard(cid)
        _save_ia()
        embed = discord.Embed(title="🔴 Canal IA Desactivado",
                              description=f"{interaction.channel.mention} ya no responderá con IA.", color=C_ERROR)
    else:
        ia_channels.add(cid)
        _save_ia()
        embed = discord.Embed(title="🟢 Canal IA Activado",
                              description=f"{interaction.channel.mention} responderá con IA a cada mensaje.\n"
                                          f"```yaml\nModelo : llama3-8b-8192\nCanales activos : {len(ia_channels)}\n```",
                              color=C_SUCCESS)
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@cmd_set_ia.error
async def _sia_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas permiso de **Administrador**.", ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  SLASH — UTILIDAD BÁSICA
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="ping", description="🏓 Latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms    = round(bot.latency * 1000)
    color = C_SUCCESS if ms < 100 else (C_WARN if ms < 200 else C_ERROR)
    e = discord.Embed(title="🏓 Pong!", description=f"Latencia: **`{ms}ms`**", color=color)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="info", description="🤖 Información del bot")
async def cmd_info(interaction: discord.Interaction):
    e = discord.Embed(title="🤖 KOD BOT — Info", color=C_INFO, timestamp=datetime.now(timezone.utc))
    e.add_field(name="👑 Creador",    value="`KING`",               inline=True)
    e.add_field(name="📚 Librería",   value="`discord.py 2.3`",     inline=True)
    e.add_field(name="🌐 Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="📡 Latencia",   value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.add_field(name="⏱️ Uptime",     value=f"`{_uptime()}`",        inline=True)
    e.add_field(name="🔄 Executor check", value=f"Cada `{CHECK_INTERVAL}s`", inline=True)
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
    e.set_footer(text=_footer())
    v = View()
    v.add_item(Button(label="Soporte", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, emoji="💬"))
    await interaction.response.send_message(embed=e, view=v)


@bot.tree.command(name="help", description="📖 Lista de comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(title="📖 KOD BOT — Comandos", color=C_BYPASS, timestamp=datetime.now(timezone.utc))
    e.add_field(name="🔓 Bypass",
                value=("`/bypass <url>` — Bypassear enlace\n"
                       "`/setautobypass` — Toggle auto-bypass en canal *(Admin)*\n"
                       "`/bypass-info check <exploit>` — Bypass de exploit\n"
                       "`/bypass-info working` — Exploits online\n"
                       "`/bypass-info compare <e1> <e2>` — Comparar exploits"),
                inline=False)
    e.add_field(name="🎮 Executor Tracker",
                value=("`/executors stat [nombre]` — Estado de exploit(s)\n"
                       "`/supported` — Exploits vigilados\n"
                       "`/set` — Configurar alertas automáticas *(Manage Server)*"),
                inline=False)
    e.add_field(name="🤖 IA (Groq)",
                value=("`/ai-chat <mensaje>` — Chat con IA\n"
                       "`/ask-ai <pregunta>` — Pregunta a la IA\n"
                       "`/translate-text <texto> <idioma>` — Traducir\n"
                       "`/summarize-text <texto>` — Resumir\n"
                       "`/set-ia-channel` — Toggle IA automática en canal *(Admin)*"),
                inline=False)
    e.add_field(name="📊 Utilidad",
                value="`/ping` `/info` `/help`",
                inline=False)
    e.set_footer(text=_footer())
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
    v = View()
    v.add_item(Button(label="Servidor de Soporte", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, emoji="💬"))
    await interaction.response.send_message(embed=e, view=v)

# ══════════════════════════════════════════════════════════════════
#  WEB SERVER — Render health check (binds to PORT)
# ══════════════════════════════════════════════════════════════════

async def _health(request):
    return aiohttp.web.Response(
        text='{"status":"ok","bot":"KOD BOT"}',
        content_type="application/json", status=200)

async def start_web():
    app = aiohttp.web.Application()
    app.router.add_get("/",       _health)
    app.router.add_get("/health", _health)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Health server en puerto {PORT}")

# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado. Agrégalo como variable de entorno.")
        return
    if not GROQ_API_KEY:
        logger.warning("⚠️  GROQ_API_KEY no encontrado. Comandos de IA no funcionarán.")
    await start_web()
    logger.info("🚀 Iniciando KOD BOT...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
