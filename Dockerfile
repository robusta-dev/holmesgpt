# Build stage
FROM python:3.11-slim as builder
ENV PATH="/root/.local/bin/:$PATH"

# Install build dependencies in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    apt-transport-https \
    gnupg2 \
    build-essential \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create and activate virtual environment
RUN python -m venv /app/venv --upgrade-deps

ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Needed for kubectl
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.32/deb/Release.key -o Release.key

# Set the architecture-specific kube lineage URLs
ARG KUBE_LINEAGE_ARM_URL=https://github.com/robusta-dev/kube-lineage/releases/download/v2.2.3/kube-lineage-macos-latest-v2.2.3
ARG KUBE_LINEAGE_AMD_URL=https://github.com/robusta-dev/kube-lineage/releases/download/v2.2.3/kube-lineage-ubuntu-latest-v2.2.3
# Define a build argument to identify the platform
ARG TARGETPLATFORM
# Conditional download based on the platform
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
    curl -L -o kube-lineage $KUBE_LINEAGE_ARM_URL; \
    elif [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
    curl -L -o kube-lineage $KUBE_LINEAGE_AMD_URL; \
    else \
    echo "Unsupported platform: $TARGETPLATFORM"; exit 1; \
    fi
RUN chmod +x kube-lineage
RUN ./kube-lineage --version

# Set the architecture-specific argocd URLs
# Freezing to argocd 2.13.5 as it has fixes CVE-2025-21613 and CVE-2025-21614.
# The argocd release 2.14.2 (latest as 2025-02-19) unfortunately has these CVEs.
ARG ARGOCD_ARM_URL=https://github.com/argoproj/argo-cd/releases/download/v2.13.5/argocd-linux-arm64
ARG ARGOCD_AMD_URL=https://github.com/argoproj/argo-cd/releases/download/v2.13.5/argocd-linux-amd64
# Conditional download based on the platform
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
    curl -L -o argocd $ARGOCD_ARM_URL; \
    elif [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
    curl -L -o argocd $ARGOCD_AMD_URL; \
    else \
    echo "Unsupported platform: $TARGETPLATFORM"; exit 1; \
    fi
RUN chmod +x argocd
RUN ./argocd --help

# Install Helm
RUN curl https://baltocdn.com/helm/signing.asc | gpg --dearmor -o /usr/share/keyrings/helm.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" \
    | tee /etc/apt/sources.list.d/helm-stable-debian.list \
    && apt-get update \
    && apt-get install -y helm \
    && rm -rf /var/lib/apt/lists/*

# Set up poetry and install dependencies
ARG PRIVATE_PACKAGE_REGISTRY="none"
ARG POETRY_REQUESTS_TIMEOUT
COPY pyproject.toml poetry.lock /app/

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    if [ "${PRIVATE_PACKAGE_REGISTRY}" != "none" ]; then \
        pip config set global.index-url "${PRIVATE_PACKAGE_REGISTRY}" && \
        poetry source add --priority=primary artifactory "${PRIVATE_PACKAGE_REGISTRY}"; \
    fi && \
    poetry install --no-interaction --no-ansi --no-root --only=main


# Final stage
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH" \
    PYTHONPATH=".:/app/holmes"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/venv /venv

# Install runtime dependencies and security fixes in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    git \
    apt-transport-https \
    gnupg2 \
    ca-certificates \
    libexpat1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set up kubectl in single layer
COPY --from=builder /app/Release.key Release.key
RUN cat Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg && \
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.32/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends kubectl && \
    rm -f Release.key && \
    rm -rf /var/lib/apt/lists/*


# Microsoft ODBC for Azure SQL. Required for azure/sql toolset
RUN VERSION_ID=$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2 | cut -d '.' -f 1) && \
    if ! echo "11 12" | grep -q "$VERSION_ID"; then \
        echo "Debian $VERSION_ID is not currently supported."; \
        exit 1; \
    fi && \
    curl -sSL -O https://packages.microsoft.com/config/debian/$VERSION_ID/packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 libgssapi-krb5-2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# Set up kube lineage
COPY --from=builder /app/kube-lineage /usr/local/bin
RUN kube-lineage --version

# Set up ArgoCD
COPY --from=builder /app/argocd /usr/local/bin/argocd
RUN argocd --help

# Set up Helm
COPY --from=builder /usr/bin/helm /usr/local/bin/helm
RUN chmod +x /usr/local/bin/helm
RUN helm version

ARG AWS_DEFAULT_PROFILE
ARG AWS_DEFAULT_REGION
ARG AWS_PROFILE
ARG AWS_REGION

# Patching CVE-2024-32002
RUN git config --global core.symlinks false

# Remove vulnerable setuptools from base image (CVE-2024-6345 fix)
RUN rm -rf /usr/local/lib/python3.11/site-packages/setuptools-65.5.1.dist-info \\\n    /usr/local/lib/python3.11/ensurepip/_bundled/setuptools-65.5.0-py3-none-any.whl

COPY ./holmes /app/holmes
COPY ./server.py /app/server.py
COPY ./holmes_cli.py /app/holmes_cli.py

ENTRYPOINT ["python", "holmes_cli.py"]
#CMD ["http://docker.for.mac.localhost:9093"]
