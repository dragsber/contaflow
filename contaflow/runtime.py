import logging
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

from contaflow.store import data_directory


def log_exception(error, context, traceback=None):
    log_path = data_directory() / "contaflow.log"
    logger = logging.getLogger("contaflow")
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
    logger.error(context, exc_info=(type(error), error, traceback or error.__traceback__))
    return str(log_path)


def show_error(parent, title, user_message, error, context):
    log_path = log_exception(error, context)
    messagebox.showerror(
        title,
        f"{user_message}\n\nIl dettaglio tecnico è disponibile nel log locale:\n{log_path}",
        parent=parent,
    )
