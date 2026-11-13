"""Manage the isolated release check from the Qt event loop."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from .updates import WORKER_FLAG, version_key


TIMEOUT_MS = 8000


class UpdateCheck(QObject):
    finished = pyqtSignal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self._directory = None
        self._process = QProcess(self)
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process.kill)

    @staticmethod
    def _worker_arguments(destination):
        arguments = [WORKER_FLAG, str(destination)]
        if not getattr(sys, 'frozen', False):
            arguments.insert(0, str(Path(__file__).resolve().parents[1] / 'lomokino_gui.py'))
        return arguments

    def start(self):
        if self._directory is not None:
            return
        try:
            self._directory = TemporaryDirectory(prefix='lomokino-update-', ignore_cleanup_errors=True)
        except OSError:
            self.finished.emit(None)
            return
        self._timer.start(TIMEOUT_MS)
        destination = Path(self._directory.name) / 'tag'
        self._process.start(sys.executable, self._worker_arguments(destination))

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._process_finished(-1, QProcess.ExitStatus.CrashExit)

    def _process_finished(self, code, status):
        if self._directory is None:
            return
        self._timer.stop()
        directory, self._directory = self._directory, None
        tag = None
        with directory:
            if code == 0 and status == QProcess.ExitStatus.NormalExit:
                try:
                    candidate = (Path(directory.name) / 'tag').read_text(encoding='ascii')
                except (OSError, UnicodeError):
                    candidate = None
                if version_key(candidate) is not None:
                    tag = candidate
        self.finished.emit(tag)

    def stop(self):
        if self._directory is not None:
            self._process.kill()
            self._process.waitForFinished(1000)
