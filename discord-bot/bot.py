"""
FMD BOT — Bypass + Executor Alerts
"""
import sys, types

try:
    import audioop
except ImportError:
    sys.modules["audioop"] = types.ModuleType("audioop")

import os, re, json, time, asyncio, logging, threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
from discord.ext import tasks
import requests

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
BOT_CREDIT = "BY KING"

BYPASS_API_URL = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT = 30
BYPASS_RETRIES = 3
BYPASS_DELAY   = 3

WEAO_API       = "https://api.weao.xyz/v1/exploits"
CHECK_INTERVAL = 90

CONFIG_FILE     = "config.json"
STATE_FILE      = "estado_anterior.json"
AUTOBYPASS_FILE = "autobypass_channels.json"

# ── COLORES ──────────────────────────────────────────────────────
C_MAIN    = 0xB026FF
C_SUCCESS = 0x57F287
C_ERROR   = 0xED4245
C_WARN    = 0xFEE75C
C_INFO    = 0x5865F2

# ── TUS IMÁGENES ─────────────────────────────────────────────────
IMG_MAIN    = "https://cdn.discordapp.com/attachments/1525556800579965058/1525566942281465876/ezgif-35ed139046075f14_1.gif?ex=6a53da6e&is=6a5288ee&hm=1f2c78e97d4a8d8ef46a52d25480674f993989ed7729172febf795a6ecc32bd6&"
EMOJI_GREEN = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
EMOJI_OK    = "https://cdn.discordapp.com/emojis/1525379448768303207.webp?size=100&animated=true"
EMOJI_LINK  = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"

GIF_LOADING = "https://media.tenor.com/wpSo-8CrXqUAAAAi/loading-loading-forever.gif"

DEFAULT_EXPLOITS = [
    "Solara","Wave","AWP","Vega X","Delta","Hydrogen","Fluxus",
    "Electron","Nihon","Celestial","Velocity","Oxygen U","Comet",
    "Zypher","Krnl","Synapse X","Script-Ware","Evon","JJSploit",
    "Coco","Zen","Borealis","Sirius","Xeno","Rise","Valyse",
    "Elysian","Novus","Vynixius","Seliware","Exoliner","Neo",
    "Trigon","Eclipse","Arceus X","Aurora","Nexus","Carbon",
]

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

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

def _status_e(s: str) -> str:
    s = (s or "").lower()
    if s == "online":  return "🟢"
    if s == "patched": return "🔴"
    return "🟡"

# ── BYPASS ───────────────────────────────────────────────────────
_KEYS = ("content","result","loadstring","bypassed","bypassed_link",
         "bypassed_url","final_url","destination","url","link","key","output")
_http = requests.Session()
_http.headers.update({"User-Agent": "FMD-Bot/1.0"})

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
            if resp.status_code not in (200,):
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

# ── EMBEDS ───────────────────────────────────────────────────────

def embed_bypass_ok(result: str, elapsed: float, url: str) -> discord.Embed:
    e = discord.Embed(color=C_SUCCESS, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
    e.set_thumbnail(url=EMOJI_OK)
    e.add_field(name="🔗 URL",       value=f"```\n{url[:200]}\n```",        inline=False)
    e.add_field(name="✅ RESURTADO", value=f"```\n{result[:900]}\n```",      inline=False)
    e.add_field(name="⏱️ Tiempo",    value=f"`{elapsed:.2f}s`",              inline=True)
    e.add_field(name="📅 Fecha",     value=f"`{_ts()}`",                     inline=True)
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    return e

def embed_bypass_fail(error: str, url: str, elapsed: float) -> discord.Embed:
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_LINK)
    e.add_field(name="🔗 URL",    value=f"```\n{url[:200]}\n```",   inline=False)
    e.add_field(name="❌ Error",  value=f"```\n{error or '?'}\n```", inline=False)
    e.add_field(name="⏱️ Tiempo", value=f"`{int(elapsed*1000)}ms`", inline=True)
    e.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    return e

# ── VIEWS ────────────────────────────────────────────────────────

class BypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._r = result
        self.add_item(Button(label="Soporte",     emoji="💬", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Invitar Bot", emoji="🤖", url=BOT_INVITE_URL,     style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="📋 Copiar RESURTADO", style=discord.ButtonStyle.success, row=1)
    async def copy_btn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            content=f"```\n{self._r[:1800]}\n```", ephemeral=True)

class ErrorView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Soporte", emoji="💬", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))

# ── WEAO ─────────────────────────────────────────────────────────

def _weao_sync() -> dict:
    try:
        resp = _http.get(WEAO_API, timeout=15)
        if resp.status_code == 200:
            raw = resp.json()
            lst = raw if isinstance(raw, list) else raw.get("exploits", raw.get("data", []))
            return {item.get("name","").lower(): item for item in lst if item.get("name")}
    except Exception as ex:
        logger.warning(f"[WEAO] {ex}")
    return {}

async def fetch_exploits() -> dict:
    return await asyncio.get_running_loop().run_in_executor(None, _weao_sync)

# ── BOT ──────────────────────────────────────────────────────────

class FMDBot(discord.Client):
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
        if not exploit_check.is_running():
            exploit_check.start()

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(_auto_bypass(message, urls))

bot = FMDBot()

# ── AUTO-BYPASS ───────────────────────────────────────────────────

async def _auto_bypass(message: discord.Message, urls: list):
    try: await message.delete()
    except Exception: pass
    loop = asyncio.get_running_loop()
    for url in urls[:3]:
        if not _is_url(url): continue
        loading = discord.Embed(
            description="```\nProcesando bypass...\n```",
            color=C_WARN, timestamp=datetime.now(timezone.utc))
        loading.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
        loading.set_thumbnail(url=GIF_LOADING)
        loading.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
        try: msg = await message.channel.send(content=message.author.mention, embed=loading)
        except Exception: continue
        t0 = time.time()
        result, error = await loop.run_in_executor(None, _bypass_sync, url)
        elapsed = time.time() - t0
        try:
            if result:
                await msg.edit(content=message.author.mention,
                               embed=embed_bypass_ok(result, elapsed, url), view=BypassView(result))
            else:
                await msg.edit(content=message.author.mention,
                               embed=embed_bypass_fail(error, url, elapsed), view=ErrorView())
        except Exception: pass

# ── EXECUTOR ALERTS ───────────────────────────────────────────────

@tasks.loop(seconds=CHECK_INTERVAL)
async def exploit_check():
    config   = load_json(CONFIG_FILE, {})
    previous = load_json(STATE_FILE, {})
    api_data = await fetch_exploits()
    if not api_data: return
    changed = False
    for guild_id, gcfg in config.items():
        if not gcfg.get("enabled"): continue
        ch_id = gcfg.get("channel_id")
        if not ch_id or ch_id == "none": continue
        guild = bot.get_guild(int(guild_id))
        if not guild: continue
        channel = guild.get_channel(int(ch_id))
        if not channel: continue
        role_id = gcfg.get("role_id")
        for exp_name in gcfg.get("exploits", DEFAULT_EXPLOITS):
            info = api_data.get(exp_name.lower())
            if not info: continue
            real    = info.get("name", exp_name)
            key     = f"{guild_id}_{real.lower()}"
            cur_st  = info.get("status", "Unknown")
            cur_ver = info.get("version", "N/A")
            prev    = previous.get(key, {})
            previous[key] = {"status": cur_st, "version": cur_ver}
            changed = True
            if prev.get("status") == cur_st and prev.get("version") == cur_ver: continue
            is_on = cur_st.lower() == "online"
            color = C_SUCCESS if is_on else (C_ERROR if cur_st.lower()=="patched" else C_WARN)
            dl    = info.get("download", info.get("download_link", info.get("link", None)))
            embed = discord.Embed(
                title=f"{_status_e(cur_st)}  {real}",
                color=color, timestamp=datetime.now(timezone.utc))
            embed.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}",
                             icon_url=EMOJI_GREEN if is_on else EMOJI_LINK)
            embed.set_thumbnail(url=EMOJI_OK if is_on else EMOJI_LINK)
            if prev.get("status") and prev["status"] != cur_st:
                embed.add_field(name="Estado",  value=f"`{prev['status']}` → **{cur_st}**", inline=True)
            if prev.get("version") and prev["version"] != cur_ver:
                embed.add_field(name="Versión", value=f"`{prev['version']}` → `{cur_ver}`", inline=True)
            embed.add_field(name="Versión actual", value=f"`{cur_ver}`",              inline=True)
            if dl:
                embed.add_field(name="Descarga", value=f"[⬇️ Descargar]({dl})",      inline=False)
            embed.set_image(url=IMG_MAIN)
            embed.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
            mention = "@everyone"
            if role_id:
                role = guild.get_role(int(role_id))
                if role: mention = role.mention
            try:
                await channel.send(content=mention, embed=embed)
            except Exception as ex:
                logger.error(f"[alert] {ex}")
    if changed: save_json(STATE_FILE, previous)

