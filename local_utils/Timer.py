from time import perf_counter

class TimerError(Exception):
    """Custom class for Timer exceptions"""


class Timer:
    """Timer to be used with context"""
    timers = {}

    def __init__(self,
                 name = None,
                 logger = None
                 ):
        self.name = name
        self.logger = logger
        self._start_time = None

        if name: # Create the entry for timer <name> in timers 
            self.timers.setdefault(self.name,0)

    def start(self) -> None:
        # Start a new timer
        if self._start_time is not None:
            raise TimerError(f"Timer is already running. Use .stop() to stop it")
        
        self._start_time = perf_counter()

    def stop(self):
        if self.name is None:
            raise TimerError(f"Timer is not running. Use .start() to start it")
        
        if self.name is None:
            raise TimerError(f"Timer is not running. Use .start() to start it")
        
        elapsed_time = perf_counter() - self._start_time
        
        if self.name:
            self.timers[self.name] = elapsed_time
    
    def __enter__(self):
        self.start()
        return(self)
    
    def __exit__(self, *exc_info):
        self.stop()
        if self.logger:
            self.logger.log(self.name,self.timers[self.name])

    


