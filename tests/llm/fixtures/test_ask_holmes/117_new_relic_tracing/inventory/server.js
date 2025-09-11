// Node 18+
import http from "node:http";
import pino from "pino";

const PORT = process.env.PORT || 7000;
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

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/healthz") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ ok: true, service: "inventory" }));
    }

    if (req.method === "POST" && req.url === "/inventory/check") {
      const { itemId = "sku-1", qty = 1 } = await readJson(req);
      const available = Number(qty) <= 5;
      log.info({ itemId, qty, available }, "inventory.check");
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ available }));
    }

    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "not_found" }));
  } catch (e) {
    log.error({ err: e?.message || String(e) }, "unhandled");
    res.writeHead(500, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: String(e) }));
  }
});

server.listen(PORT, () => log.info({ port: PORT }, "listening"));
