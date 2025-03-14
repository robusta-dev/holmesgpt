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
import { callout, getUrl } from "./util/callout.js";
import { createTracedHandler } from "./util/trace-handler.js";

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

  fastify.get("/backend/checkout", async (request, reply) => {
    return tracer.startActiveSpan("serve_checkout_page", async (span) => {
      try {
        span.addEvent("serving_checkout_page");

        return reply
          .type("text/html")
          .send(
            fs.readFileSync(
              path.join(__dirname, "./templates/checkout.html"),
              "utf8",
            ),
          );
      } catch (error) {
        span.recordException(error as Error);
        span.setStatus({ code: SpanStatusCode.ERROR });
        throw error;
      } finally {
        span.end();
      }
    });
  });

  // Process checkout API
  fastify.post("/backend/api/checkout", async (request, reply) => {
    // Extract trace context from headers
    const traceparent = request.headers.traceparent as string;
    console.log(`traceparent=${traceparent}`);

    if (traceparent) {
      fastify.log.info(`Received traceparent: ${traceparent}`);
    }
    return tracer.startActiveSpan("forward_checkout", async (span) => {
      try {
        const checkoutData = request.body as any;

        const authUrl = getUrl("auth-service", 3006, "/auth/api/auth");
        await callout(authUrl, checkoutData, request.log);
        span.addEvent("forwarding_checkout");

        const checkoutUrl = getUrl(
          "checkout-service",
          3004,
          "/checkout/api/checkout",
        );
        const data = await callout(checkoutUrl, checkoutData, request.log);

        span.addEvent("forward_successful");

        return data;
      } catch (error) {
        request.log.error(error);
        // Record error in the span
        span.recordException(error as Error);
        span.setStatus({ code: SpanStatusCode.ERROR });

        return {
          success: false,
          message: `Checkout failed: ${(error as Error).message}`,
        };
      } finally {
        span.end();
      }
    });
  });
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
  initTelemetry("backend-service", fastify);
  setup(fastify);
  try {
    await fastify.listen({ port: 3003, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3003");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}
