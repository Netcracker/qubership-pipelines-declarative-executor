from __future__ import annotations

import io, logging, time

from contextlib import contextmanager
from pstats import SortKey
from pipelines_declarative_executor.utils.env_var_utils import EnvVar


class ProfilingUtils:

    class Timer:
        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.elapsed_time_ms = (time.perf_counter() - self.start_time) * 1_000

    @staticmethod
    @contextmanager
    def time_it(message: str = ''):
        message = f"{message} - " if message else ''
        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            elapsed = end - start
            logging.info(f"{message}Executed in {elapsed:.6f} seconds")

    @staticmethod
    @contextmanager
    def profile_it():
        if not EnvVar.ENABLE_PROFILER_STATS:
            yield
            return
        import cProfile, pstats
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            yield
        finally:
            profiler.disable()
            stats_stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stats_stream)
            stats.sort_stats(SortKey.TIME)
            stats.print_stats(30)
            logging.info("PROFILING RESULT:\n%s", stats_stream.getvalue())

    @staticmethod
    def get_monitoring_metrics() -> dict:
        return {
            'peak_memory_mb': 0.0,
            'avg_cpu': 0.0,
            'samples': 0,
            'total_cpu': 0.0,
        }

    @staticmethod
    async def monitor_process(pid: int, metrics: dict, interval: float = 0.1):
        try:
            import psutil, asyncio
            parent = psutil.Process(pid)
            processes = {parent.pid: parent}
            while True:
                try:
                    for child in parent.children(recursive=True):
                        if child.pid not in processes:
                            processes[child.pid] = child

                    current_memory_mb = 0.0
                    current_cpu_percent = 0.0

                    for proc in processes.values():
                        mem_info = proc.memory_info()
                        current_memory_mb += mem_info.rss / (1024 * 1024) # RSS = Resident Set Size = physical memory
                        current_cpu_percent += proc.cpu_percent(interval=None)

                    metrics['peak_memory_mb'] = max(metrics['peak_memory_mb'], current_memory_mb)
                    metrics['total_cpu'] += current_cpu_percent
                    metrics['samples'] += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                except Exception as e:
                    logging.debug(f"Monitoring error for PID {pid}: {e}")

                await asyncio.sleep(interval)

        except Exception as e:
            logging.debug(f"Failed to monitor process {pid}: {e}")
