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
    @debug_fxn
    def __init__(self, thread_fxn, thread_fxn_args, post_thread_fxn, post_thread_fxn_args,
            progress_title, progress_msg, parent):

        self.post_thread_fxn = post_thread_fxn
        self.post_thread_fxn_args = post_thread_fxn_args
        self.thread_fxn = thread_fxn
        self.thread_fxn_args = thread_fxn_args
        self.win_parent = parent

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
        # for some reason this pulsing thing causes Segmentation faults
        #   race condition??
        #wx.CallAfter(self.pulse_image_remap_dialog)

    @debug_fxn
    def long_task_postthread(self, evt):
        # On Windows especially, must Destroy progress dialog for application
        #   to continue
        self.image_remap_dialog.Destroy()
        # execute post thread function
        self.post_thread_fxn(*self.post_thread_fxn_args)

    def long_task_thread(self):
        self.thread_fxn(*self.thread_fxn_args)
        wx.PostEvent(self.win_parent, myLongTaskDoneEvent())

    def pulse_image_remap_dialog(self):
        if self.image_remap_dialog_keep_pulsing:
            self.image_remap_dialog.Pulse()
            wx.CallLater(100, self.pulse_image_remap_dialog)
        else:
            pass
            #print("image_remap_dialog done (max value)")


