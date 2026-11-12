FROM ghcr.io/netcracker/qubership-envgene:2.16.6 AS pde-builder

RUN apk add --no-cache build-base python3-dev libffi-dev openssl-dev zlib-dev linux-headers

COPY requirements.txt /tmp/requirements.txt
RUN /usr/bin/python3 -m venv /opt/pde/venv && \
    /opt/pde/venv/bin/pip install --no-compile --no-cache-dir -r /tmp/requirements.txt

FROM ghcr.io/netcracker/qubership-envgene:2.16.6
LABEL org.opencontainers.image.description="Qubership Pipelines Declarative Executor with EnvGene"

WORKDIR /app

# EnvGene's runtime image already provides bash, git, sops, zip, tar and ca-certificates.
RUN apk add --no-cache p7zip procps curl

COPY --from=pde-builder /opt/pde/venv /opt/pde/venv
COPY . .

ARG CLI_SAMPLES_URL="https://github.com/Netcracker/qubership-pipelines-cli-command-samples/releases/latest/download/qubership_cli_samples_alpine312.pyz"
RUN curl -fL -o /app/quber_cli.pyz "${CLI_SAMPLES_URL}"

ENV PATH="/opt/pde/venv/bin:/opt/jre/bin:${PATH}" \
    PYTHONPATH="/app/src:/module/scripts" \
    PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH="/app/quber_cli.pyz" \
    PYTHONUNBUFFERED=1
