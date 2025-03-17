import { fastifyOtelInstrumentation } from "./telemetry.js";
import Fastify, { FastifyInstance } from "fastify";
import { trace } from "@opentelemetry/api";
import { fileURLToPath, pathToFileURL } from "url";
import { createTracedHandler } from "./util/trace-handler.js";
import { executePostgresQuery } from "./util/db.js";
import fastifyMetrics from "fastify-metrics";

const tracer = trace.getTracer("auth-service");

export const setup = async (fastify: FastifyInstance) => {
  fastify.get(
    "/auth/health",
    createTracedHandler("health", tracer, async (request, reply, span) => {
      return reply.send({
        ok: true,
      });
    }),
  );
  fastify.post(
    "/auth/api/auth",
    createTracedHandler(
      "authenticate",
      tracer,
      async (request, reply, span) => {
        await executePostgresQuery("SELECT * FROM users WHERE id=$1", 500);
        return {
          success: true,
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
    await fastify.listen({ port: 3006, host: "0.0.0.0" });
    console.log("Backend server is running on http://localhost:3004");
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}
