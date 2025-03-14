import { FastifyRequest, FastifyReply } from "fastify";
import {
  context,
  propagation,
  Span,
  SpanStatusCode,
  Tracer,
  trace,
} from "@opentelemetry/api";

/**
 * Creates a traced route handler with automatic context propagation
 *
 * @param spanName The name of the span to create
 * @param tracer The tracer to use for creating spans
 * @param handler The function to execute within the span context
 * @returns A Fastify route handler function
 */
export function createTracedHandler<T>(
  spanName: string,
  tracer: Tracer,
  handler: (
    request: FastifyRequest,
    reply: FastifyReply,
    span: Span,
  ) => Promise<T>,
) {
  return async (request: FastifyRequest, reply: FastifyReply) => {
    // Extract propagated context from request headers
    const extractedContext = propagation.extract(
      context.active(),
      request.headers,
    );

    // Run the handler within the extracted context
    return context.with(extractedContext, () => {
      return tracer.startActiveSpan(spanName, async (span) => {
        try {
          // Add useful attributes to the span
          span.setAttribute("http.method", request.method);
          span.setAttribute("http.url", request.url);

          // Execute the actual handler
          return await handler(request, reply, span);
        } catch (error) {
          // Record any errors
          span.recordException(error as Error);
          span.setStatus({ code: SpanStatusCode.ERROR });
          throw error;
        } finally {
          span.end();
        }
      });
    });
  };
}
