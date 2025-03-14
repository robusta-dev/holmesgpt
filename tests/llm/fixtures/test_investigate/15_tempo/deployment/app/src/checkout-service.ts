import Fastify, { FastifyInstance } from "fastify";
import fastifyStatic from "@fastify/static";
import { initTelemetry } from "./telemetry.js";
import {
  context,
  propagation,
  SpanStatusCode,
  trace,
} from "@opentelemetry/api";
import fs from "fs";
import { fileURLToPath, pathToFileURL } from "url";
import path from "path";
import { createTracedHandler } from "./util/trace-handler.js";
import { callout, getUrl } from "./util/callout.js";
import { executePostgresQuery } from "./util/db.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const tracer = trace.getTracer("checkout-service");

export const setup = async (fastify: FastifyInstance) => {
  fastify.get(
    "/checkout/health",
    createTracedHandler("health", tracer, async (request, reply, span) => {
      return reply.send({
        ok: true,
      });
    }),
  );
  fastify.post(
    "/checkout/api/checkout",
    createTracedHandler(
      "process_checkout",
      tracer,
      async (request, reply, span) => {
        const checkoutData = request.body as any;

        span.addEvent("processing_payment", {
          email: checkoutData.email,
        });
        const url = getUrl("fraud-service", 3005, "/fraud/api/fraud");
        await callout(url, checkoutData, request.log);
        await executePostgresQuery(
          "SELECT * FROM products WHERE status='available'",
          500,
        );
        await new Promise((resolve) => setTimeout(resolve, 200));
        span.addEvent("checkout_successful");

        return {
          success: true,
          message: "Order placed successfully!",
          orderId: `ORDER-${Math.floor(Math.random() * 10000)}`,
        };
      },
    ),
  );
};

const isMainModule = () => {
  const mainModulePath = import.meta.url;
  const executedFilePath = pathToFileURL(process.argv[1]).href;
  return mainModulePath === executedFilePath;
};

if (isMainModule()) {
  const fastify = Fastify({
    logger: true,
  });
  initTelemetry("checkout-service", fastify);
  setup(fastify);
  try {
    await fastify.listen({ port: 3004, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3004");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}
