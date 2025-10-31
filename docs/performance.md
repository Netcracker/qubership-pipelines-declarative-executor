## Performance Tests

### Lazy imports

Here is before/after comparison of execution timings of a sample command `spam`

**Before** imports optimization:

```text
(first run) Total stage time: 835 ms, CLI execution: 818 ms, prepare files: 4 ms, store results: 10 ms
(next runs) Total stage time: 314 ms, CLI execution: 300 ms, prepare files: 4 ms, store results: 6 ms
```

**After** imports optimization:

```text
First run, no imports cache - Total stage time: 146 ms
├── prepare files: 4 ms
├── store results: 7 ms
├── CLI execution: 134 ms
│   ├── 103 ms - cold imports
│   ├── 4 ms - actual work
│   └── ~27 ms - subprocess
 
Next runs, with cache - Total stage time: 79 ms
├── prepare files: 3 ms
├── store results: 6 ms
├── CLI execution: 67 ms
│   ├── 41 ms - cached imports
│   ├── 4 ms - actual work
│   └── ~22 ms - subprocess
```

Timings in comparable format:

- (first run) Total stage time: 152 ms, CLI execution: 139 ms, prepare files: 4 ms, store results: 6 ms
- Total stage time: 81 ms, CLI execution: 68 ms, prepare files: 3 ms, store results: 6 ms
- Total stage time: 86 ms, CLI execution: 73 ms, prepare files: 3 ms, store results: 6 ms
- Total stage time: 82 ms, CLI execution: 69 ms, prepare files: 3 ms, store results: 6 ms
- (spam files) Total stage time: 76 ms, CLI execution: 67 ms, prepare files: 3 ms, store results: 1 ms

### Built-in Commands

When invoking ExecutionCommands in main python process, by having them built-in, as part of executor, timings are:

- (first run) Total stage time: 53 ms, CLI execution: 33 ms, prepare files: 7 ms, store results: 9 ms
- Total stage time: 36 ms, CLI execution: 15 ms, prepare files: 6 ms, store results: 9 ms
- Total stage time: 38 ms, CLI execution: 16 ms, prepare files: 6 ms, store results: 9 ms
- Total stage time: 27 ms, CLI execution: 14 ms, prepare files: 4 ms, store results: 5 ms
- (spam files) Total stage time: 17 ms, CLI execution: 8 ms, prepare files: 3 ms, store results: 1 ms

But we do lose:

- Process isolation
- Ability to run Commands in parallel (unless we redesign ExecutionCommands interface and make it async)
- Convenience of releasing "Python Modules" as separate applications, with their own release cycles

### Importing commands from modules

When invoking ExecutionCommands in main process, also without python subprocess invocation, and reading them from unzipped "Python Module" via (sort of) reflection:

- (first run) Total stage time: 39 ms, CLI execution: 25 ms, prepare files: 4 ms, store results: 7 ms
- Total stage time: 26 ms, CLI execution: 14 ms, prepare files: 3 ms, store results: 5 ms
- Total stage time: 25 ms, CLI execution: 12 ms, prepare files: 4 ms, store results: 5 ms
- Total stage time: 24 ms, CLI execution: 12 ms, prepare files: 3 ms, store results: 5 ms
- (spam files) Total stage time: 20 ms, CLI execution: 8 ms, prepare files: 4 ms, store results: 1 ms

But we do lose:

- Process isolation (and we must add imported module to our 'path')
- Ability to run Commands in parallel (unless we redesign ExecutionCommands interface and make it async)
- Method of mapping commands to their implementations is not 100% reliable (at least in this PoC implementation)
- Adds more restrictions on created commands

### Research PoCs

Prototypes of "Built-in" and "Import" solutions are available in `rnd/perf_testing` branch