@exploit_check.before_loop
async def _before():
    await bot.wait_until_ready()
    await asyncio.sleep(15)

# ── SETUP VIEW ────────────────────────────────────────────────────

class SetupView(discord.ui.View):
    def __init__(self, guild, cfg):
        super().__init__(timeout=180)
        self.guild = guild
        self.cfg   = cfg.copy()
        txt_chs = [c for c in guild.channels if isinstance(c, discord.TextChannel)][:25]
        ch_opts = [discord.SelectOption(label=f"#{c.name}", value=str(c.id),
                    default=(str(c.id)==str(cfg.get("channel_id","")))) for c in txt_chs] \
                  or [discord.SelectOption(label="Sin canales", value="none")]
        chs = discord.ui.Select(placeholder="Canal de alertas", options=ch_opts, row=0)
        chs.callback = self._ch
        self.add_item(chs)
        roles = [r for r in guild.roles if r.name != "@everyone"][:24]
        r_opts = [discord.SelectOption(label="@everyone", value="none", default=not cfg.get("role_id"))]
        r_opts += [discord.SelectOption(label=f"@{r.name}", value=str(r.id),
                    default=(str(r.id)==str(cfg.get("role_id","")))) for r in roles]
        rs = discord.ui.Select(placeholder="Rol a mencionar", options=r_opts[:25], row=1)
        rs.callback = self._role
        self.add_item(rs)

    async def _ch(self, i):
        self.cfg["channel_id"] = i.data["values"][0]
        await i.response.defer()

    async def _role(self, i):
        v = i.data["values"][0]
        self.cfg["role_id"] = None if v == "none" else v
        await i.response.defer()

    @discord.ui.button(label="✅ Activar",    style=discord.ButtonStyle.success, row=2)
    async def _on(self, i, _):
        self.cfg["enabled"] = True
        await i.response.send_message("✅ Alertas activadas.", ephemeral=True)

    @discord.ui.button(label="🔕 Desactivar", style=discord.ButtonStyle.danger, row=2)
    async def _off(self, i, _):
        self.cfg["enabled"] = False
        await i.response.send_message("🔕 Alertas desactivadas.", ephemeral=True)

    @discord.ui.button(label="💾 Guardar", style=discord.ButtonStyle.primary, row=3)
    async def _save(self, i, _):
        cfg = load_json(CONFIG_FILE, {})
        gid = str(self.guild.id)
        cfg.setdefault(gid, {}).update(self.cfg)
        cfg[gid].setdefault("exploits", DEFAULT_EXPLOITS)
        save_json(CONFIG_FILE, cfg)
        ch   = self.guild.get_channel(int(self.cfg["channel_id"])) \
               if self.cfg.get("channel_id","") not in ("none","") else None
        role = self.guild.get_role(int(self.cfg["role_id"])) if self.cfg.get("role_id") else None
        e = discord.Embed(title="✅ Guardado", color=C_SUCCESS)
        e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_OK)
        e.add_field(name="Canal",   value=ch.mention   if ch   else "No configurado", inline=True)
        e.add_field(name="Rol",     value=role.mention if role else "@everyone",       inline=True)
        e.add_field(name="Alertas", value="✅ Activas" if self.cfg.get("enabled") else "🔕 Off", inline=True)
        await i.response.edit_message(embed=e, view=None)
        self.stop()

