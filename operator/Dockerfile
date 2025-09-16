# Dockerfile for Holmes Operator
# Lightweight image with just the operator requirements

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy operator code
COPY main.py /app/main.py

# Create non-root user
RUN groupadd -g 1000 operator || groupmod -g 1000 operator && \
    useradd -m -u 1000 -g 1000 operator || usermod -u 1000 -g 1000 operator && \
    chown -R 1000:1000 /app
USER 1000

# Set Python to unbuffered mode
ENV PYTHONUNBUFFERED=1

# Health check endpoint (kopf provides this on port 8081)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/healthz')" || exit 1

# Run the operator (Kopf health on 8081, Prometheus metrics on 8080)
ENTRYPOINT ["kopf", "run", "-A", "--standalone", "--liveness=http://0.0.0.0:8081/healthz", "/app/main.py"]
