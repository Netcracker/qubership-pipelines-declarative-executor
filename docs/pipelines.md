## Atlas pipelines

Atlas-pipelines are used to describe orchestrator-agnostic DevOps processes.

You can chain (or launch in parallel) different jobs, dynamically use parameters received from results of previous jobs, collect execution reports etc.

The "jobs" themselves are python CLIs wrapped into docker images, so you can implement any steps needed for your process.

### Pipeline structure

TBD

### "PYTHON_DOCKER_IMAGE" jobs

Sample jobs are implemented in [qubership-pipelines-cli-command-samples](https://github.com/Netcracker/qubership-pipelines-cli-command-samples).

Your created jobs should follow the same contract - take input parameters and files from context, implement ExecutionCommand interface, and store outputs according to context config.
