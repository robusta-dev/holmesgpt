# Build stage
FROM python:3.11-slim as builder
ENV PATH="/root/.local/bin/:$PATH"

RUN apt-get update \
    && apt-get install -y \
       curl \
       git \
       apt-transport-https \
       gnupg2 \
       build-essential \
       unzip

WORKDIR /app


# Create and activate virtual environment
RUN python -m venv /app/venv --upgrade-deps && \
    . /app/venv/bin/activate

ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Needed for kubectl
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key -o Release.key

# Set the architecture-specific kube lineage URLs
ARG ARM_URL=https://github.com/Avi-Robusta/kube-lineage/releases/download/v2.0.1/kube-lineage-macos-latest-v2.0.1
ARG AMD_URL=https://github.com/Avi-Robusta/kube-lineage/releases/download/v2.0.1/kube-lineage-ubuntu-latest-v2.0.1
# Define a build argument to identify the platform
ARG TARGETPLATFORM
# Conditional download based on the platform
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
        curl -L -o kube-lineage $ARM_URL; \
    elif [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        curl -L -o kube-lineage $AMD_URL; \
    else \
        echo "Unsupported platform: $TARGETPLATFORM"; exit 1; \
    fi
RUN chmod 777 kube-lineage
RUN ./kube-lineage --version

# Set up poetry
ARG PRIVATE_PACKAGE_REGISTRY="none"
RUN if [ "${PRIVATE_PACKAGE_REGISTRY}" != "none" ]; then \
    pip config set global.index-url "${PRIVATE_PACKAGE_REGISTRY}"; \
    fi \
    && pip install poetry    
ARG POETRY_REQUESTS_TIMEOUT
RUN poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock /app/
RUN if [ "${PRIVATE_PACKAGE_REGISTRY}" != "none" ]; then \
    poetry source add --priority=primary artifactory "${PRIVATE_PACKAGE_REGISTRY}"; \
    fi \
    && poetry install --no-interaction --no-ansi --no-root

# Final stage
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH=$PYTHONPATH:.:/app/holmes

WORKDIR /app

COPY --from=builder /app/venv /venv
COPY . /app


RUN apt-get update \
    && apt-get install -y \
       git \
       apt-transport-https \
       gnupg2

# Set up kubectl
COPY --from=builder /app/Release.key Release.key
RUN cat Release.key |  gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update
RUN apt-get install -y kubectl

# Set up kube lineage
COPY --from=builder /app/kube-lineage /usr/local/bin
RUN kube-lineage --version

ARG AWS_DEFAULT_PROFILE
ARG AWS_DEFAULT_REGION
ARG AWS_PROFILE
ARG AWS_REGION

ENTRYPOINT ["python", "holmes.py"]
#CMD ["http://docker.for.mac.localhost:9093"]
