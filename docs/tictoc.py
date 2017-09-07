import sys
import time
import datetime

class Timer:
    def __init__(self):
        self.start_time = time.time()

    def start(self):
        self.start_time = time.time()

    def eltime(self):
        return time.time() - self.start_time

    def eltime_pr(self, outstring, prfile=sys.stderr):
        eltime = time.time() - self.start_time
        elapsed = str(datetime.timedelta(seconds=eltime))
        print( outstring + elapsed, file=prfile )
