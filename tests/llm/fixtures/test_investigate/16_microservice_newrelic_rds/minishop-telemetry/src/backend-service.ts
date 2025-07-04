import { fastifyOtelInstrumentation } from "./telemetry.js";
import Fastify, { FastifyInstance } from "fastify";
import fastifyStatic from "@fastify/static";
import {
  context,
  propagation,
  SpanStatusCode,
  trace,
} from "@opentelemetry/api";
import fs from "fs";
import { fileURLToPath, pathToFileURL } from "url";
import path from "path";
import { callout, getUrl } from "./util/callout.js";
import { createTracedHandler } from "./util/trace-handler.js";
import fastifyMetrics from "fastify-metrics";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const tracer = trace.getTracer("backend-service");

export const setup = async (fastify: FastifyInstance) => {
  fastify.register(fastifyStatic, {
    root: path.join(__dirname, "./public"),
    prefix: "/",
  });

  fastify.get("/", async (request, reply) => {
    return reply.redirect("/backend/checkout");
  });
  fastify.get(
    "/backend/health",
    createTracedHandler("health", tracer, async (request, reply, span) => {
      return reply.send({
        ok: true,
      });
    }),
  );

  fastify.get(
    "/backend/checkout",
    createTracedHandler(
      "serve_checkout_page",
      tracer,
      async (request, reply, span) => {
        return reply
          .type("text/html")
          .send(
            fs.readFileSync(
              path.join(__dirname, "./templates/checkout.html"),
              "utf8",
            ),
          );
      },
    ),
  );

  // Process checkout API
  fastify.post(
    "/backend/api/checkout",
    createTracedHandler(
      "/backend/api/checkout",
      tracer,
      async (request, reply, span) => {
        const checkoutData = request.body as any;

        const authUrl = getUrl("auth-service", 3006, "/auth/api/auth");
        await callout(authUrl, checkoutData, request.log);

        const checkoutUrl = getUrl(
          "checkout-service",
          3004,
          "/checkout/api/checkout",
        );
        const data = await callout(checkoutUrl, checkoutData, request.log);

        return data;
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
  await fastify.register(fastifyMetrics as any, { endpoint: "/metrics" });
  // await fastify.register(fastifyOtelInstrumentation.plugin());
  await setup(fastify);
  try {
    await fastify.listen({ port: 3003, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3003");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}
