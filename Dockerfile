# to build it:
#   docker build -t robusta-ai .
# to use it:
#   docker run -it --net=host -v $(pwd)/config.yaml:/app/config.yaml -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config robusta-ai ask "what pods are unhealthy and why?"
FROM python:3.11-slim

WORKDIR /app

# zscaler trust - uncomment for building image locally
#COPY  zscaler.root.crt /usr/local/share/ca-certificates/
#RUN chmod 644 /usr/local/share/ca-certificates/*.crt && update-ca-certificates

RUN apt-get update && apt-get install -y \
    curl \
    git \
    apt-transport-https \
    gnupg2 \
    build-essential \
    && curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update \
    && apt-get install -y kubectl unzip\
    && rm -rf /var/lib/apt/lists/* 

# Install AWS CLI v2 so kubectl works w/ remote eks clusters
# build-arg to choose architecture of the awscli binary x68_64 or aarch64 - defaulting to x86_64
ARG ARCH=x86_64
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install

# Install Google cli so kubectl works w/ remove gke clusters
RUN curl https://dl.google.com/dl/cloudsdk/release/google-cloud-sdk.tar.gz > /tmp/google-cloud-sdk.tar.gz
RUN mkdir -p /usr/local/gcloud \
  && tar -C /usr/local/gcloud -xvf /tmp/google-cloud-sdk.tar.gz \
  && /usr/local/gcloud/google-cloud-sdk/install.sh
ENV PATH $PATH:/usr/local/gcloud/google-cloud-sdk/bin
RUN gcloud components install gke-gcloud-auth-plugin

# Install Krew and add its installation directory to PATH
RUN sh -c "\
    set -x; cd \$(mktemp -d) && \
    OS=\$(uname | tr '[:upper:]' '[:lower:]') && \
    ARCH=\$(uname -m | sed -e 's/x86_64/amd64/' -e 's/\\(arm\\)\\(64\\)\\?.*/\\1\\2/' -e 's/aarch64$/arm64/') && \
    KREW=krew-\${OS}_\${ARCH} && \
    curl -fsSLO \"https://github.com/kubernetes-sigs/krew/releases/latest/download/\${KREW}.tar.gz\" && \
    tar zxvf \"\${KREW}.tar.gz\" && \
    ./\"\${KREW}\" install krew \
    "

# Add Krew to PATH
ENV PATH="/root/.krew/bin:$PATH"

# Install kube-lineage via Krew
RUN kubectl krew install lineage

# Copy the poetry configuration files into the container at /app
COPY pyproject.toml poetry.lock* /app/

ARG PRIVATE_PACKAGE_REGISTRY="none"
RUN if [ "${PRIVATE_PACKAGE_REGISTRY}" != "none" ]; then \
    pip config set global.index-url "${PRIVATE_PACKAGE_REGISTRY}"; \
    fi \
    && pip install poetry     

# Increase poetry timeout in case package registry times out
ARG POETRY_REQUESTS_TIMEOUT
RUN poetry config virtualenvs.create false \
    && if [ "${PRIVATE_PACKAGE_REGISTRY}" != "none" ]; then \
    poetry source add --priority=primary artifactory "${PRIVATE_PACKAGE_REGISTRY}"; \
    fi \
    && poetry install --no-interaction --no-ansi --no-root

#COPY config.yaml /app/

COPY . /app

ARG AWS_DEFAULT_PROFILE
ARG AWS_DEFAULT_REGION
ARG AWS_PROFILE
ARG AWS_REGION

ENTRYPOINT ["poetry", "run", "--quiet", "python", "main.py"]
#CMD ["http://docker.for.mac.localhost:9093"]
