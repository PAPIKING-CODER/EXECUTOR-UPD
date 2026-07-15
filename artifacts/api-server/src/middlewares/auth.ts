import type { Request, Response, NextFunction } from "express";

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  const session = req.session as { userId?: string; isOwner?: boolean } | undefined;
  if (!session?.userId) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  next();
}
