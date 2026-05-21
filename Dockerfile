FROM python:3.13-alpine
LABEL org.opencontainers.image.description="Qubership Pipelines Declarative Executor"
WORKDIR /app

ARG SOPS_VERSION
COPY .sops-version /tmp/.sops-version

RUN apk add --no-cache p7zip curl procps git

# Install SOPS
RUN SOPS_VERSION=${SOPS_VERSION:-$(cat /tmp/.sops-version)} && \
    curl -LO https://github.com/getsops/sops/releases/download/${SOPS_VERSION}/sops-${SOPS_VERSION}.linux.amd64 && \
    mv sops-${SOPS_VERSION}.linux.amd64 /usr/local/bin/sops && chmod +x /usr/local/bin/sops

# Install Executor
COPY . .
RUN pip install --no-compile --no-cache-dir -r requirements.txt

# Install CLI Samples
RUN curl -L -o quber_cli.pyz https://github.com/Netcracker/qubership-pipelines-cli-command-samples/releases/latest/download/qubership_cli_samples_alpine.pyz

ENV PATH="/root/.local/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH="/app/quber_cli.pyz" \
    PYTHONUNBUFFERED=1