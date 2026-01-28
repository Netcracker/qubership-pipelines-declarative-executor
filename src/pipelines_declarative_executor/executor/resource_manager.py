import asyncio
import logging
import psutil

from pipelines_declarative_executor.utils.env_var_utils import EnvVar


class ResourceManager:

    _current_count = 0
    _lock = None
    _condition = None

    @classmethod
    def _initialize(cls):
        if cls._lock is None:
            cls._lock = asyncio.Lock()
            cls._condition = asyncio.Condition(cls._lock)

    @classmethod
    async def acquire(cls) -> bool:
        cls._initialize()
        async with cls._condition:
            try:
                await asyncio.wait_for(cls._wait_for_resources(), timeout=EnvVar.RESOURCE_MANAGER_QUEUE_TIMEOUT)
                cls._current_count += 1
                return True
            except asyncio.TimeoutError:
                return False

    @classmethod
    async def release(cls):
        async with cls._condition:
            cls._current_count = max(0, cls._current_count - 1)
            cls._condition.notify_all()

    @classmethod
    async def _wait_for_resources(cls):
        while True:
            if cls._can_acquire():
                return
            await cls._condition.wait()

    @classmethod
    def _can_acquire(cls) -> bool:
        if not EnvVar.ENABLE_RESOURCE_MANAGER:
            return True

        if cls._current_count >= EnvVar.MAX_CONCURRENT_STAGES:
            return False

        try:
            required_memory = EnvVar.REQUIRED_MEMORY_PER_SUBPROCESS * 1024 * 1024  # to bytes
            available_memory = psutil.virtual_memory().available
            if available_memory < required_memory:
                logging.warning("Not enough memory to start subprocess!")
                return False
        except Exception as e:
            logging.error(f"Could not check available virtual memory: [{type(e)} - {str(e)}]")

        return True
