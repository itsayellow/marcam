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
    """Elapsed timing helper for debuging convenience.
    """
    def __init__(self):
        self.has_thread_time = hasattr(time, 'thread_time')
        self.reset()

    def reset(self):
        """Reset elapsed timer to 0
        """
        self.time_start = time.time()
        if self.has_thread_time:
            # pylint: disable=no-member
            self.thread_time_start = time.thread_time()

    def eltime_s(self):
        """Return elapsed time since __init__ or reset in seconds.

        Returns:
            float: elapsed time in seconds
        """
        return time.time() - self.time_start

    def thread_eltime_s(self):
        """Return elapsed thread_time since __init__ or reset in seconds.

        thread_time is cpu time spent in this thread only since reset.
        If thread_time is not available on this platform, return 0.

        Returns:
            float: elapsed time in seconds, or 0 if thread_time is
                unavailable.
        """
        if self.has_thread_time:
            # pylint: disable=no-member
            return time.thread_time() - self.thread_time_start
        else:
            return 0

    def eltime_ms(self):
        """Return elapsed time since __init__ or reset in milliseconds.

        Returns:
            float: elapsed time in milliseconds
        """
        return 1000 * (time.time() - self.time_start)

    def thread_eltime_ms(self):
        """Return elapsed thread_time since __init__ or reset in
        milliseconds.

        thread_time is cpu time spent in this thread only since reset.
        If thread_time is not available on this platform, return 0.

        Returns:
            float: elapsed time in milliseconds, or 0 if thread_time is
                unavailable.
        """
        if self.has_thread_time:
            # pylint: disable=no-member
            return 1000 * (time.thread_time() - self.thread_time_start)
        else:
            return 0

    def log_ms(self, log_fxn, message, *args):
        """Print a log message that ends in elapsed milliseconds string.

        If time.thread_time() is available, elapsed ms is followed by the
            string "(thread: <eltime>ms)" showing thread time only.

        Args:
            log_fxn (logging.{debug,info,warn,error}): logging function
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "%.1fms"%(self.eltime_ms())
        if self.has_thread_time:
            message = message + " (thread: %.1fms)"%(self.thread_eltime_ms())
        log_fxn(message, *args)

    def print_ms(self, message, *args):
        """Print a message to stdout that ends in elapsed milliseconds string.

        If time.thread_time() is available, elapsed ms is followed by the
            string "(thread: <eltime>ms)" showing thread time only.

        Args:
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "%.1fms"%(self.eltime_ms())
        if self.has_thread_time:
            message = message + " (thread: %.1fms)"%(self.thread_eltime_ms())
        print(message, *args)

    def log_s(self, log_fxn, message, *args):
        """Print a log message that ends in elapsed seconds string.

        If time.thread_time() is available, elapsed s is followed by the
            string "(thread: <eltime>s)" showing thread time only.

        Args:
            log_fxn (logging.{debug,info,warn,error}): logging function
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "%.1fs"%(self.eltime_s())
        if self.has_thread_time:
            message = message + " (thread: %.1fs)"%(self.thread_eltime_s())
        log_fxn(message, *args)

    def print_s(self, message, *args):
        """Print a message to stdout that ends in elapsed milliseconds string.

        If time.thread_time() is available, elapsed s is followed by the
            string "(thread: <eltime>s)" showing thread time only.

        Args:
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "%.1fs"%(self.eltime_s())
        if self.has_thread_time:
            message = message + " (thread: %.1fs)"%(self.thread_eltime_s())
        print(message, *args)

    def log_thread_ms(self, log_fxn, message, *args):
        """Print a log message that ends in: time elapsed in this thread
        in milliseconds string.

        If time.thread_time() is not available in this platform, thread time
            returned will always be 0ms.

        Args:
            log_fxn (logging.{debug,info,warn,error}): logging function
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "(thread: %.1fms)"%(self.thread_eltime_ms())
        log_fxn(message, *args)

    def print_thread_ms(self, message, *args):
        """Print a message to stdout that ends in: time elapsed in this
        thread in milliseconds string.

        If time.thread_time() is not available in this platform, thread time
            returned will always be 0ms.

        Args:
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "(thread: %.1fms)"%(self.thread_eltime_ms())
        print(message, *args)

    def log_thread_s(self, log_fxn, message, *args):
        """Print a log message that ends in: time elapsed in this thread
        in seconds string.

        If time.thread_time() is not available in this platform, thread time
            returned will always be 0s.

        Args:
            log_fxn (logging.{debug,info,warn,error}): logging function
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "(thread: %.1fs)"%(self.thread_eltime_s())
        log_fxn(message, *args)

    def print_thread_s(self, message, *args):
        """Print a message to stdout that ends in: time elapsed in this
        thread in seconds string.

        If time.thread_time() is not available in this platform, thread time
            returned will always be 0s.

        Args:
            message (str): string with possible string-format codes
            *args (str format objects): any objects of string-formatting in
                message.
        """
        message = message + "(thread: %.1fs)"%(self.thread_eltime_s())
        print(message, *args)
