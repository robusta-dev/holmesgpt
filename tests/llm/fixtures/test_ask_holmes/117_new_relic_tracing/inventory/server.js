// Node 18+
import express from "express";
import pino from "pino";

const PORT = process.env.PORT || 7000;
const level = process.env.LOG_LEVEL || (process.env.LOG === "1" ? "info" : "silent");
const log = pino({ level });

const app = express();
app.use(express.json());

// Health check
app.get("/healthz", (req, res) => {
  res.json({ ok: true, service: "inventory" });
});

// Inventory check endpoint
app.post("/inventory/check", (req, res) => {
  const { itemId = "sku-1", qty = 1 } = req.body;
  const available = Number(qty) <= 5;
  log.info({ itemId, qty, available }, "inventory.check");
  res.json({ available });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: "not_found" });
});

// Error handler
app.use((err, req, res, next) => {
  log.error({ err: err?.message || String(err) }, "unhandled");
  res.status(500).json({ error: String(err) });
});

// Graceful shutdown
process.on("SIGTERM", () => {
  log.info("shutdown");
  server.close(() => process.exit(0));
});

const server = app.listen(PORT, () => log.info({ port: PORT }, "listening"));
