## qubership-pipelines-declarative-executor

This repo contains GitHub-composite-actions and reusable workflows created for generating GitHub-native workflows from [Atlas Pipelines](./docs/pipelines.md)

Atlas Pipelines are intended to be composed of jobs following a certain contract, that are implemented as executor-agnostic python modules, packed into docker containers.

Example modules for this repo are going to be developed and built [in a separate repo with development guide](https://github.com/Netcracker/qubership-cli-command-samples).

### Installation:

In more details, installation process is described in [a separate article](./docs/installation.md)

- Creating repository for your tenant (all workflows will be executed there, it might be private, and all the secrets will be used from its store)
- Adding initial configuration (3 workflows, provided [in this repo](./tenant_sample_repo)) and adapting it, if necessary (e.g. choosing appropriate qubership-pipelines-declarative-executor version)
- Generating token with write access to your repo's actions/workflows/content and adding it into secrets
- Executing your Atlas Pipelines from your repo (either from locally-added config files, or from other repos/web)