# ── COMANDOS ──────────────────────────────────────────────────────

@bot.tree.command(name="bypass", description="Bypassea un enlace")
@app_commands.describe(url="Enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_url(url):
        return await interaction.response.send_message(
            embed=discord.Embed(description="URL inválida.", color=C_ERROR), ephemeral=True)
    loading = discord.Embed(
        description="```\nProcesando bypass...\n```",
        color=C_WARN, timestamp=datetime.now(timezone.utc))
    loading.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
    loading.set_thumbnail(url=GIF_LOADING)
    loading.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    await interaction.response.send_message(embed=loading)
    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, _bypass_sync, url)
    elapsed = time.time() - t0
    if result:
        await interaction.edit_original_response(
            embed=embed_bypass_ok(result, elapsed, url), view=BypassView(result))
    else:
        await interaction.edit_original_response(
            embed=embed_bypass_fail(error, url, elapsed), view=ErrorView())


@bot.tree.command(name="setautobypass", description="Activa o desactiva el auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid); _save_ab()
        e = discord.Embed(
            description=f"Auto-bypass **desactivado** en {interaction.channel.mention}.",
            color=C_ERROR)
    else:
        autobypass_channels.add(cid); _save_ab()
        e = discord.Embed(
            description=f"Auto-bypass **activado** en {interaction.channel.mention}.\nLos enlaces se bypasean automáticamente.",
            color=C_SUCCESS)
    e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
    e.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ae(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("Necesitas permisos de **Administrador**.", ephemeral=True)


@bot.tree.command(name="set", description="Configura las alertas automáticas de executors")
@app_commands.default_permissions(manage_guild=True)
async def cmd_set(interaction: discord.Interaction):
    cfg  = load_json(CONFIG_FILE, {})
    gcfg = cfg.get(str(interaction.guild_id), {})
    ch_v = f"<#{gcfg['channel_id']}>" if gcfg.get("channel_id") else "No configurado"
    rl_v = f"<@&{gcfg['role_id']}>"   if gcfg.get("role_id")    else "@everyone"
    en_v = "✅ Activas" if gcfg.get("enabled") else "🔕 Desactivadas"
    e = discord.Embed(
        description=f"**Canal:** {ch_v}\n**Rol:** {rl_v}\n**Alertas:** {en_v}",
        color=C_MAIN)
    e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    await interaction.response.send_message(embed=e, view=SetupView(interaction.guild, gcfg), ephemeral=True)


@bot.tree.command(name="ping", description="Ver latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    color = C_SUCCESS if ms < 100 else (C_WARN if ms < 200 else C_ERROR)
    e = discord.Embed(color=color)
    e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
    e.add_field(name="📡 Latencia",   value=f"`{ms}ms`",             inline=True)
    e.add_field(name="⏱️ Uptime",     value=f"`{_uptime()}`",        inline=True)
    e.add_field(name="🌐 Servidores", value=f"`{len(bot.guilds)}`",   inline=True)
    e.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="help", description="Ver todos los comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(color=C_MAIN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} • {BOT_CREDIT}", icon_url=EMOJI_GREEN)
    e.set_thumbnail(url=EMOJI_OK)
    e.add_field(
        name="🔓 Bypass",
        value=("`/bypass <url>` — Bypassea un enlace\n"
               "`/setautobypass` — Toggle auto-bypass en canal *(Admin)*"),
        inline=False)
    e.add_field(
        name="🔔 Executor Alerts",
        value="`/set` — Configurar canal y rol de alertas *(Manage Server)*",
        inline=False)
    e.add_field(
        name="📊 Utilidad",
        value="`/ping` — Latencia del bot\n`/help` — Esta lista",
        inline=False)
    e.set_image(url=IMG_MAIN)
    e.set_footer(text=f"{BOT_NAME} • {BOT_CREDIT}")
    v = View()
    v.add_item(Button(label="Soporte",     emoji="💬", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
    v.add_item(Button(label="Invitar Bot", emoji="🤖", url=BOT_INVITE_URL,     style=discord.ButtonStyle.link))
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
