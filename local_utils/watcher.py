import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ResultFileHandler(FileSystemEventHandler):
    def __init__(self, filename: str, runner = None):
        self._filename = filename
        self._runner = runner

    def on_modified(self, event):
        if not event.is_directory and event.src_path == self._filename:
            self._runner.get_logger().debug(f"result file: {event.src_path} has been modified!")
            if self._runner is not None:
                self._runner.completed()

class ResultWatchdog():
    def __init__(self, filename: str, runner = None):
        self._handler = ResultFileHandler(filename, runner)
        self._dir = os.path.dirname(filename)
        if self._dir == "":
            self._dir = "."
        if not os.path.isdir(self._dir):
            raise ValueError(f"directory '{self._dir}' does not exist")
        self._observer = Observer()
        self._observer.schedule(self._handler, self._dir, recursive=False)

    def start(self):
        self._observer.start()
    def stop(self):
        self._observer.stop()
        self._observer.join()