# Loggers

class Logger:
    """ A Simple logger class"""
    def __init__(self):
        self._logs = {}
    
    def log(self,key,value):
        self._logs.setdefault(key,value)


