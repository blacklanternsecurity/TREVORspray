import queue
import logging
import threading
from time import sleep
from contextlib import suppress

log = logging.getLogger("trevorspray.util.threadpool")


class ThreadPool:
    def __init__(self, maxthreads=10, name="threadpool"):
        self.maxthreads = int(maxthreads)
        self.name = str(name)
        self.pool = [None] * self.maxthreads
        self.inputQueue = queue.SimpleQueue()
        self.outputQueue = queue.SimpleQueue()
        self._stop = False

    def start(self):
        log.debug(
            f'Starting thread pool "{self.name}" with {self.maxthreads:,} threads'
        )
        for i in range(self.maxthreads):
            t = ThreadWorker(pool=self, name=f"{self.name}_worker_{i + 1}")
            t.start()
            self.pool[i] = t

    def results(self, wait=False):
        while 1:
            result = False
            with suppress(Exception):
                while 1:
                    yield self.outputQueue.get_nowait()
                    result = True
            if self.queuedTasks == 0 or not wait:
                break
            if not result:
                # sleep briefly to save CPU
                sleep(0.1)

    @property
    def queuedTasks(self):
        queuedTasks = 0
        with suppress(Exception):
            queuedTasks += self.inputQueue.qsize()
        queuedTasks += [t.busy for t in self.pool if t is not None].count(True)
        return queuedTasks

    @property
    def finished(self):
        if self._stop:
            return True
        else:
            finishedThreads = [not t.busy for t in self.pool if t is not None]
            try:
                inputThreadAlive = self.inputThread.is_alive()
            except AttributeError:
                inputThreadAlive = False
            return (
                not inputThreadAlive
                and self.inputQueue.empty()
                and all(finishedThreads)
            )

    def submit(self, callback, *args, **kwargs):
        self.inputQueue.put((callback, args, kwargs))

    def map(self, callback, iterable, *args, **kwargs):
        self.inputThread = threading.Thread(
            target=self.feedQueue, args=(callback, iterable, args, kwargs), daemon=True
        )
        self.inputThread.start()
        self.start()
        sleep(0.1)
        yield from self.results(wait=True)

    def feedQueue(self, callback, iterable, args, kwargs):
        for i in iterable:
            if self._stop:
                break
            self.submit(callback, i, *args, **kwargs)

    def stop(self, wait=True):
        results = []

        log.debug(f"Shutting down thread pool with wait={wait}")
        results += list(self.results(wait=wait))

        self._stop = True

        # make sure input queues are empty
        with suppress(Exception):
            while 1:
                self.inputQueue.get_nowait()
        with suppress(Exception):
            self.inputQueue.close()

        # make sure output queues are empty
        results += list(self.results(wait=False))
        with suppress(Exception):
            self.outputQueue.close()

        return results

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.stop(wait=False)


class ThreadWorker(threading.Thread):
    def __init__(self, pool, name="worker"):
        self.pool = pool
        self.busy = False

        super().__init__(name=str(name), daemon=True)

    def run(self):
        while not self.pool._stop:
            ran = False
            self.busy = True
            try:
                callback, args, kwargs = self.pool.inputQueue.get_nowait()
                try:
                    self.pool.outputQueue.put(callback(*args, **kwargs))
                    ran = True
                except Exception:
                    import traceback

                    log.error(
                        f"Error in thread worker {self.name}: {traceback.format_exc()}"
                    )
                    break
                except KeyboardInterrupt:
                    log.error(f'Thread worker "{name}" Interrupted')
                    self.pool._stop = True
                    raise
            except queue.Empty:
                pass
            finally:
                self.busy = False
            if not ran:
                sleep(0.1)
