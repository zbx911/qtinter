import qtinter
import signal
import sys
import threading
import time
import unittest
from shim import QtCore


def _raise_ki():
    return signal.default_int_handler(signal.SIGINT, None)


class TestCtrlC(unittest.TestCase):
    # A collection of test cases for the behavior of Ctrl+C for a loop
    # operating in host mode.  The expected behavior is to propagate
    # KeyboardInterrupt to the caller of run_forever.
    #
    # Adapted from test.test_asyncio.test_windows_events.ProactorLoopCtrlC
    # but also tests unix event loops.

    def setUp(self) -> None:
        if QtCore.QCoreApplication.instance() is not None:
            self.app = QtCore.QCoreApplication.instance()
        else:
            self.app = QtCore.QCoreApplication([])

    def tearDown(self) -> None:
        self.app = None

    def _test_ctrl_c(self, loop):
        def SIGINT_after_delay():
            time.sleep(0.1)
            if sys.version_info < (3, 8):
                import os
                os.kill(os.getpid(), signal.SIGINT)
            else:
                signal.raise_signal(signal.SIGINT)

        thread = threading.Thread(target=SIGINT_after_delay)
        try:
            with self.assertRaises(KeyboardInterrupt):
                loop.call_soon(thread.start)
                loop.run_forever()
        finally:
            loop.close()


@unittest.skipIf(sys.platform == 'win32', 'unix only')
class TestUnixCtrlC(TestCtrlC):
    """Test Ctrl+C under unix."""

    def test_unix_loop(self):
        self._test_ctrl_c(qtinter.QiDefaultEventLoop())

    def test_unix_loop_with_SIGCHLD_1(self):
        loop = qtinter.QiDefaultEventLoop()
        loop.add_signal_handler(signal.SIGCHLD, _raise_ki)
        self._test_ctrl_c(loop)

    def test_unix_loop_with_SIGCHLD_2(self):
        loop = qtinter.QiDefaultEventLoop()
        loop.add_signal_handler(signal.SIGCHLD, _raise_ki)
        loop.remove_signal_handler(signal.SIGCHLD)
        self._test_ctrl_c(loop)

    def test_unix_loop_with_SIGINT_1(self):
        loop = qtinter.QiDefaultEventLoop()
        loop.add_signal_handler(signal.SIGINT, _raise_ki)
        self._test_ctrl_c(loop)

    def test_unix_loop_with_SIGINT_2(self):
        loop = qtinter.QiDefaultEventLoop()
        loop.add_signal_handler(signal.SIGINT, _raise_ki)
        loop.remove_signal_handler(signal.SIGINT)
        self._test_ctrl_c(loop)


# The Windows Ctrl+C test is not run for Python 3.7, for two reasons:
# - First, the proactor event loop in Python 3.7 does not support being
#   interrupted by Ctrl+C; see https://github.com/python/cpython/issues/67246
# - Second, Python 3.7 does not have the raise_signal function, and
#   os.kill(SIGINT) does not work under Windows; see
#   https://stackoverflow.com/questions/35772001/how-to-handle-a-signal-sigint-on-a-windows-os-machine
@unittest.skipUnless(sys.platform == 'win32', 'windows only')
@unittest.skipUnless(sys.version_info >= (3, 8), 'requires python >= 3.8')
class TestWindowsCtrlC(TestCtrlC):
    """Test Ctrl+C under windows."""

    def test_windows_proactor_loop(self):
        self._test_ctrl_c(qtinter.QiProactorEventLoop())

    def test_windows_selector_loop(self):
        self._test_ctrl_c(qtinter.QiSelectorEventLoop())


if __name__ == '__main__':
    unittest.main()