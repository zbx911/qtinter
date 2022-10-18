"""Stopwatch implementation that does not use 'asyncslot'"""

import asyncio
import time
import qtinter
from PyQt6 import QtWidgets
from typing import Optional


class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.lcdNumber = QtWidgets.QLCDNumber()
        self.lcdNumber.setSmallDecimalPoint(True)

        self.startButton = QtWidgets.QPushButton()
        self.startButton.setText("START")
        self.startButton.clicked.connect(self._start)

        self.stopButton = QtWidgets.QPushButton()
        self.stopButton.setText("STOP")
        self.stopButton.clicked.connect(self._stop)
        self.stopButton.setEnabled(False)

        self.hBoxLayout = QtWidgets.QHBoxLayout()
        self.hBoxLayout.addWidget(self.startButton)
        self.hBoxLayout.addWidget(self.stopButton)

        self.vBoxLayout = QtWidgets.QVBoxLayout(self)
        self.vBoxLayout.addWidget(self.lcdNumber)
        self.vBoxLayout.addLayout(self.hBoxLayout)

        self.setWindowTitle("qtinter - Stopwatch example")

        self.task: Optional[asyncio.Task] = None

    def closeEvent(self, event):
        if self.task is not None and not self.task.done():
            self.task.cancel()
        event.accept()

    def _start(self):
        self.startButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.task = asyncio.create_task(self._tick())
        self.task.add_done_callback(self._stopped)

    def _stop(self):
        self.task.cancel()

    def _stopped(self, task: asyncio.Task):
        self.startButton.setEnabled(True)
        self.stopButton.setEnabled(False)

    async def _tick(self):
        t0 = time.time()
        while True:
            t = time.time()
            print(f"\r{self!r} {t - t0:.2f}", end="")
            self.lcdNumber.display(format(t - t0, ".1f"))
            await asyncio.sleep(0.05)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = MyWidget()
    widget.resize(300, 200)
    widget.show()

    with qtinter.using_asyncio_from_qt():  # <-- enclose in context manager
        app.exec()
