// Node 18+
import http from "node:http";
import { URL } from "node:url";
import crypto from "node:crypto";
import pino from "pino";

const PORT = process.env.PORT || 3000;
const INVENTORY_BASE_URL = process.env.INVENTORY_BASE_URL || "http://localhost:7000";
const RISK_BASE_URL = process.env.RISK_BASE_URL || "http://localhost:8000";
const TIMEOUT_MS = Number(process.env.TIMEOUT_MS || 400);

// logging (off by default)
const level = process.env.LOG_LEVEL || (process.env.LOG === "1" ? "info" : "silent");
const log = pino({ level });

function readJson(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", c => (data += c));
    req.on("end", () => { try { resolve(data ? JSON.parse(data) : {}); } catch (e) { reject(e); } });
    req.on("error", reject);
  });
}

async function fetchJson(url, { method = "GET", headers = {}, body, timeout = TIMEOUT_MS } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(url, {
      method,
      headers: { "content-type": "application/json", ...headers },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal
    });
    const json = await res.json().catch(() => ({}));
    return { status: res.status, json };
  } finally { clearTimeout(t); }
}

// optional hooks for demo
async function preInventory(ctx)  { log.debug({ ctx }, "preInventory"); }
async function postInventory(ctx) { log.debug({ ctx }, "postInventory"); }
async function preRisk(ctx)       { log.debug({ ctx }, "preRisk"); }
async function postRisk(ctx)      { log.debug({ ctx }, "postRisk"); }

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/healthz") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ ok: true, service: "checkout" }));
    }

    if (req.method === "POST" && req.url === "/orders") {
      const body = await readJson(req);
      const requestId = req.headers["x-request-id"] || crypto.randomUUID();

      const fwd = {
        "x-request-id": requestId,
        ...(req.headers.traceparent ? { traceparent: req.headers.traceparent } : {}),
        ...(req.headers.tracestate ? { tracestate: req.headers.tracestate } : {})
      };

      const ctx = {
        requestId,
        userId: body.userId || "anon",
        itemId: body.itemId || "sku-1",
        qty: Number(body.qty ?? 1),
        amount: Number(body.amount ?? 0)
      };
      log.info({ path: "/orders", ctx }, "received");

      // 1) inventory
      await preInventory(ctx);
      const inv = await fetchJson(new URL("/inventory/check", INVENTORY_BASE_URL), {
        method: "POST", headers: fwd, body: { itemId: ctx.itemId, qty: ctx.qty }
      });
      await postInventory({ ...ctx, invStatus: inv.status });
      if (inv.status !== 200 || !inv.json?.available) {
        res.writeHead(409, { "content-type": "application/json" });
        return res.end(JSON.stringify({ ok: false, stage: "inventory", reason: "not_available" }));
      }

      // 2) risk
      await preRisk(ctx);
      const risk = await fetchJson(new URL("/risk/score", RISK_BASE_URL), {
        method: "POST", headers: fwd,
        body: { userId: ctx.userId, amount: ctx.amount, itemId: ctx.itemId, qty: ctx.qty }
      });
      await postRisk({ ...ctx, riskStatus: risk.status, score: risk.json?.score });
      if (risk.status !== 200 || risk.json?.isFraud) {
        res.writeHead(403, { "content-type": "application/json" });
        return res.end(JSON.stringify({ ok: false, stage: "risk", reason: "suspected_fraud", score: risk.json?.score }));
      }

      res.writeHead(200, { "content-type": "application/json", "x-request-id": requestId });
      return res.end(JSON.stringify({
        ok: true,
        orderId: "o_" + requestId.slice(0, 8),
        inventory: { available: true },
        risk: { isFraud: false, score: risk.json?.score ?? 0 },
        status: "PLACED"
      }));
    }

    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "not_found" }));
  } catch (e) {
    log.error({ err: e?.message || String(e) }, "unhandled");
    res.writeHead(500, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: false, stage: "unknown", error: String(e) }));
  }
});

server.listen(PORT, () => log.info({ port: PORT }, "listening"));
