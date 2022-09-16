""" _selector_events.py - AsyncSlot based on SelectorEventLoop """

import asyncio
import concurrent.futures
import selectors
import weakref
from typing import List, Optional, Tuple
from ._base_events import *


__all__ = 'AsyncSlotSelectorEventLoop', 'AsyncSlotSelectorEventLoopPolicy',


class AsyncSlotSelector(selectors.BaseSelector):
    # The selector has four states: IDLE, BLOCKED, UNBLOCKED, CLOSED.

    def __init__(self, selector: selectors.BaseSelector,
                 write_to_self: weakref.WeakMethod):
        super().__init__()
        self._selector = selector
        self._write_to_self = write_to_self
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._select_future: Optional[concurrent.futures.Future] = None
        self._notifier: Optional[AsyncSlotNotifier] = None
        self._closed = False

    def set_notifier(self, notifier: AsyncSlotNotifier) -> None:
        # set_notifier() is called before the loop starts.  At this time
        # the selector cannot be in blocked state.
        assert not self._blocked(), 'unexpected set_notifier'
        self._notifier = notifier

    def reset_notifier(self) -> None:
        self._unblock_if_blocked()
        self._notifier = None

    def _blocked(self) -> bool:
        return (self._select_future is not None
                and not self._select_future.done())

    def _unblock_if_blocked(self):
        if self._blocked():
            write_to_self = self._write_to_self()
            assert write_to_self is not None, (
                'AsyncSlotEventLoop is supposed to close AsyncSlotSelector '
                'before being deleted')
            write_to_self()
            try:
                self._select_future.exception()  # waits
            except concurrent.futures.CancelledError:
                pass

    def register(self, fileobj, events, data=None):
        self._unblock_if_blocked()
        return self._selector.register(fileobj, events, data)

    def unregister(self, fileobj):
        self._unblock_if_blocked()
        return self._selector.unregister(fileobj)

    def modify(self, fileobj, events, data=None):
        self._unblock_if_blocked()
        return self._selector.modify(fileobj, events, data)

    def select(self, timeout: Optional[float] = None) \
            -> List[Tuple[selectors.SelectorKey, int]]:

        if self._select_future is not None:
            # A prior select() call was submitted to the executor.  We only
            # submit a select() call if _run_once() calls us with a positive
            # timeout, which can only happen if there are no ready tasks to
            # execute.  That this method is called again means _run_once is
            # run again, which can only happen if we asked it to by emitting
            # the notified signal of __notifier.
            assert self._select_future.done(), 'unexpected select'
            try:
                return self._select_future.result()
            finally:
                self._select_future = None

        # Perform normal select if no notifier is set.
        if self._notifier is None:
            return self._selector.select(timeout)

        # Try select with zero timeout.  If any IO is ready or if the caller
        # does not require IO to be ready, return that.
        event_list = self._selector.select(0)
        if event_list or (timeout is not None and timeout <= 0):
            return event_list

        # No IO is ready and caller wants to wait.  select() in a separate
        # thread and tell the caller to yield.
        self._select_future = self._executor.submit(self._selector.select,
                                                    timeout)
        # Make a copy of notify because by the time the callback is invoked,
        # self._notifier may have already been reset.
        notify = self._notifier.notify
        self._select_future.add_done_callback(lambda _: notify())
        raise AsyncSlotYield

    def close(self) -> None:
        # close() is called when the loop is being closed, and the loop
        # can only be closed when it is in STOPPED state.  In this state
        # the selector cannot be blocked.  In addition, the self pipe is
        # closed before closing the selector, so write_to_self cannot be
        # used at this point.
        assert not self._blocked(), 'unexpected close'
        if not self._closed:
            self._executor.shutdown()
            self._selector.close()
            self._select_future = None
            self._notifier = None
            self._closed = True

    def get_key(self, fileobj):
        self._unblock_if_blocked()
        return self._selector.get_key(fileobj)

    def get_map(self):
        self._unblock_if_blocked()
        return self._selector.get_map()


class AsyncSlotSelectorEventLoop(AsyncSlotBaseEventLoop,
                                 asyncio.SelectorEventLoop):

    def __init__(self):
        selector = AsyncSlotSelector(selectors.DefaultSelector(),
                                     weakref.WeakMethod(self._write_to_self))
        super().__init__(selector)


class AsyncSlotSelectorEventLoopPolicy(asyncio.events.BaseDefaultEventLoopPolicy):
    _loop_factory = AsyncSlotSelectorEventLoop
