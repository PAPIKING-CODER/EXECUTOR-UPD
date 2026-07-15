import { Router } from "express";
import { requireAuth } from "../middlewares/auth";
import { db } from "@workspace/db";
import { blacklistEntriesTable } from "@workspace/db";
import { eq, desc, like, and } from "drizzle-orm";
import { ListBlacklistQueryParams, AddBlacklistBody, RemoveBlacklistParams } from "@workspace/api-zod";

const router = Router();

router.get("/blacklist", requireAuth, async (req, res): Promise<void> => {
  const parsed = ListBlacklistQueryParams.safeParse(req.query);
  const params = parsed.success ? parsed.data : { page: 1, limit: 20 };
  const page = params.page ?? 1;
  const limit = params.limit ?? 20;
  const typeFilter = params.type;
  const search = params.search;

  let all = await db.select().from(blacklistEntriesTable).orderBy(desc(blacklistEntriesTable.addedAt));

  if (typeFilter) all = all.filter((e) => e.type === typeFilter);
  if (search) all = all.filter((e) => e.targetId.includes(search) || (e.targetName ?? "").toLowerCase().includes(search.toLowerCase()));

  const total = all.length;
  const offset = (page - 1) * limit;
  const entries = all.slice(offset, offset + limit).map((e) => ({
    id: e.id,
    type: e.type as "user" | "server" | "word",
    targetId: e.targetId,
    targetName: e.targetName ?? null,
    reason: e.reason ?? null,
    addedBy: e.addedBy,
    addedAt: e.addedAt.toISOString(),
  }));

  res.json({ entries, total, page, limit });
});

router.post("/blacklist", requireAuth, async (req, res): Promise<void> => {
  const parsed = AddBlacklistBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const session = req.session as { userId?: string };
  const [entry] = await db
    .insert(blacklistEntriesTable)
    .values({
      type: parsed.data.type,
      targetId: parsed.data.targetId,
      targetName: parsed.data.targetName ?? null,
      reason: parsed.data.reason ?? null,
      addedBy: session.userId ?? "owner",
    })
    .returning();

  res.status(201).json({
    id: entry!.id,
    type: entry!.type as "user" | "server" | "word",
    targetId: entry!.targetId,
    targetName: entry!.targetName ?? null,
    reason: entry!.reason ?? null,
    addedBy: entry!.addedBy,
    addedAt: entry!.addedAt.toISOString(),
  });
});

router.delete("/blacklist/:id", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params["id"]) ? req.params["id"][0] : req.params["id"];
  const parsed = RemoveBlacklistParams.safeParse({ id: parseInt(raw ?? "0", 10) });
  if (!parsed.success || isNaN(parsed.data.id)) {
    res.status(400).json({ error: "Invalid ID" });
    return;
  }

  await db.delete(blacklistEntriesTable).where(eq(blacklistEntriesTable.id, parsed.data.id));
  res.json({ success: true, message: "Entry removed" });
});

export default router;
