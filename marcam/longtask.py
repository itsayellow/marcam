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


(myLongTaskDoneEvent, EVT_LONG_TASK_DONE) = wx.lib.newevent.NewEvent()


class LongTaskThreaded:
    """Class supporting long tasks that need to be in separate thread.

    Handles running the thread part of the task in a separate thread,
        wx Events, and wx ProgressDialog.
    """
    @debug_fxn
    def __init__(self, thread_fxn, thread_fxn_args, post_thread_fxn,
            progress_title, progress_msg, parent):
        """Initialize a Long Task needing thread execution and wx support.

        Args:
            thread_fxn (function handle): long-running function to be run in
                separate thread.  Return values from this function will
                be passed as positional arguments to post_thread_fxn.
            thread_fxn_args (tuple): arguments for thread_fxn
            post_thread_fxn (function handle): function that runs after
                thread_fxn has finished
            progress_title (str): Text for titlebar of wx.ProgressDialog
            progress_msg (str): Text for message area of wx.ProgressDialog
            parent (wx.Window): Window that handles events and is parent
                of ProgressDialog
        """

        self.thread_fxn = thread_fxn
        self.thread_fxn_args = thread_fxn_args
        self.post_thread_fxn = post_thread_fxn
        self.win_parent = parent
        self.thread_fxn_returnvals = None

        imageproc_thread = threading.Thread(
                target=self.long_task_thread,
                )
        self.win_parent.Bind(EVT_LONG_TASK_DONE, self.long_task_postthread)
        imageproc_thread.start()
        self.image_remap_dialog = wx.ProgressDialog(
                progress_title,
                progress_msg,
                parent=self.win_parent
                )
        # Pulse seems to only be needed to be called once!  Not multiple times
        #   as the docs imply.
        self.image_remap_dialog.Pulse()

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

        wx.PostEvent(self.win_parent, myLongTaskDoneEvent())

    @debug_fxn
    def long_task_postthread(self, evt):
        """Function triggered when event signifies that thread fxn is done.

        Args:
            evt (myLongTaskDoneEvent): obj returned from event when long task
                thread is finished
        """
        # On Windows especially, must Destroy progress dialog for application
        #   to continue
        self.image_remap_dialog.Destroy()
        # execute post thread function with return value(s) from thread_fxn
        self.post_thread_fxn(*self.thread_fxn_returnvals)
