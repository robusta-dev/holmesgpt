import {
  context,
  propagation,
  Span,
  SpanStatusCode,
  trace,
} from "@opentelemetry/api";

const tracer = trace.getTracer("callout");

export function getUrl(host: string, port: number, path: string) {
  if (process.env.NODE_ENV !== "production") {
    return `http://localhost:3003${path}`;
  }
  return `http://${host}:${port}${path}`;
}

export async function callout(url, data, logger) {
  return tracer.startActiveSpan("callout", async (span: Span) => {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "application/json",
      };

      span.setAttribute("downstream_url", url);

      propagation.inject(context.active(), headers);
      const response = await fetch(url, {
        method: "POST",
        headers: headers,
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        logger.error(
          `Downstream response failed ${response.status} ${await response.text()}`,
        );
        const errorMsg = `HTTP error! Status: ${response.status} ${await response.text()}`;
        span.recordException(new Error(errorMsg));
        span.setStatus({ code: SpanStatusCode.ERROR });
        throw new Error(errorMsg);
      }
      const result = await response.json();
      span.end();
      return result;
    } catch (error) {
      span.recordException(error);
      span.setStatus({ code: SpanStatusCode.ERROR });
      throw error;
    } finally {
      span.end();
    }
  });
}
