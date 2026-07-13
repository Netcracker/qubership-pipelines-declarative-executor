### Release preparation checklist

- [ ] Run `update_version.sh` with next version to bump versions in workflows
- [ ] Run integration tests (workflow `run-tests.yml`)
- [ ] All automatic workflows should succeed (e.g. `super-linter`, `link-checker`)
- [ ] Release via `build-and-release.yml` workflow
- [ ] Validate and review created release (in GitHub Releases and on PyPI)

> Version/tag references are kept in sync by running: `update_version.sh`, which
> syncs the version across `env_var_utils.py`, `pipeline.yml`, `reusable-pipeline.yml`, `pipeline_with_custom_image.yml`
