import os
import sys
import yaml
from qubership_pipelines_common_library.v1.github_client import GithubClient

import logging
logging.basicConfig(stream=sys.stdout,
                    format='[%(asctime)s] [%(levelname)-5s] [%(filename)s:%(lineno)-3s] %(message)s',
                    level=logging.DEBUG)

WORKFLOW_FILE = os.getenv('TARGET_WORKFLOW_FILE', 'UNDEFINED')
REPO_FULL_NAME = os.getenv('REPO_FULL_NAME', 'UNDEFINED')
TARGET_BRANCH = os.getenv('TARGET_BRANCH', 'UNDEFINED')
GH_TOKEN = os.getenv('GH_TOKEN', 'UNDEFINED')

RETRY_ATTEMPTS = int(os.getenv('RUN_WORKFLOW_RETRY_ATTEMPTS', '6'))
RETRY_TIMEOUT = int(os.getenv('RUN_WORKFLOW_RETRY_TIMEOUT', '5'))
GENERATED_BRANCHES_POOL_SIZE = int(os.getenv('GENERATED_BRANCHES_POOL_SIZE', '40'))
GH = GithubClient(GH_TOKEN)


def run_workflow():
    repo_parts = REPO_FULL_NAME.split("/")
    return GH.trigger_workflow(repo_parts[0], repo_parts[1], WORKFLOW_FILE, TARGET_BRANCH, {})


def save_summary(data):
    message = f"""### Workflow generated and executed:
- Check resulting [GENERATED_WORKFLOW.yml]({os.getenv('GENERATED_WORKFLOW_URL', 'UNKNOWN')})
"""
    if data:
        message += f"""
- [Executed run]({data['url']}):
```
{yaml.safe_dump(data, sort_keys=False)}```"""
    with open(os.getenv('GITHUB_STEP_SUMMARY'), 'w') as summary_file:
        summary_file.write(message)


def save_artifact(data):
    if not data:
        logging.error("No data to save!")
    with open('result.yaml', 'w') as fs:
        yaml.safe_dump(data, fs, sort_keys=False)


if __name__ == '__main__':
    execution_info = run_workflow()
    execution_data = {
        "id": execution_info.get_id(),
        "createdAt": execution_info.get_time_start(),
        "branch": TARGET_BRANCH,
        "url": execution_info.get_url(),
    }
    save_summary(execution_data)
    save_artifact(execution_data)
