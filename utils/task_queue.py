import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

class TaskQueue:
    def __init__(self, num_workers: int = 4):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.num_workers = num_workers
        self.workers = []
        self._running = False

    async def add_task(self, func: Callable, *args, **kwargs):
        """Add a task to the queue."""
        await self.queue.put((func, args, kwargs))

    async def _worker(self, worker_id: int):
        """Worker coroutine that consumes tasks from the queue."""
        logger.info(f"Worker {worker_id} started")
        while self._running:
            try:
                # Wait for a task
                task_item = await self.queue.get()
                func, args, kwargs = task_item
                
                try:
                    if asyncio.iscoroutinefunction(func):
                        await func(*args, **kwargs)
                    else:
                        await asyncio.to_thread(func, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in worker {worker_id} processing task: {e}", exc_info=True)
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} loop error: {e}")
                
        logger.info(f"Worker {worker_id} stopped")

    def start(self):
        """Start the worker tasks."""
        if self._running:
            return
        self._running = True
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker(i))
            self.workers.append(task)
        logger.info(f"TaskQueue started with {self.num_workers} workers")

    async def stop(self):
        """Stop all workers and cancel pending tasks."""
        self._running = False
        for task in self.workers:
            task.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("TaskQueue stopped")

# Global instance
task_queue = TaskQueue(num_workers=5)
