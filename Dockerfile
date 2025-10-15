FROM python:3.11-slim
LABEL org.opencontainers.image.description="Qubership Pipelines Declarative Executor"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends p7zip-full curl && rm -rf /var/lib/apt/lists/*

# Install SOPS
RUN curl -LO https://github.com/getsops/sops/releases/download/v3.10.2/sops-v3.10.2.linux.amd64 && \
    mv sops-v3.10.2.linux.amd64 /usr/local/bin/sops && chmod +x /usr/local/bin/sops

# Install Executor
COPY . .
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Install CLI Samples
ADD https://github.com/Netcracker/qubership-pipelines-cli-command-samples/releases/latest/download/qubership_cli_samples.pyz .
RUN mkdir -p /app/quber_cli && \
    7z x qubership_cli_samples.pyz -o/app/quber_cli/ -y && \
    rm qubership_cli_samples.pyz

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app/src
ENV PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH=/app/quber_cli
ENV PYTHONUNBUFFERED=1

# ENTRYPOINT ["python", "-m", "pipelines_declarative_executor"]
