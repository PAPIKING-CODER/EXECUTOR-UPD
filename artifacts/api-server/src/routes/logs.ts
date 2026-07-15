import { Router } from "express";
import { requireAuth } from "../middlewares/auth";
import { db } from "@workspace/db";
import { logsTable } from "@workspace/db";
import { desc, gte, lte, and, type SQL } from "drizzle-orm";
import { ListLogsQueryParams, CreateLogBody } from "@workspace/api-zod";

const router = Router();

const SEED_LOGS = [
  { type: "command", message: "User 123 used /help in #general", guildId: "123456789012345678", userId: "111111111111111111", metadata: null },
  { type: "join", message: "Bot joined server Anime Central", guildId: "234567890123456789", userId: null, metadata: null },
  { type: "command", message: "User 456 used /play in #music", guildId: "456789012345678901", userId: "222222222222222222", metadata: null },
  { type: "error", message: "Command /ban failed: Missing permissions", guildId: "345678901234567890", userId: "333333333333333333", metadata: null },
  { type: "moderation", message: "User 789 was banned from FMD Gaming Community", guildId: "123456789012345678", userId: "444444444444444444", metadata: null },
  { type: "api", message: "Discord API rate limit hit on endpoint /channels/{id}/messages", guildId: null, userId: null, metadata: null },
  { type: "command", message: "User 321 used /stats in #bot-commands", guildId: "567890123456789012", userId: "555555555555555555", metadata: null },
  { type: "leave", message: "Bot left server Tech Talk (kicked)", guildId: "345678901234567890", userId: null, metadata: null },
];

async function ensureSeeded() {
  const count = await db.$count(logsTable);
  if (count === 0) {
    await db.insert(logsTable).values(SEED_LOGS);
  }
}

router.get("/logs", requireAuth, async (req, res): Promise<void> => {
  const parsed = ListLogsQueryParams.safeParse(req.query);
  const params = parsed.success ? parsed.data : { page: 1, limit: 50 };
  const page = params.page ?? 1;
  const limit = Math.min(params.limit ?? 50, 100);

  await ensureSeeded();

  let all = await db.select().from(logsTable).orderBy(desc(logsTable.createdAt));

  if (params.type) all = all.filter((l) => l.type === params.type);
  if (params.search) all = all.filter((l) => l.message.toLowerCase().includes((params.search ?? "").toLowerCase()));
  if (params.dateFrom) all = all.filter((l) => l.createdAt >= new Date(params.dateFrom!));
  if (params.dateTo) all = all.filter((l) => l.createdAt <= new Date(params.dateTo!));

  const total = all.length;
  const offset = (page - 1) * limit;
  const logs = all.slice(offset, offset + limit).map((l) => ({
    id: l.id,
    type: l.type as "command" | "error" | "join" | "leave" | "moderation" | "api",
    message: l.message,
    guildId: l.guildId ?? null,
    userId: l.userId ?? null,
    metadata: l.metadata ?? null,
    createdAt: l.createdAt.toISOString(),
  }));

  res.json({ logs, total, page, limit });
});

router.post("/logs", async (req, res): Promise<void> => {
  // Public endpoint — bot calls this without session auth
  const parsed = CreateLogBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const [entry] = await db
    .insert(logsTable)
    .values({
      type: parsed.data.type,
      message: parsed.data.message,
      guildId: parsed.data.guildId ?? null,
      userId: parsed.data.userId ?? null,
      metadata: parsed.data.metadata ?? null,
    })
    .returning();

  res.status(201).json({
    id: entry!.id,
    type: entry!.type as "command" | "error" | "join" | "leave" | "moderation" | "api",
    message: entry!.message,
    guildId: entry!.guildId ?? null,
    userId: entry!.userId ?? null,
    metadata: entry!.metadata ?? null,
    createdAt: entry!.createdAt.toISOString(),
  });
});

export default router;
