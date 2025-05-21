import logging
import queue

class QueueHandler(logging.Handler):
    """Manda cada mensaje de log a una queue para la GUI."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

def setup_logging(log_file: str = 'ytube.log', log_queue: queue.Queue = None) -> logging.Logger:
    """
    Configura un logger único para toda la app.
    Si ya existe, devuelve el mismo.
    """
    logger = logging.getLogger('YouTubeManager')
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = '%(asctime)s [%(levelname)s] %(message)s'
    formatter = logging.Formatter(fmt)

    # Handler a archivo
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Handler a queue para GUI
    if log_queue:
        qh = QueueHandler(log_queue)
        qh.setLevel(logging.INFO)
        qh.setFormatter(formatter)
        logger.addHandler(qh)

    return logger
