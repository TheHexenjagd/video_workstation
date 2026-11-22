"""Thread-safe daily log file writer."""

from datetime import datetime
import os
import threading


class DailyLogger:
    """Append timestamped entries to a single daily `.log` file inside `logs_dir`."""

    def __init__(self, logs_dir):
        self.logs_dir = logs_dir
        self._lock = threading.Lock()

    def get_daily_path(self, date=None):
        now = date or datetime.now()
        return os.path.join(self.logs_dir, f"{now:%Y-%m-%d}.log")

    def write(self, message, separator=False):
        try:
            os.makedirs(self.logs_dir, exist_ok=True)
            now = datetime.now()
            log_path = self.get_daily_path(now)
            with self._lock:
                has_content = os.path.exists(log_path) and os.path.getsize(log_path) > 0
                with open(log_path, "a", encoding="utf-8") as log_file:
                    if separator:
                        if has_content:
                            log_file.write("\n")
                        log_file.write("=" * 80 + "\n")
                        log_file.write(f"SESIÓN: {now:%Y-%m-%d %H:%M:%S}  |  {message}\n")
                        log_file.write("=" * 80 + "\n")
                    else:
                        for line in str(message).splitlines() or [""]:
                            if line.startswith("  "):
                                log_file.write(f"           {line}\n")
                            else:
                                log_file.write(f"[{now:%H:%M:%S}] {line}\n")
        except Exception:
            pass
