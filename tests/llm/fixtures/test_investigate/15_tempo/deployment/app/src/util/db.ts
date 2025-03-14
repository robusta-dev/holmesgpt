import * as opentelemetry from "@opentelemetry/api";
import { setTimeout } from "timers/promises";

/**
 * Simulates a PostgreSQL database query with OpenTelemetry instrumentation
 */
export async function executePostgresQuery(
  query: string,
  max_delay_ms: number = 1000,
) {
  const tracer = opentelemetry.trace.getTracer("postgres-service");

  return tracer.startActiveSpan(
    "postgres.query",
    { attributes: { "db.system": "postgresql", "db.statement": query } },
    async (span) => {
      try {
        // Simulate DB query execution time
        const executionTimeMs = Math.floor(Math.random() * max_delay_ms) + 5;
        span.setAttribute("db.execution_time_ms", executionTimeMs);

        // Simulate network latency and query execution
        await setTimeout(executionTimeMs);

        // Simulate a query result
        const result = {
          rowCount: Math.floor(Math.random() * 10),
          rows: Array(Math.floor(Math.random() * 10))
            .fill(0)
            .map(() => ({})),
        };

        span.setAttribute("db.rows_affected", result.rowCount);

        span.setStatus({ code: opentelemetry.SpanStatusCode.OK });
        return result;
      } catch (error) {
        // Properly record errors in the span
        span.setStatus({
          code: opentelemetry.SpanStatusCode.ERROR,
          message: error instanceof Error ? error.message : "Unknown error",
        });

        if (error instanceof Error) {
          span.recordException(error);
        }

        throw error;
      } finally {
        span.end();
      }
    },
  );
}
