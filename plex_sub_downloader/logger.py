import logging

from logging.handlers import RotatingFileHandler

FILE = './plex-sub-downloader.log'
FILE_MAXSIZE = 10 * 1024 * 1024  # 10MB
FILE_BACKUP_CNT = 2
LOG_FORMAT = '%(asctime)s:%(module)s:%(levelname)s - %(message)s'
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class SingletonType(type):
    _instances = {}

    def getInstance(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = \
                    super(SingletonType, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(object, metaclass=SingletonType):
    # __metaclass__ = SingletonType   # python 2 Style

    def __init__(self, name='plex-sub-downloader', level=logging.INFO):

        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def enableDebug(self):
        self.logger.setLevel(logging.DEBUG)

    def setLevel(self, level):
        self.logger.setLevel(level)
        
    def getLogger(self):
        return self.logger
