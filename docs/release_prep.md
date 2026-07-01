### Release preparation checklist

- [ ] Run integration tests (workflow `run-tests.yml`)
- [ ] All automatic workflows should succeed (e.g. `super-linter`, `link-checker`)
- [ ] Release via `build-and-release.yml` workflow
- [ ] Validate and review created release (in GitHub Releases and on PyPI)

> Version/tag references are kept in sync automatically: `build-and-release.yml` bumps
> `pyproject.toml` (via `poetry version`) and then runs `update_version.sh`, which
> syncs the version across `env_var_utils.py`, `pipeline.yml`, `reusable-pipeline.yml`, `pipeline_with_custom_image.yml`
