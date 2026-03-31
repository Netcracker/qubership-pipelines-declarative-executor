FROM python:3.11-slim
LABEL org.opencontainers.image.description="Qubership Pipelines Declarative Executor"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends p7zip-full curl procps git && rm -rf /var/lib/apt/lists/*

# Install SOPS
RUN curl -LO https://github.com/getsops/sops/releases/download/v3.12.2/sops-v3.12.2.linux.amd64 && \
    mv sops-v3.12.2.linux.amd64 /usr/local/bin/sops && chmod +x /usr/local/bin/sops

# Install Executor
COPY . .
RUN pip install --no-compile --no-cache-dir -r requirements.txt

# Install CLI Samples
RUN curl -L -o quber_cli.pyz https://github.com/Netcracker/qubership-pipelines-cli-command-samples/releases/latest/download/qubership_cli_samples.pyz

ENV PATH="/root/.local/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH="/app/quber_cli.pyz" \
    PYTHONUNBUFFERED=1