import { Router } from "express";
import { requireAuth } from "../middlewares/auth";
import { db } from "@workspace/db";
import { commandsTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { UpdateCommandParams, UpdateCommandBody } from "@workspace/api-zod";

const router = Router();

const SEED_COMMANDS = [
  { name: "help", description: "Show all available commands", category: "General", enabled: true, usageCount: 1523, permissions: "@everyone" },
  { name: "ping", description: "Check bot latency", category: "General", enabled: true, usageCount: 892, permissions: "@everyone" },
  { name: "stats", description: "Show bot statistics", category: "General", enabled: true, usageCount: 634, permissions: "@everyone" },
  { name: "ban", description: "Ban a user from the server", category: "Moderation", enabled: true, usageCount: 217, permissions: "ADMINISTRATOR" },
  { name: "kick", description: "Kick a user from the server", category: "Moderation", enabled: true, usageCount: 143, permissions: "KICK_MEMBERS" },
  { name: "mute", description: "Mute a user", category: "Moderation", enabled: true, usageCount: 398, permissions: "MUTE_MEMBERS" },
  { name: "warn", description: "Warn a user", category: "Moderation", enabled: true, usageCount: 712, permissions: "KICK_MEMBERS" },
  { name: "play", description: "Play a song from YouTube", category: "Music", enabled: true, usageCount: 2891, permissions: "@everyone" },
  { name: "skip", description: "Skip the current song", category: "Music", enabled: true, usageCount: 1034, permissions: "@everyone" },
  { name: "queue", description: "Show the music queue", category: "Music", enabled: true, usageCount: 876, permissions: "@everyone" },
  { name: "announce", description: "Send an announcement", category: "Admin", enabled: true, usageCount: 45, permissions: "ADMINISTRATOR" },
  { name: "purge", description: "Delete multiple messages", category: "Moderation", enabled: false, usageCount: 89, permissions: "MANAGE_MESSAGES" },
  { name: "userinfo", description: "Get information about a user", category: "Info", enabled: true, usageCount: 456, permissions: "@everyone" },
  { name: "serverinfo", description: "Get information about the server", category: "Info", enabled: true, usageCount: 321, permissions: "@everyone" },
  { name: "avatar", description: "Show user avatar", category: "Info", enabled: true, usageCount: 678, permissions: "@everyone" },
];

async function ensureSeeded() {
  const count = await db.$count(commandsTable);
  if (count === 0) {
    await db.insert(commandsTable).values(SEED_COMMANDS).onConflictDoNothing();
  }
}

router.get("/commands", requireAuth, async (req, res): Promise<void> => {
  await ensureSeeded();
  const commands = await db.select().from(commandsTable);
  res.json(
    commands.map((c) => ({
      name: c.name,
      description: c.description,
      category: c.category,
      enabled: c.enabled,
      usageCount: c.usageCount,
      permissions: c.permissions,
    }))
  );
});

router.patch("/commands/:name", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params["name"]) ? req.params["name"][0] : req.params["name"];
  const paramParsed = UpdateCommandParams.safeParse({ name: raw });
  if (!paramParsed.success) { res.status(400).json({ error: "Invalid command name" }); return; }

  const bodyParsed = UpdateCommandBody.safeParse(req.body);
  if (!bodyParsed.success) { res.status(400).json({ error: bodyParsed.error.message }); return; }

  await ensureSeeded();
  const [updated] = await db
    .update(commandsTable)
    .set({ enabled: bodyParsed.data.enabled })
    .where(eq(commandsTable.name, paramParsed.data.name))
    .returning();

  if (!updated) { res.status(404).json({ error: "Command not found" }); return; }

  res.json({
    name: updated.name,
    description: updated.description,
    category: updated.category,
    enabled: updated.enabled,
    usageCount: updated.usageCount,
    permissions: updated.permissions,
  });
});

export default router;
