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
    unzip \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create and activate virtual environment
RUN python -m venv /app/venv --upgrade-deps && \
    . /app/venv/bin/activate

ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Needed for kubectl
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key -o Release.key

# Set the architecture-specific kube lineage URLs
ARG KUBE_LINEAGE_ARM_URL=https://github.com/Avi-Robusta/kube-lineage/releases/download/v2.2.1/kube-lineage-macos-latest-v2.2.1
ARG KUBE_LINEAGE_AMD_URL=https://github.com/Avi-Robusta/kube-lineage/releases/download/v2.2.1/kube-lineage-ubuntu-latest-v2.2.1
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
RUN chmod 777 kube-lineage
RUN ./kube-lineage --version

# Set the architecture-specific argocd URLs
ARG ARGOCD_ARM_URL=https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-arm64
ARG ARGOCD_AMD_URL=https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
# Conditional download based on the platform
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
    curl -L -o argocd $ARGOCD_ARM_URL; \
    elif [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
    curl -L -o argocd $ARGOCD_AMD_URL; \
    else \
    echo "Unsupported platform: $TARGETPLATFORM"; exit 1; \
    fi
RUN chmod 777 argocd
RUN ./argocd --help

# Set the architecture-specific aws-cli
# ARG AWS_CLI_ARM_URL=https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip
# ARG AWS_CLI_AMD_URL=https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
# # Conditional download based on the platform
# RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
#     curl $AWS_CLI_ARM_URL -o "awscliv2.zip"; \
#     elif [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
#     curl $AWS_CLI_AMD_URL -o "awscliv2.zip"; \
#     else \
#     echo "Unsupported platform: $TARGETPLATFORM"; exit 1; \
#     fi
# RUN unzip awscliv2.zip && ./aws/install
# RUN aws --version

# Install Helm
RUN curl https://baltocdn.com/helm/signing.asc | gpg --dearmor -o /usr/share/keyrings/helm.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" \
    | tee /etc/apt/sources.list.d/helm-stable-debian.list \
    && apt-get update \
    && apt-get install -y helm \
    && rm -rf /var/lib/apt/lists/*

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

# We're installing here libexpat1, to upgrade the package to include a fix to 3 high CVEs. CVE-2024-45491,CVE-2024-45490,CVE-2024-45492
RUN apt-get update \
    && apt-get install -y \
    curl \
    jq \
    git \
    apt-transport-https \
    gnupg2 \
    && apt-get purge -y --auto-remove \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# Set up kubectl
COPY --from=builder /app/Release.key Release.key
RUN cat Release.key |  gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update
RUN apt-get install -y kubectl

# Set up kube lineage
COPY --from=builder /app/kube-lineage /usr/local/bin
RUN kube-lineage --version

# Set up ArgoCD
COPY --from=builder /app/argocd /usr/local/bin/argocd
RUN argocd --help

# Set up AWS CLI
# COPY --from=builder /usr/local/aws-cli/ /usr/local/aws-cli/
# ENV PATH $PATH:/usr/local/aws-cli/v2/current/bin
# RUN aws --version

# Set up Helm
COPY --from=builder /usr/bin/helm /usr/local/bin/helm
RUN chmod 555 /usr/local/bin/helm
RUN helm version

ARG AWS_DEFAULT_PROFILE
ARG AWS_DEFAULT_REGION
ARG AWS_PROFILE
ARG AWS_REGION

# Patching CVE-2024-32002
RUN git config --global core.symlinks false

# Remove setuptools-65.5.1 installed from python:3.11-slim base image as fix for CVE-2024-6345 until image will be updated
RUN rm -rf /usr/local/lib/python3.11/site-packages/setuptools-65.5.1.dist-info

COPY . /app

ENTRYPOINT ["python", "holmes.py"]
#CMD ["http://docker.for.mac.localhost:9093"]
