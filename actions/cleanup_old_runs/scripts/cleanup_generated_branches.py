import os
import subprocess
import sys

import logging
logging.basicConfig(stream=sys.stdout,
                    format='[%(asctime)s] [%(levelname)-5s] [%(filename)s:%(lineno)-3s] %(message)s',
                    level=logging.DEBUG)

GIT_LIST_REMOTE_COMMAND = "git ls-remote --heads | cut -f 2"
GENERATED_BRANCHES_NAME = "refs/heads/sub_flow_"
REFS_HEADS_PREFIX = "refs/heads/"
GENERATED_BRANCHES_POOL_SIZE = int(os.getenv('GENERATED_BRANCHES_POOL_SIZE', '40'))
REMOVE_RELATED_WORKFLOW_RUNS = True


def get_sorted_remote_branches_list():
    output = subprocess.run(
        GIT_LIST_REMOTE_COMMAND,
        capture_output=True, text=True, shell=True)
    branches_list = [branch for branch in output.stdout.splitlines() if branch.startswith(GENERATED_BRANCHES_NAME)]
    branches_list.sort(key=lambda x: int(x[len(GENERATED_BRANCHES_NAME):]))
    return branches_list


def delete_remote_branches(branches_list):
    logging.debug(f"Branches to be deleted: {branches_list}")
    for branch in branches_list:
        output = subprocess.run(
            f"git push origin --delete {branch}",
            capture_output=True, text=True, shell=True
        )
        if REMOVE_RELATED_WORKFLOW_RUNS:
            delete_related_workflow_runs(branch)
    logging.debug(f"Removed {len(branches_list)} branches")


def delete_related_workflow_runs(full_branch_name):
    related_runs_output = subprocess.run(
        f"gh run list --branch {full_branch_name[len(REFS_HEADS_PREFIX):]} --json databaseId --jq '.[].databaseId'",
        capture_output=True, text=True, shell=True
    )
    related_runs = [trimmed_ln for ln in related_runs_output.stdout.splitlines() if (trimmed_ln := ln.strip())]
    if not related_runs:
        logging.debug(f"No related runs for {full_branch_name} exist")
        return
    logging.debug(f"Removing related_runs for {full_branch_name}: {related_runs}")
    for run_id in related_runs:
        subprocess.run(
            f"gh run delete {run_id}",
            capture_output=True, text=True, shell=True
        )


if __name__ == '__main__':
    branches = get_sorted_remote_branches_list()
    if len(branches) > GENERATED_BRANCHES_POOL_SIZE:
        logging.debug(f"Found {len(branches)} generated branches (with prefix {GENERATED_BRANCHES_NAME}, will trim oldest ones (pool size = {GENERATED_BRANCHES_POOL_SIZE})")
        branches_to_delete = branches[:len(branches) - GENERATED_BRANCHES_POOL_SIZE]
        delete_remote_branches(branches_to_delete)
