# Loggers

class Logger:
    """ A Simple logger class"""
    def __init__(self):
        self._logs = {}
    
    def log(self,key,value):
        self._logs.setdefault(key,value)

class StatusLogger:
    def __init__(self, multi_config: dict, status_file: str):
        self._status_file = status_file


