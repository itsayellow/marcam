"""Elapsed Timing functions for debugging purposes.
"""
# Copyright 2018 Matthew A. Clapp (modifications to original code)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import time


class ElTimer:
    def __init__(self):
        self.has_thread_time = hasattr(time, 'thread_time')
        self.reset()

    def reset(self):
        self.time_start = time.time()
        if self.has_thread_time:
            self.thread_time_start = time.thread_time()

    def eltime_s(self):
        return time.time() - self.time_start

    def thread_eltime_s(self):
        if self.has_thread_time:
            return time.thread_time() - self.thread_time_start
        else:
            return 0

    def eltime_ms(self):
        return 1000 * (time.time() - self.time_start)

    def thread_eltime_ms(self):
        if self.has_thread_time:
            return 1000 * (time.thread_time() - self.thread_time_start)
        else:
            return 0

    def log_ms(self, log_fxn, message, *args):
        message = message + "%.1fms"%(self.eltime_ms())
        if self.has_thread_time:
            message = message + " (thread: %.1fms)"%(self.thread_eltime_ms())
        log_fxn(message, *args)

    def print_ms(self, message, *args):
        message = message + "%.1fms"%(self.eltime_ms())
        if self.has_thread_time:
            message = message + " (thread: %.1fms)"%(self.thread_eltime_ms())
        print(message, *args)

    def log_s(self, log_fxn, message, *args):
        message = message + "%.1fs"%(self.eltime_s())
        if self.has_thread_time:
            message = message + " (thread: %.1fs)"%(self.thread_eltime_s())
        log_fxn(message, *args)

    def print_s(self, message, *args):
        message = message + "%.1fs"%(self.eltime_s())
        if self.has_thread_time:
            message = message + " (thread: %.1fs)"%(self.thread_eltime_s())
        print(message, *args)

    def log_thread_ms(self, log_fxn, message, *args):
        message = message + "(thread: %.1fms)"%(self.thread_eltime_ms())
        log_fxn(message, *args)

    def print_thread_ms(self, message, *args):
        message = message + "(thread: %.1fms)"%(self.thread_eltime_ms())
        print(message, *args)

    def log_thread_s(self, log_fxn, message, *args):
        message = message + "(thread: %.1fs)"%(self.thread_eltime_s())
        log_fxn(message, *args)

    def print_thread_s(self, message, *args):
        message = message + "(thread: %.1fs)"%(self.thread_eltime_s())
        print(message, *args)
