"""Module to facilitate a generic interface to running long tasks in separate
    threads.
"""
# Copyright 2018 Matthew A. Clapp
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

import logging
import threading

import wx

import common


# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug, common.DEBUG_FXN_STATE)


class Threaded:
    """Class supporting long tasks that need to be in separate thread.

    Handles running the thread part of the task in a separate thread,
        and wx Events needed to invoke post-thread actions.
    """
    @debug_fxn
    def __init__(self, thread_fxn, thread_fxn_args, post_thread_fxn, parent):
        """Initialize a Long Task needing thread execution and wx support.

        Args:
            thread_fxn (function handle): long-running function to be run in
                separate thread.  Return values from this function will
                be passed as positional arguments to post_thread_fxn.
            thread_fxn_args (tuple): arguments for thread_fxn
            post_thread_fxn (function handle): function that runs after
                thread_fxn has finished
            parent (wx.Window): Window that handles events and is parent
                of ProgressDialog
        """

        self.thread_fxn = thread_fxn
        self.thread_fxn_args = thread_fxn_args
        self.post_thread_fxn = post_thread_fxn
        self.win_parent = parent
        self.thread_fxn_returnvals = None

        # We could normally omit events altogether if post_thread_fxn is None,
        #   but we'll keep these in in case a derived class needs the machinery
        # NOTE: IT MIGHT BE that binding an event to self.long_task_postthread
        #   prevents this class instance from being deleted if the calling code
        #   goes out of scope.  (??)

        # get new Event and EventBinder for this instance only
        (self.myLongTaskDoneEvent, evt_long_task_done) = wx.lib.newevent.NewEvent()
        # bind postthread function to "done" event
        self.win_parent.Bind(evt_long_task_done, self.long_task_postthread)

        # build thread
        task_thread = threading.Thread(
                target=self.long_task_thread,
                )
        # Start task thread computing.
        # Do this last, so that if it ends super fast we are not trying to
        #   still do things with self.progress_dialog after long_task_postthread
        #   Destroys the dialog.
        task_thread.start()

    @debug_fxn
    def long_task_thread(self):
        """Function that is run in separate thread

        If thread_fxn returns any values, they will be passed as positional
        arguments to post_thread_fxn.
        """
        thread_fxn_returnvals = self.thread_fxn(*self.thread_fxn_args)
        if thread_fxn_returnvals is None:
            # if returnvals = None, make empty tuple
            self.thread_fxn_returnvals = ()
        else:
            try:
                # if returnvals are iterable, convert to tuple
                self.thread_fxn_returnvals = tuple(thread_fxn_returnvals)
            except TypeError:
                # if returnvals are single value, wrap in tuple
                self.thread_fxn_returnvals = (thread_fxn_returnvals,)

        wx.PostEvent(self.win_parent, self.myLongTaskDoneEvent())

    @debug_fxn
    def long_task_postthread(self, _evt):
        """Function triggered when event signifies that thread fxn is done.

        Args:
            evt (self.myLongTaskDoneEvent): obj returned from event when long task
                thread is finished
        """
        # if it exists, execute post thread function with return value(s)
        #   from thread_fxn
        if self.post_thread_fxn is not None:
            self.post_thread_fxn(*self.thread_fxn_returnvals)


class ThreadedProgressPulse(Threaded):
    """Class supporting long tasks that need to be in separate thread.

    Handles running the thread part of the task in a separate thread,
        wx Events needed to invoke post-thread actions, and wx ProgressDialog.
        Sets ProgressDialog to "Pulse" mode, which shows indeterminant progress
        (just activity).
    """
    @debug_fxn
    def __init__(self, thread_fxn, thread_fxn_args, post_thread_fxn,
            progress_title, progress_msg, parent):
        self.win_parent = parent
        self.thread_fxn_returnvals = None

        self.progress_dialog = wx.ProgressDialog(
                progress_title,
                progress_msg,
                parent=self.win_parent
                )
        # Pulse seems to only be needed to be called once!  Not multiple times
        #   as the docs imply.
        self.progress_dialog.Pulse()
        # invoke thread stuff after setting up progress_dialog, so thread
        #   ending and post-thread destroying progress_dialog is impossible
        #   to come first
        super().__init__(thread_fxn, thread_fxn_args, post_thread_fxn, parent)

    @debug_fxn
    def long_task_postthread(self, _evt):
        """Function triggered when event signifies that thread fxn is done.

        Args:
            evt (self.myLongTaskDoneEvent): obj returned from event when long task
                thread is finished
        """
        # On Windows especially, must Destroy progress dialog for application
        #   to continue
        self.progress_dialog.Destroy()
        # execute post thread function with return value(s) from thread_fxn
        super().long_task_postthread(_evt)


class ThreadedDisableEnable(Threaded):
    """Class supporting long tasks that need to be in separate thread.

    Handles running the thread part of the task in a separate thread,
        wx Events needed to invoke post-thread actions, and wx ProgressDialog.
        Sets ProgressDialog to "Pulse" mode, which shows indeterminant progress
        (just activity).
    """
    @debug_fxn
    def __init__(self, thread_fxn, thread_fxn_args, post_thread_fxn,
            progress_title, progress_msg, parent):
        self.win_parent = parent
        self.thread_fxn_returnvals = None

        # Disable access to parent window
        self.win_parent.Enable(False)

        # invoke thread stuff after Disabling parent window, so there's no
        #   chance it can happen after post-thread stuff
        super().__init__(thread_fxn, thread_fxn_args, post_thread_fxn, parent)

    @debug_fxn
    def long_task_postthread(self, _evt):
        """Function triggered when event signifies that thread fxn is done.

        Args:
            evt (self.myLongTaskDoneEvent): obj returned from event when long task
                thread is finished
        """
        # Re-enable access to parent window
        self.win_parent.Enable(True)

        # execute post thread function with return value(s) from thread_fxn
        super().long_task_postthread(_evt)
