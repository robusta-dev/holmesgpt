FROM python:3.11-slim

# Install Flask and OpenTelemetry packages
RUN pip install --no-cache-dir \
    flask==3.1.2 \
    opentelemetry-api==1.37.0 \
    opentelemetry-sdk==1.37.0 \
    opentelemetry-instrumentation-flask==0.58b0 \
    opentelemetry-exporter-otlp-proto-grpc==1.37.0 \
    requests==2.32.3

# Create app directory
RUN mkdir /app

# Set working directory
WORKDIR /app

# Default command - can be overridden
CMD ["python", "/app/app.py"]
