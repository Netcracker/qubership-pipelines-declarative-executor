from datetime import datetime

import yaml
import random
import uuid

from typing import Any


class RandomPipelineGenerator:
    TEMPLATES = {
        "template-spam-params": {
            "type": "PYTHON_MODULE",
            "command": "spam",
            "input": {
                "params": {
                    "params": {
                        "param_count": 3,
                        "sleep_time": 0,
                    }
                },
            },
            "output": {
                "params": {
                    "RESULT_SPAM": "params.some_insecure_param_0"
                }
            }
        },
        "template-spam-files": {
            "type": "PYTHON_MODULE",
            "command": "spam-files",
            "input": {
                "params": {
                    "params": {
                        "files_count": 3,
                    }
                },
            },
        },
        "template-system-load-cpu-test": {
            "type": "PYTHON_MODULE",
            "command": "system-load-test",
            "input": {
                "params": {
                    "params": {
                        "sleep_between_tests": 0,
                        "cpu": {
                            "run_test": True,
                            "load": 1,
                            "duration": 1
                        },
                    }
                }
            }
        },
        "template-system-load-ram-test": {
            "type": "PYTHON_MODULE",
            "command": "system-load-test",
            "input": {
                "params": {
                    "params": {
                        "sleep_between_tests": 0,
                        "ram": {
                            "run_test": True,
                            "size_mb": 50,
                            "duration": 1,
                            "chunks": 2
                        },
                    }
                }
            }
        },
        "template-system-load-network-test": {
            "type": "PYTHON_MODULE",
            "command": "system-load-test",
            "input": {
                "params": {
                    "params": {
                        "sleep_between_tests": 0,
                        "network": {
                            "run_test": True,
                            "url": "https://raw.githubusercontent.com/Netcracker/qubership-pipelines-common-python-library/refs/heads/main/README.md",
                        },
                    }
                }
            }
        }
    }

    def __init__(self, stages_count: int = 50, add_parallel_blocks: bool = True,
                 max_parallel_stages: int = 8, parallel_percentage: float = 0.2):
        self.stages_count = stages_count
        self.add_parallel_blocks = add_parallel_blocks
        self.max_parallel_stages = max_parallel_stages
        self.parallel_percentage = parallel_percentage
        self.pipeline_id = f"pipeline-{str(uuid.uuid4())[:8]}"

    def _generate_single_stage(self, stage_num: int) -> dict[str, Any]:
        template_name = random.choice(list(self.TEMPLATES.keys()))
        return {
            "name": f"Stage {template_name} {stage_num}",
            "job": template_name
        }

    def _generate_parallel_block(self, start_stage_num: int, children_count: int) -> dict[str, Any]:
        parallel_stages = []
        for i in range(children_count):
            template_name = random.choice(list(self.TEMPLATES.keys()))
            parallel_stages.append({
                "name": f"Stage {template_name} {start_stage_num + i}",
                "job": template_name
            })

        return {
            "name": f"Parallel Block {start_stage_num}",
            "parallel": parallel_stages
        }

    def _create_parallel_blocks_distribution(self) -> list[int]:
        if not self.add_parallel_blocks or self.stages_count < 3:
            return []

        target_parallel_children = int(self.stages_count * self.parallel_percentage)

        total_stages_allocated = 0
        parallel_blocks = []

        while total_stages_allocated < target_parallel_children:
            remaining_needed = target_parallel_children - total_stages_allocated
            if remaining_needed < 2:
                break

            max_possible = min(self.max_parallel_stages, remaining_needed)
            if max_possible < 2:
                break

            block_size = random.randint(2, max_possible)
            parallel_blocks.append(block_size)
            total_stages_allocated += block_size

        return parallel_blocks

    def generate_pipeline(self) -> dict[str, Any]:
        if not self.add_parallel_blocks:
            stages = []
            for i in range(1, self.stages_count + 1):
                stages.append(self._generate_single_stage(i))

        else:
            parallel_blocks_dist = self._create_parallel_blocks_distribution()
            parallel_stages_total = sum(1 + children for children in parallel_blocks_dist)
            single_stages_count = max(0, self.stages_count - parallel_stages_total)

            stages = []
            stage_counter = 1
            stage_types = []

            for _ in range(single_stages_count):
                stage_types.append("single")
            for children_count in parallel_blocks_dist:
                stage_types.append(("parallel", children_count))
            random.shuffle(stage_types)

            for stage_type in stage_types:
                if stage_type == "single":
                    stages.append(self._generate_single_stage(stage_counter))
                    stage_counter += 1
                else:
                    _, children_count = stage_type
                    parallel_block = self._generate_parallel_block(stage_counter, children_count)
                    stages.append(parallel_block)
                    stage_counter += 1 + children_count

        pipeline = {
            "kind": "AtlasPipeline",
            "apiVersion": "v2",
            "pipeline": {
                "id": self.pipeline_id,
                "name": f"Generated Pipeline - {datetime.now()}",
                "stages": stages,
                "jobs": self.TEMPLATES
            }
        }

        return pipeline

    @staticmethod
    def save_to_file(pipeline: dict[str, Any], filename: str = "pipeline.yaml"):
        with open(filename, 'w') as f:
            yaml.safe_dump(pipeline, f, default_flow_style=False, sort_keys=False)


if __name__ == '__main__':
    generator = RandomPipelineGenerator(
        stages_count=100,
        add_parallel_blocks=True,
        max_parallel_stages=8,
        parallel_percentage=0.2
    )

    pipeline = generator.generate_pipeline()
    generator.save_to_file(pipeline=pipeline, filename="pipeline.yaml")
