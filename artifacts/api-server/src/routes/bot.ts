import { Router } from "express";
import os from "os";
import { requireAuth } from "../middlewares/auth";
import { db } from "@workspace/db";
import { botSettingsTable, logsTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import {
  UpdateBotSettingsBody,
  SendAnnouncementBody,
} from "@workspace/api-zod";

const router = Router();

router.get("/bot/stats", requireAuth, async (req, res): Promise<void> => {
  const cpuUsage = os.loadavg()[0] * 10; // rough percentage
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;

  // Try to ping Discord API for latency
  let latency = 0;
  let discordApiStatus: "operational" | "degraded" | "outage" = "operational";
  try {
    const start = Date.now();
    const r = await fetch("https://discord.com/api/v10/gateway", { signal: AbortSignal.timeout(5000) });
    latency = Date.now() - start;
    if (!r.ok) discordApiStatus = "degraded";
  } catch {
    discordApiStatus = "outage";
    latency = 9999;
  }

  // Try to get real bot data if token is set
  const token = process.env["DISCORD_BOT_TOKEN"];
  let guildCount = 0;
  let userCount = 0;
  let channelCount = 0;
  let botStatus: "online" | "offline" | "idle" | "dnd" = "offline";

  if (token) {
    try {
      const data = await (
        await fetch("https://discord.com/api/v10/applications/@me", {
          headers: { Authorization: `Bot ${token}` },
        })
      ).json() as { approximate_guild_count?: number };
      guildCount = data.approximate_guild_count ?? 0;
      botStatus = "online";
    } catch {
      botStatus = "offline";
    }
  } else {
    // Demo values when no token configured
    guildCount = 42;
    userCount = 15823;
    channelCount = 387;
    botStatus = "online";
  }

  res.json({
    status: botStatus,
    uptime: Math.floor(process.uptime()),
    latency,
    guildCount,
    userCount,
    channelCount,
    cpuUsage: Math.min(parseFloat(cpuUsage.toFixed(1)), 100),
    ramUsage: parseFloat((usedMem / 1024 / 1024 / 1024).toFixed(2)),
    ramTotal: parseFloat((totalMem / 1024 / 1024 / 1024).toFixed(2)),
    pythonVersion: "3.11.x",
    discordApiStatus,
  });
});

router.get("/bot/settings", requireAuth, async (req, res): Promise<void> => {
  let [settings] = await db.select().from(botSettingsTable).where(eq(botSettingsTable.id, 1));
  if (!settings) {
    [settings] = await db
      .insert(botSettingsTable)
      .values({ id: 1, maintenanceMode: false, statusText: "FMD BOT | /help", statusType: "playing", disabledCommands: [] })
      .onConflictDoNothing()
      .returning();
    if (!settings) {
      [settings] = await db.select().from(botSettingsTable).where(eq(botSettingsTable.id, 1));
    }
  }
  res.json({
    maintenanceMode: settings!.maintenanceMode,
    statusText: settings!.statusText,
    statusType: settings!.statusType,
    disabledCommands: settings!.disabledCommands ?? [],
  });
});

router.patch("/bot/settings", requireAuth, async (req, res): Promise<void> => {
  const parsed = UpdateBotSettingsBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const updates: Record<string, unknown> = {};
  if (parsed.data.maintenanceMode !== undefined) updates["maintenanceMode"] = parsed.data.maintenanceMode;
  if (parsed.data.statusText !== undefined) updates["statusText"] = parsed.data.statusText;
  if (parsed.data.statusType !== undefined) updates["statusType"] = parsed.data.statusType;

  // Ensure row exists
  await db
    .insert(botSettingsTable)
    .values({ id: 1, maintenanceMode: false, statusText: "FMD BOT | /help", statusType: "playing", disabledCommands: [] })
    .onConflictDoNothing();

  const [updated] = await db
    .update(botSettingsTable)
    .set({ ...updates, updatedAt: new Date() })
    .where(eq(botSettingsTable.id, 1))
    .returning();

  res.json({
    maintenanceMode: updated!.maintenanceMode,
    statusText: updated!.statusText,
    statusType: updated!.statusType,
    disabledCommands: updated!.disabledCommands ?? [],
  });
});

router.post("/bot/restart", requireAuth, async (req, res): Promise<void> => {
  await db.insert(logsTable).values({
    type: "api",
    message: "Bot restart signaled from dashboard",
    guildId: null,
    userId: (req.session as { userId?: string }).userId ?? "owner",
    metadata: null,
  });
  req.log.info("Bot restart signaled");
  res.json({ success: true, message: "Restart signal sent to bot" });
});

router.post("/bot/announcement", requireAuth, async (req, res): Promise<void> => {
  const parsed = SendAnnouncementBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  await db.insert(logsTable).values({
    type: "api",
    message: `Announcement sent: ${parsed.data.message}`,
    guildId: parsed.data.targetGuildId ?? null,
    userId: (req.session as { userId?: string }).userId ?? "owner",
    metadata: JSON.stringify({ announcement: parsed.data.message }),
  });
  res.json({ success: true, message: "Announcement queued" });
});

export default router;
