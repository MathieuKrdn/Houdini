import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from PySide2 import QtCore

# WORKER Signal
class WorkerSignals(QtCore.QObject):
    """
    Define signals for the worker thread.
    - scan_complete: Emits total file count after scanning.
    - progress_update: Emits the number of files converted so far.
    - status_update: Emits a string for the status label ui.
    - finished: Signals the entire process is done.
    """
    scan_complete = QtCore.Signal(int)
    progress_update = QtCore.Signal(int)
    status_update = QtCore.Signal(str)
    finished = QtCore.Signal()


# WORKER
class RatConversionWorker(QtCore.QObject):
    def __init__(self, folder, use_subfolders, max_workers):
        super(RatConversionWorker, self).__init__()
        self.signals = WorkerSignals()
        self.folder = folder
        self.use_subfolders = use_subfolders
        self.max_workers = max_workers
        self.is_cancelled = False

    @QtCore.Slot()
    def run(self):
        # Scan root and return the number of files
        self.signals.status_update.emit("Scanning for image files...")
        image_files = self._find_files()
        total_files = len(image_files)
        self.signals.scan_complete.emit(total_files)

        if self.is_cancelled:
            self.signals.finished.emit()
            return
            
        if not image_files:
            self.signals.status_update.emit("No new image files found to convert.")
            time.sleep(1.5)
            self.signals.finished.emit()
            return

        # STAGE 2: Convert files and report progress for each one.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # enumerate the count of completed tasks
            for i, _ in enumerate(executor.map(self._convert_single_file, image_files)):
                if self.is_cancelled:
                    self.signals.status_update.emit(f"Cancelled. Processed {i} of {total_files} files.")
                    break
                # number of files done
                self.signals.progress_update.emit(i + 1)
        
        if not self.is_cancelled:
            self.signals.status_update.emit(f"Successfully converted {total_files} files.")
        
        time.sleep(1.5)
        self.signals.finished.emit()

    def _find_files(self):
        # find files based on extension (with or without subfolder process)
        valid_extensions = (".exr", ".tif", ".tiff", ".png", ".jpg", ".jpeg")
        files_to_process = []
        if self.use_subfolders:
            for root, _, files in os.walk(self.folder):
                for f in files:
                    if f.lower().endswith(valid_extensions):
                        files_to_process.append(os.path.join(root, f))
        else:
            for f in os.listdir(self.folder):
                path = os.path.join(self.folder, f)
                if os.path.isfile(path) and f.lower().endswith(valid_extensions):
                    files_to_process.append(path)
        return files_to_process

    def _convert_single_file(self, image_path):
        # convert process
        if self.is_cancelled:
            return
        base_name = os.path.basename(image_path)
        self.signals.status_update.emit(f"Converting: {base_name}")
        rat_path = f"{os.path.splitext(image_path)[0]}.rat"
        cmd = ["iconvert", image_path, rat_path]
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run(cmd, check=True, creationflags=creation_flags, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Error converting {base_name}: {e.stderr}")
        except FileNotFoundError:
            self.signals.status_update.emit("'iconvert' not found")
            self.is_cancelled = True