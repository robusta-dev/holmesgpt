import { fastifyOtelInstrumentation } from "./telemetry.js";
import Fastify, { FastifyInstance } from "fastify";
import { trace } from "@opentelemetry/api";
import { pathToFileURL } from "url";
import { createTracedHandler } from "./util/trace-handler.js";
import { executePostgresQuery } from "./util/db.js";
import fastifyMetrics from "fastify-metrics";

const tracer = trace.getTracer("fraud-service");

export const setup = async (fastify: FastifyInstance) => {
  fastify.get(
    "/fraud/health",
    createTracedHandler("health", tracer, async (request, reply, span) => {
      return reply.send({
        ok: true,
      });
    }),
  );
  fastify.post(
    "/fraud/api/fraud",
    createTracedHandler(
      "check_for_fraud",
      tracer,
      async (request, reply, span) => {
        const data = request.body as any;
        let is_fraud = true;
        if (data.cardNumber && data.cardNumber.startsWith("1234")) {
          is_fraud = false;
        }
        await executePostgresQuery(
          "SELECT * FROM banned_card_numbers WHERE id=$1",
          7000,
        );
        span.addEvent("validated_payment", {
          cardNumber: data.cardNumber,
        });

        await new Promise((resolve) => setTimeout(resolve, 200));

        span.addEvent("check_for_fraud_completed");

        return {
          is_fraud: is_fraud,
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
  await fastify.register(fastifyMetrics as any, { endpoint: "/metrics" });
  // await fastify.register(fastifyOtelInstrumentation.plugin());
  await setup(fastify);
  try {
    await fastify.listen({ port: 3005, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3004");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}
