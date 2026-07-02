#!/usr/bin/env bash
# Rewrites every version/tag reference to <version> so they stay in sync with pyproject.toml
set -euo pipefail

VERSION="${1:?Usage: update_version.sh <version>  (e.g. 2.1.2 or v1.0.0)}"
VERSION="${VERSION#v}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

ENV_VARS="$ROOT/src/pipelines_declarative_executor/utils/env_var_utils.py"
REUSABLE="$ROOT/.github/workflows/reusable-pipeline.yml"
CUSTOM_IMAGE="$ROOT/.github/workflows/pipeline_with_custom_image.yml"
PIPELINE="$ROOT/.github/workflows/pipeline.yml"

sed -i -E "s/(PDE_VERSION = )\"[^\"]*\"/\1\"${VERSION}\"/" "$ENV_VARS"

sed -i -E "s#(qubership-pipelines-declarative-executor:)v[0-9]+\.[0-9]+\.[0-9]+#\1v${VERSION}#g" \
  "$REUSABLE" "$CUSTOM_IMAGE"

sed -i -E "s#(reusable-pipeline\.yml@)v[0-9]+\.[0-9]+\.[0-9]+#\1v${VERSION}#g" "$PIPELINE"
