from qubership_pipelines_common_library.v1.execution.exec_command import ExecutionCommand

WORD_LIST = [
    "apple", "happy", "sunshine", "book", "mountain",
    "ocean", "guitar", "laughter", "butterfly", "coffee",
    "rainbow", "adventure", "breeze", "chocolate", "dolphin",
    "elephant", "firefly", "garden", "harmony", "island",
    "jellybean", "kitten", "lighthouse", "moonlight", "notebook",
    "orange", "penguin", "quilt", "river", "sunflower",
    "telescope", "umbrella", "violin", "waterfall", "xylophone",
    "yogurt", "zeppelin", "autumn", "blossom", "cinnamon",
    "daisy", "echo", "flamingo", "giraffe", "horizon",
    "iceberg", "jazz", "kiwi", "lullaby", "meadow"
]


class SampleStandaloneExecutionCommand(ExecutionCommand):

    def _validate(self):
        names = ["paths.input.params",
                 "paths.output.params",
                 "params.param_1",
                 "params.param_2"]
        return self.context.validate(names)

    def _execute(self):
        self.context.logger.info("Running SampleExecutionCommand - calculating sum of 'param_1' and 'param_2'...")
        result_sum = int(self.context.input_param_get("params.param_1")) + int(self.context.input_param_get("params.param_2"))
        self.context.output_param_set("params.result", result_sum)
        self.context.output_params_save()


class CalcCommand(ExecutionCommand):

    def _validate(self):
        names = ["paths.input.params",
                 "paths.output.params",
                 "params.param_1",
                 "params.param_2",
                 "params.operation",
                 "params.result_name"]
        return self.context.validate(names)

    def _execute(self):
        self.context.logger.info("Running CalcCommand - calculating operation on 'param_1' and 'param_2'...")
        param1 = int(self.context.input_param_get("params.param_1"))
        param2 = int(self.context.input_param_get("params.param_2"))
        match self.context.input_param_get("params.operation"):
            case "add":
                result = param1 + param2
            case "subtract":
                result = param1 - param2
            case "multiply":
                result = param1 * param2
            case "divide":
                result = param1 / param2
            case _:
                raise Exception(f"Invalid operation: {self.context.input_param_get('params.operation')}")
        self.context.output_param_set(f"params.{self.context.input_param_get('params.result_name')}", result)
        self.context.output_params_save()


class GenerateTestOutputParamsCommand(ExecutionCommand):

    def _validate(self):
        names = ["paths.input.params",
                 "paths.output.params"]
        return self.context.validate(names)

    def _execute(self):
        import random
        self.context.logger.info("Running GenerateTestOutputParamsCommand - spamming different params into output...")
        for i in range(5):
            self.context.output_param_set(f"params.some_insecure_param_{i}",
                                          f"{random.choice(WORD_LIST)}_{random.choice(WORD_LIST)}_{random.choice(WORD_LIST)}")
            self.context.output_param_secure_set(f"params.secure_param_{i}",
                                          f"{random.choice(WORD_LIST)}_{random.choice(WORD_LIST)}_{random.choice(WORD_LIST)}")
        self.context.output_param_set("params.nested_system.its_key", f"{random.choice(WORD_LIST)}")
        self.context.output_param_set("params.nested_system.its_secret", f"{random.choice(WORD_LIST)}")
        self.context.output_params_save()


class GenerateTestOutputFilesCommand(ExecutionCommand):

    def _validate(self):
        names = ["paths.input.params", "paths.output.files"]
        return self.context.validate(names)

    def _execute(self):
        import random
        from pathlib import Path
        files_count = int(self.context.input_param_get("params.files_count", 1))
        self.context.logger.info(f"Running GenerateTestOutputFilesCommand - creating {files_count} different file(s) in output_files directory...")
        for i in range(files_count):
            target_path = Path(self.context.input_param_get("paths.output.files")).joinpath(f"file_{i}.txt")
            with open(target_path, 'w') as fs:
                fs.write(f"File words spam: {random.choice(WORD_LIST)}_{random.choice(WORD_LIST)}_{random.choice(WORD_LIST)}\nAnd even {random.choice(WORD_LIST)}!")


COMMAND_MAPPING = {
    "run-sample": SampleStandaloneExecutionCommand,
    "calc": CalcCommand,
    "spam": GenerateTestOutputParamsCommand,
    "spam-files": GenerateTestOutputFilesCommand,
}
