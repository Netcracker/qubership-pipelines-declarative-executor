### Performance Tests

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
