import { pgTable, text, boolean, integer } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const commandsTable = pgTable("commands", {
  name: text("name").primaryKey(),
  description: text("description").notNull().default(""),
  category: text("category").notNull().default("General"),
  enabled: boolean("enabled").notNull().default(true),
  usageCount: integer("usage_count").notNull().default(0),
  permissions: text("permissions").notNull().default("@everyone"),
});

export const insertCommandSchema = createInsertSchema(commandsTable);
export type InsertCommand = z.infer<typeof insertCommandSchema>;
export type Command = typeof commandsTable.$inferSelect;
