"""Cooperative priority for explicit deletions in the central LexIA process."""
from collections import deque
from contextlib import contextmanager
from functools import wraps
import threading
import uuid


class DeletionPriorityYield(BaseException):
    """Unwind at a safe background checkpoint without recording a file error."""


class LibraryWorkPriority:
    def __init__(self):
        self._condition = threading.Condition(threading.RLock())
        self._queue = deque()
        self._background = None
        self._owner = None

    def reserve(self):
        with self._condition:
            ticket = uuid.uuid4().hex
            self._queue.append(ticket)
            self._condition.notify_all()
            return ticket

    def cancel(self, ticket):
        with self._condition:
            if ticket in self._queue:
                self._queue.remove(ticket)
            self._condition.notify_all()

    def pending(self):
        with self._condition:
            return bool(self._queue)

    def blocker(self):
        with self._condition:
            return self._background[1] if self._background else ('otra eliminación' if self._owner else '')

    def checkpoint(self):
        with self._condition:
            if self._queue and self._background and self._background[0] == threading.get_ident():
                raise DeletionPriorityYield()

    @contextmanager
    def background(self, label):
        identity = threading.get_ident()
        with self._condition:
            while self._queue or self._background is not None or self._owner is not None:
                self._condition.wait()
            self._background = (identity, label)
        try:
            yield
        finally:
            with self._condition:
                self._background = None
                self._condition.notify_all()

    def background_task(self, label):
        def decorate(function):
            @wraps(function)
            def wrapped(*args, **kwargs):
                with self.background(label):
                    return function(*args, **kwargs)
            return wrapped
        return decorate

    @contextmanager
    def deletion(self, ticket=None):
        identity = threading.get_ident()
        with self._condition:
            nested = self._owner == identity
        if nested:
            yield
            return
        ticket = ticket or self.reserve()
        try:
            with self._condition:
                while self._background is not None or self._owner is not None or self._queue[0] != ticket:
                    self._condition.wait()
                self._owner = identity
            yield
        finally:
            with self._condition:
                if self._owner == identity:
                    self._owner = None
                if ticket in self._queue:
                    self._queue.remove(ticket)
                self._condition.notify_all()


WORK_PRIORITY = LibraryWorkPriority()
