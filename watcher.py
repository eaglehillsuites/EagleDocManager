"""
Watcher - Background folder watcher using watchdog.
Monitors configured folders and triggers processing on new PDFs.
"""

import time
import threading
from pathlib import Path
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent


class PDFHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str], None], exceptions: list[str]):
        super().__init__()
        self.callback = callback
        self.exceptions = exceptions
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_process(self, path: str) -> bool:
        if not path.lower().endswith(".pdf"):
            return False
        filename = Path(path).name
        for exc in self.exceptions:
            if exc.lower() in filename.lower():
                return False
        # Don't process files in Archive subdirectory
        if "Archive" in path:
            return False
        # Don't process audit log
        if "eagle_doc_audit" in filename.lower():
            return False
        return True

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._schedule(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and self._should_process(event.dest_path):
            self._schedule(event.dest_path)

    def _schedule(self, path: str):
        """Wait for file to finish writing before processing."""
        def wait_and_process():
            prev_size = -1
            for _ in range(20):  # Wait up to 10 seconds
                try:
                    size = Path(path).stat().st_size
                    if size == prev_size and size > 0:
                        break
                    prev_size = size
                except Exception:
                    pass
                time.sleep(0.5)
            self.callback(path)

        thread = threading.Thread(target=wait_and_process, daemon=True)
        thread.start()


class FolderWatcher:
    """
    Watches one or more folders for new PDF files.
    
    Usage:
        watcher = FolderWatcher(on_new_file=my_handler, exceptions=["ignore_this"])
        watcher.add_folder("/path/to/folder")
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(self, on_new_file: Callable[[str], None],
                 exceptions: Optional[list[str]] = None):
        self.on_new_file = on_new_file
        self.exceptions = exceptions or []
        self._observer: Optional[Observer] = None
        self._running = False
        self._watched_folders: list[str] = []

    def add_folder(self, folder_path: str):
        if folder_path not in self._watched_folders:
            self._watched_folders.append(folder_path)
            # If already running, add watch dynamically
            if self._running and self._observer:
                handler = PDFHandler(self.on_new_file, self.exceptions)
                self._observer.schedule(handler, folder_path, recursive=False)

    def remove_folder(self, folder_path: str):
        if folder_path in self._watched_folders:
            self._watched_folders.remove(folder_path)
            # Restart observer to apply change
            if self._running:
                self.stop()
                self.start()

    def set_folders(self, folders: list[str]):
        self._watched_folders = list(folders)
        if self._running:
            self.stop()
            self.start()

    def set_exceptions(self, exceptions: list[str]):
        self.exceptions = exceptions

    def start(self):
        if self._running:
            return

        if not self._watched_folders:
            return

        self._observer = Observer()
        handler = PDFHandler(self.on_new_file, self.exceptions)

        for folder in self._watched_folders:
            if Path(folder).exists():
                self._observer.schedule(handler, folder, recursive=False)

        self._observer.start()
        self._running = True

    def stop(self):
        if self._running and self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._running = False

    def pause(self):
        self.stop()

    def resume(self):
        self.start()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_folders(self) -> list[str]:
        return list(self._watched_folders)
