### Release preparation checklist

- [ ] Run integration tests (workflow `run-tests.yml`)
- [ ] All automatic workflows should succeed (e.g. `super-linter`, `link-checker`)
- [ ] Update and pin upcoming version/tag in `reusable-pipeline.yml` (e.g. change `v2.0.0` to `v2.0.1`)
- [ ] Release via `build-and-release.yml` workflow
- [ ] Validate and review create release (in GitHub Releases and on PyPI)
