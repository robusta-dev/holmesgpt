// import { fastifyOtelInstrumentation } from "./telemetry.js";
import Fastify from "fastify";
import { setup as setupCheckout } from "./checkout-service.js";
import { setup as setupBackend } from "./backend-service.js";
import { setup as setupFraud } from "./fraud-service.js";
import { setup as setupAuth } from "./auth-service.js";
import fastifyMetrics from "fastify-metrics";

async function start() {
  const fastify = Fastify({
    logger: true,
  });
  // await fastify.register(fastifyOtelInstrumentation.plugin());
  await fastify.register(fastifyMetrics as any, { endpoint: "/metrics" });
  await setupFraud(fastify);
  await setupCheckout(fastify);
  await setupAuth(fastify);
  await setupBackend(fastify);
  try {
    await fastify.listen({ port: 3003, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3003");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}

start();
