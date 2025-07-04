import { NodeSDK } from "@opentelemetry/sdk-node";
import opentelemetry from "@opentelemetry/api";
import {
  BatchSpanProcessor,
  ConsoleSpanExporter,
  NodeTracerProvider,
} from "@opentelemetry/sdk-trace-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import {
  PeriodicExportingMetricReader,
  ConsoleMetricExporter,
  MeterProvider,
} from "@opentelemetry/sdk-metrics";
import pkg from "@fastify/otel";
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
} from "@opentelemetry/semantic-conventions";
import { Resource } from "@opentelemetry/resources";
import { PrometheusExporter } from "@opentelemetry/exporter-prometheus";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
const { FastifyOtelInstrumentation } = pkg;

const service_name = process.env.SERVICE_NAME || "minishop";

const resource = new Resource({
  [ATTR_SERVICE_NAME]: service_name,
  [ATTR_SERVICE_VERSION]: "1.0",
});

const metricReader = new PrometheusExporter({
  port: parseInt(process.env.METRICS_PORT) || 9463,
});

const traceExporter = new OTLPTraceExporter({
  url: process.env.TEMPO_URL || "http://localhost:4318/v1/traces",
  keepAlive: true,
  concurrencyLimit: 100,
  timeoutMillis: 5000,
});

const spanProcessor = new BatchSpanProcessor(traceExporter, {
  maxExportBatchSize: 10,
  scheduledDelayMillis: 100,
});

const traceProvider = new NodeTracerProvider({
  resource: resource,
  spanProcessors: [spanProcessor],
});

traceProvider.register();
const sdk = new NodeSDK({
  serviceName: service_name,
  resource: resource,
  traceExporter: traceExporter,
  spanProcessor: spanProcessor,
  metricReader: metricReader,
});

sdk.start();

const fastifyOtelInstrumentation = new FastifyOtelInstrumentation({
  servername: service_name,
});

export { fastifyOtelInstrumentation };
