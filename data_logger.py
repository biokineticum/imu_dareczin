import os
from datetime import datetime

class DataLogger:
    def __init__(self, prefix="sesja_testowa"):
        self.prefix = prefix
        self.filename = None
        self.filepath = None
        self.file = None

    def start_session(self, directory=".", prefix=None):
        """
        Closes any existing session and starts a new logging CSV file.
        Returns the absolute file path of the created file.
        """
        self.stop_session()

        if prefix:
            self.prefix = prefix
        
        # Clean prefix to avoid invalid filename characters
        safe_prefix = "".join(c for c in self.prefix if c.isalnum() or c in (' ', '_', '-')).rstrip()
        safe_prefix = safe_prefix.replace(' ', '_')
        if not safe_prefix:
            safe_prefix = "data_session"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{safe_prefix}_{timestamp}.csv"
        self.filepath = os.path.abspath(os.path.join(directory, self.filename))
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
        # Open CSV file and write headers (Excel-friendly separator)
        self.file = open(self.filepath, "w", encoding="utf-8")
        self.file.write("Czas[s],X[g],Y[g],Z[g]\n")
        self.file.flush()
        return self.filepath

    def log_point(self, t, x, y, z):
        """Writes a single row of telemetry data to the file and flushes it."""
        if self.file and not self.file.closed:
            try:
                self.file.write(f"{t:.4f},{x:.4f},{y:.4f},{z:.4f}\n")
                self.file.flush()  # Flush immediately to avoid loss on crashes
            except Exception as e:
                print(f"Error writing to log file: {e}")

    def stop_session(self):
        """Closes the current log file session."""
        if self.file:
            try:
                self.file.close()
            except Exception:
                pass
            self.file = None
            
    def is_logging(self):
        """Returns True if there is an active logging session."""
        return self.file is not None
