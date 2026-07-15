import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./auth";
import botRouter from "./bot";
import guildsRouter from "./guilds";
import blacklistRouter from "./blacklist";
import logsRouter from "./logs";
import commandsRouter from "./commands";
import statsRouter from "./stats";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(botRouter);
router.use(guildsRouter);
router.use(blacklistRouter);
router.use(logsRouter);
router.use(commandsRouter);
router.use(statsRouter);

export default router;
