import logging
import sqlite3
import tempfile
from pathlib import Path
from logging.handlers import RotatingFileHandler

from contaflow.store import data_directory


def log_exception(error, context, traceback=None, *, level=logging.ERROR):
    log_path = data_directory() / "contaflow.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("contaflow")
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
    logger.log(level, context, exc_info=(type(error), error, traceback or error.__traceback__))
    return str(log_path)


def log_startup_event(phase, error):
    """Keep exception messages and tracebacks out of exportable logs."""
    from db.migrations import MigrationError

    kind = ("migrazione/apertura" if isinstance(error, MigrationError) else
            "lettura SQLite" if isinstance(error, sqlite3.Error) else "errore applicativo")
    for directory in (data_directory(), Path(tempfile.gettempdir())):
        path = directory / "contaflow-avvio.log"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(path, maxBytes=128_000, backupCount=1, encoding="utf-8")
            try:
                handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                handler.handle(logging.LogRecord("contaflow", logging.ERROR, "", 0,
                                                 "%s: %s", (phase, kind), None))
            finally:
                handler.close()
            return str(path)
        except OSError:
            continue
    return "Log non disponibile"


def show_error(parent, title, user_message, error, context):
    from tkinter import messagebox

    log_path = log_exception(error, context)
    messagebox.showerror(
        title,
        f"{user_message}\n\nIl dettaglio tecnico è disponibile nel log locale:\n{log_path}",
        parent=parent,
    )
