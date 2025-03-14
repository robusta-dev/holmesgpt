import Fastify from "fastify";
import { setup as setupCheckout } from "./checkout-service.js";
import { setup as setupBackend } from "./backend-service.js";
import { setup as setupFraud } from "./fraud-service.js";
import { setup as setupAuth } from "./auth-service.js";
import { initTelemetry } from "./telemetry.js";

async function start() {
  const fastify = Fastify({
    logger: true,
  });
  initTelemetry("all-service", fastify);
  setupFraud(fastify);
  setupCheckout(fastify);
  setupAuth(fastify);
  setupBackend(fastify);
  try {
    await fastify.listen({ port: 3003, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3003");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}

start();
