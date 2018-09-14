#!/usr/bin/env python3
"""Top-level module to run to run the Marcam application
"""

# Copyright 2017-2018 Matthew A. Clapp
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

# GUI for displaying an image and counting cells


import argparse
import json
import logging
import pathlib
import platform
import sys
import threading
import time

import wx
import wx.adv
import wx.lib.dialogs
import wx.lib.newevent

import image_proc
from marcam_image_frame import ImageFrame
import const
import common
import marcam_extra
import mcmfile
if const.PLATFORM == 'win':
    import winpipe


# DEBUG defaults to False.  Is set to True if debug switch found
DEBUG = False
# Placeholder.  This is set in another_instance_running()
SINGLEINST_INSTANCE = None

# which modules are we logging
LOGGED_MODULES = [
        __name__, 'common', 'image_proc', 'image_scrolled_canvas',
        'image_scrolled_canvas_marks', 'longtask', 'marcam_image_frame',
        'marcam_extra', 'mcmfile', 'winpipe'
        ]

# global logger obj for this file
LOGGER = logging.getLogger(__name__)

LOGGER.info("MSC:ICON_DIR=%s", const.ICON_DIR)

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)


WIN_FILE_PIPE_NAME = r"\\.\pipe\Marcam" + "-%s"%wx.GetUserId()

(myWinFileEvent, EVT_WIN_FILE) = wx.lib.newevent.NewEvent()


@debug_fxn
def can_read_image(image_path):
    """Detect if this image is readable by this program.

    Detects any readable plain image file, or .mcm file.

    Args:
        image_path (pathlike): path to image to check if readable

    Returns:
        bool: True if image is readable by wx.Image()
    """
    image_path = pathlib.Path(image_path)

    if mcmfile.is_valid(image_path):
        img_ok = True
    elif image_path.suffix == ".1sc":
        img_ok = bool(image_proc.file1sc_to_image(image_path))
    else:
        # for all other image files
        # wx.Image.CanRead has its own error log, which is setup to cause
        #   error dialog.  Disable it if because want to use our own
        no_log = wx.LogNull()
        img_ok = wx.Image.CanRead(str(image_path))
        # re-enable logging
        del no_log

    return img_ok

@debug_fxn
def logging_setup(log_level=logging.DEBUG):
    """Setup logging for all logged modules

    Args:
        log_level (logging.LOG_LEVEL): log level for all modules from logging
    """

    # create formatter
    formatter = marcam_extra.MarcamFormatter(
            "%(asctime)s:%(name)s:%(levelname)s:\n%(message)s",
            add_terminator=True
            )

    # make sure log file dir exists
    const.USER_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # canonical logfile full path
    logfile_name = 'marcam.log'
    logfile_path = const.USER_LOG_DIR / logfile_name

    # rename all old log files
    #   (log.txt.2 -> log.txt.3, log.txt.1 -> log.txt.2, log.txt -> log.txt.1
    num_logfile_hist = 10
    for i in range(num_logfile_hist-1, -1, -1):
        fname = const.USER_LOG_DIR / (logfile_name + (".%d"%i if i != 0 else ""))
        fname_plus_1 = const.USER_LOG_DIR / (logfile_name + ".%d"%(i+1))
        if fname.exists():
            fname.replace(fname_plus_1)

    # file handler
    file_handler = logging.FileHandler(str(logfile_path))
    # don't automatically add \n to end of log messages, we will do that
    #   conditionally in MarcamFormatter
    file_handler.terminator = ''
    file_handler.setLevel(log_level)
    # add global formatter to file handler
    file_handler.setFormatter(formatter)

    for logger_name in LOGGED_MODULES:
        logging.getLogger(logger_name).setLevel(log_level)
        logging.getLogger(logger_name).addHandler(file_handler)

    # inform log of the global log level
    log_eff_level = LOGGER.getEffectiveLevel()
    LOGGER.log(
            log_eff_level,
            "Global log level set to %s", logging.getLevelName(log_eff_level)
            )


# NOTE: closing window saves size, opening new window uses saved size
class MarcamApp(wx.App):
    """Main Marcam application wx.App

    Handles key bindings, Frame management, OS interaction, startup, shutdown.
    """
    @debug_fxn
    def __init__(self, open_files, *args, **kwargs):
        """
        Args:
            open_files (list of pathlike): files to open as startup occurs
        """
        # reset this before calling super().__init__(), which calls
        #   MacOpenFiles()
        self.file_windows = marcam_extra.FrameList()
        self.config_data = None
        self.last_frame_pos = wx.DefaultPosition
        self.last_falsecolor = 'viridis'
        self.last_autocontrast_level = 0

        # may call MacOpenFiles and add files to self.file_windows and make
        #   new frames
        super().__init__(*args, **kwargs)

        # App configuration
        # Must be called after wx.App initialized with super().__init__()
        self.wx_config = wx.Config("Marcam", "itsayellow.com")
        self.read_config()

        # File history
        self.file_history = marcam_extra.FileHistory()
        self.file_history.Load(self.wx_config)

        # this next statement can only be after calling __init__ of wx.App
        # gives just window-placeable screen area
        self.display_size = wx.Display().GetClientArea().GetSize()

        for open_filename in open_files:
            # Will open error dialog if file is unreadable.
            self.new_frame_open_file(open_filename)

        # if after giving chances to open files from command-line, OS events,
        #   etc., we still don't have any open frames, open an empty one
        #   on startup
        if self.file_windows.has_zero():
            # Open an empty frame.
            # Will open error dialog if file is unreadable.
            self.new_frame_open_file(None)

        # binding to App is surest way to catch keys accurately, not having
        #   to worry about which widget has focus
        # binding to a frame or panel can end up it not having focus,
        #   just donk, donk, donk bell sounds
        # The reason is because a Panel will not accept focus if it has a child
        #   window that can accept focus
        #   wx.Panel.SetFocus: "In practice, if you call this method and the
        #   control has at least one child window, the focus will be given to the
        #   child window."
        #   (see wx.Panel.AcceptsFocus, wx.Panel.SetFocus,
        #   wx.Panel.SetFocusIgnoringChildren)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_UP, self.on_key_up)

        # Since we're the master instance, on Windows startup a thread to field
        #   requests from possible other instances that run just long enough to
        #   request file(s) be opened by us.
        if const.PLATFORM == 'win':
            win_file_thread = threading.Thread(
                    target=win_file_receiver,
                    args=(self,),
                    daemon=True,
                    )
            win_file_thread.start()
            self.Bind(EVT_WIN_FILE, self.on_evt_win_file)

    def set_last_autocontrast_level(self, level=0):
        """Set "last autocontrast" menuitem in all windows with given level

        Args:
            level (integer): auto-contrast level
        """
        self.last_autocontrast_level = level

        for frame in self.file_windows.get_list_copy():
            key_accel = frame.tools_imgautocontrastlast_item.GetItemLabel().split('\t')[1]
            frame.tools_imgautocontrastlast_item.SetItemLabel(
                    "Image &Auto-Contrast (%d)\t%s"%(
                        self.get_last_autocontrast_level(),
                        key_accel
                        )
                    )

    def get_last_autocontrast_level(self):
        """Get "last autocontrast" level used in any window for Auto-Contrast
            image operation.

        Returns:
            (integer): auto-contrast level last used in any window
        """
        return self.last_autocontrast_level

    def set_last_falsecolor(self, cmap="viridis"):
        """Set "last false color" menuitem in all windows with given colormap

        Args:
            cmap (str): string (lower-case) representing the colormap
        """
        self.last_falsecolor = cmap

        for frame in self.file_windows.get_list_copy():
            key_accel = frame.tools_imgfcolorlast_item.GetItemLabel().split('\t')[1]
            frame.tools_imgfcolorlast_item.SetItemLabel(
                    "Image False Color (%s)\t%s"%(
                        self.get_last_falsecolor().capitalize(),
                        key_accel
                        )
                    )

    def get_last_falsecolor(self):
        """Get "last false color" colormap used in any window for False Color
            image operation.

        Returns:
            (str): string (lower-case) representing the colormap
        """
        return self.last_falsecolor

    def on_evt_win_file(self, evt):
        """Event handler for our custom Event receiving Windows file open
            events from other application instances.

        Args:
            evt (wx.Event): event object having attribute with filename to open.
        """
        LOGGER.info("Event received: %s", evt.open_filename)
        self.open_file(evt.open_filename)

    def on_key_down(self, evt):
        """Event handler for any key down event in the Application. Calls
        on_key_down of the frame that is active.

        Args:
            evt (wx.KeyEvent):
        """
        active_frame = self.file_windows.active_frame()
        if active_frame is not None:
            active_frame.on_key_down(evt)
        else:
            evt.Skip()

    def on_key_up(self, evt):
        """Event handler for any key up event in the Application.  Calls
        on_key_up of the frame that is active.

        Args:
            evt (wx.KeyEvent):
        """
        active_frame = self.file_windows.active_frame()
        if active_frame is not None:
            active_frame.on_key_up(evt)
        else:
            evt.Skip()

    @debug_fxn
    def shutdown_frame(self, frame_to_close_id, force_close=False,
            from_close_menu=False, from_quit_menu=False):
        """
        Args:
            frame_to_close_id: window id of frame to close
            force_close: True if we must close frame no matter what
            from_close_menu: origin of CloseEvt was File->Close
            from_quit_menu: origin of CloseEvt was File->Quit

        Returns:
            bool: Whether caller should veto closing of this window
        """
        # if force_close:
        #   self.file_windows.remove(frame)
        #   close_window = True
        # else:
        #   if len(self.file_windows) > 1:
        #       if image_closed:
        #           self.file_windows.remove(frame)
        #           close_window = True
        #       else:
        #           close_window = False
        #   else:
        #       if not image_closed:
        #           close_window = False
        #       else:
        #           if from_quit_menu:
        #               self.file_windows.remove(frame)
        #               close_window = True
        #           elif from_close_menu:
        #               if const.PLATFORM == 'mac':
        #                   frame.Hide()
        #               close_window = False
        #           else:
        #               if const.PLATFORM == 'mac':
        #                   frame.Hide()
        #                   close_window = False
        #               else:
        #                   self.file_windows.remove(frame)
        #                   close_window = True

        frame_to_close = self.file_windows.frame_from_id(frame_to_close_id)

        # keep_win_open tells close_image() if it should reset the frame's
        #   settings if it successfully closes the image (in anticipation of
        #   keeping the frame open).
        # Logic is identical to (not close_window) with image_closed=True
        # Strictly speaking there is no problem with this being True always,
        #   except that it might possibly take more time.
        keep_win_open = not (
                force_close or
                self.file_windows.has_multiple() or
                (self.file_windows.has_one() and from_quit_menu) or
                (
                    self.file_windows.has_one() and
                    not from_quit_menu and
                    not from_close_menu and
                    const.PLATFORM != 'mac'
                    )
                )

        # close_image checks to see if there are unsaved changes, and if there
        #   is, asks the user if the user wants to save, or cancel window close
        # image_closed is False if user clicked "Cancel" when asked to save
        #   otherwise it is True
        image_closed = frame_to_close.close_image(keep_win_open=keep_win_open)

        # this tells whether we should continue in the process of closing window
        #   after the return of this function
        close_window = (
                force_close or
                (self.file_windows.has_multiple() and image_closed) or
                (self.file_windows.has_one() and image_closed and from_quit_menu) or
                (
                    self.file_windows.has_one() and
                    image_closed and
                    not from_quit_menu and
                    not from_close_menu and
                    const.PLATFORM != 'mac'
                    )
                )

        # on Mac, which conditions cause the last window to stay open and hid
        hide_window = (
            not force_close and
            self.file_windows.has_one() and
            image_closed and
            not from_quit_menu and
            (const.PLATFORM == 'mac')
        )

        # if hide_window is True, close_window must also be False
        assert (hide_window and not close_window) or not hide_window

        if close_window:
            self.file_windows.remove_id(frame_to_close_id)
            self.file_history.RemoveMenu(frame_to_close.open_recent_menu)

        if hide_window:
            # on Mac we hide the last frame we close.
            frame_to_close.Hide()

        veto_close = not close_window

        return veto_close

    @debug_fxn
    def new_frame_open_file(self, open_filename):
        """Open specified file in new frame

        Will open an error dialog if file is unreadable.

        Args:
            open_filename (pathlike or None): filename to open in new frame
        """
        if open_filename is not None:
            open_filename = pathlib.Path(open_filename)

            already_open_frame = self.file_windows.frame_with_file(open_filename)
            if already_open_frame:
                # Already have a frame with that file open, don't open a dup
                #   just move it to front
                already_open_frame.activate()
                # our image is already open in a frame, so return early
                return
            else:
                # verify ok image before opening new frame
                img_ok = can_read_image(open_filename)
        else:
            # force img_ok to True if open_filename is None
            # we are trying to force a new empty window open (application init)
            img_ok = True

        if img_ok:
            new_size = wx.Size(self.config_data['winsize'])
            if self.last_frame_pos == wx.DefaultPosition:
                new_pos = self.last_frame_pos
            else:
                new_pos = wx.Point(
                        self.last_frame_pos.x + const.NEW_FRAME_OFFSET,
                        self.last_frame_pos.y + const.NEW_FRAME_OFFSET
                        )
                x_too_big = new_pos.x + new_size.x > self.display_size.x
                y_too_big = new_pos.y + new_size.y > self.display_size.y
                if x_too_big and y_too_big:
                    new_pos = wx.DefaultPosition
                elif x_too_big:
                    new_pos.x = 0
                elif y_too_big:
                    new_pos.y = 0
            new_frame = ImageFrame(
                    self,
                    size=new_size,
                    pos=new_pos
                    )
            self.file_windows.append(new_frame)
            if open_filename is not None:
                # Will open error dialog if file is unreadable.
                new_frame.open_image_this_frame(open_filename)
            # need to actually GetPosition to get real position, in case both
            #   self.last_frame_pos = (-1, -1) and new_pos = (-1, -1)
            self.last_frame_pos = new_frame.GetPosition()
        else:
            marcam_extra.file_unable_to_open_dialog(None, open_filename)

    @debug_fxn
    def quit_app(self):
        """Quit App by closing every single frame.

        When all frames are closed, wx automatically shuts down App.
        If Cancel is ever clicked and frame is not closed, then quit process
            aborts.
        """
        # we need to copy this because frame.Close() will end up modifying
        #   self.file_windows, which will corrupt the loop in progress
        for frame in self.file_windows.get_list_copy():
            frame.close_source = 'quit_menu'
            frame_closed = frame.Close()
            if not frame_closed:
                break

    @debug_fxn
    def MacOpenFiles(self, file_names):
        """wx.PyApp standard function to accept Cocoa "openFiles" events.
        Over-ridden to process files.

        Args:
            file_names: list of (str) file names to open
        """
        # NOTE: works great in bundled app,
        #   but cmd-line invocation causes sends last argument of command-line
        #   to this function, even if that's the script name.

        if self.config_data is None:
            # No config_data means we are starting up app.  In this case,
            #   check if MacOpenFiles is just giving us args from sys.argv.
            # If one or more file_names are in sys.argv, then it will be
            #   processed by the main __init__ and we don't need to process
            #   it here.
            # This should also protect us against receiving the script name
            #   as a filename to MacOpenFiles (which happens when starting
            #   from the command-line).
            LOGGER.debug("Before sys.argv pruning: %s", str(file_names))
            # Use list(enumerate()) to make a copy, so when we pop values
            #   there's no generator to get screwed up.
            for (i, filename) in list(enumerate(file_names)):
                if filename in sys.argv:
                    file_names.pop(i)
            LOGGER.debug("After sys.argv pruning: %s", str(file_names))

            if file_names:
                # if we haven't set up config yet, schedule this to be run after
                #   we finish setting up
                LOGGER.debug("Postponing MacOpenFiles until we have config_data.")
                wx.CallAfter(self.MacOpenFiles, file_names)
            else:
                # No file_names left after pruning, so just cancel
                LOGGER.debug("Canceling MacOpenFiles because all files are from sys.argv.")
            return

        LOGGER.debug(file_names)
        for open_filename in file_names:
            self.open_file(open_filename)

    @debug_fxn
    def open_file(self, open_filename):
        """Open specified filename in either this frame or new frame

        Args:
            open_filename (pathlike): image filename to open
        """
        # open in blank window, or
        #   add to file_windows list of file windows
        if self.file_windows.has_zero() or self.file_windows.all_have_image():
            # Will open error dialog if file is unreadable.
            self.new_frame_open_file(open_filename)
        else:
            # only one frame, and it has no image
            # Will open error dialog if file is unreadable.
            self.file_windows.only_frame().open_image_this_frame(open_filename)

    @debug_fxn
    def read_config(self):
        """Load config--from file if present or else defaults.  Create config file
            with default config data if one is not present.
        """
        # initialize dict
        self.config_data = {}

        # winsize
        self.config_data['winsize'] = json.loads(
                self.wx_config.Read(
                    'winsize',
                    defaultVal=json.dumps([800, 600])
                    )
                )

        # debug
        self.config_data['debug'] = self.wx_config.ReadBool(
                'debug',
                defaultVal=False
                )

    @debug_fxn
    def write_config(self):
        """Load config--from file if present or else defaults.  Create config file
            with default config data if one is not present.
        """
        # winsize
        self.wx_config.Write(
                'winsize',
                json.dumps(self.config_data['winsize'])
                )

        # debug
        self.wx_config.WriteBool(
                'debug',
                self.config_data['debug']
                )

    def OnExit(self):
        """Overloaded function that is called before App finally exits

        "wx.AppConsole.OnExit which is called when the application exits but
        before wxPython cleans up its internal structures."

        Returns:
            Whatever AppConsole.OnExit() returns
        """
        # save file_history on quit
        self.file_history.Save(self.wx_config)
        # save config_data right before app is about to exit
        self.write_config()
        return super().OnExit()


def process_command_line(argv):
    """Process command line invocation arguments and switches.

    Args:
        argv: list of arguments, or `None` from ``sys.argv[1:]``.

    Returns:
        args: Namespace with named attributes of arguments and switches
    """
    #script_name = argv[0]
    argv = argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(
            description="View images of cells, and allow for counting of them.")

    # specifying nargs= puts outputs of parser in list (even if nargs=1)

    # positional arguments
    parser.add_argument('srcfiles', nargs='*',
            help="Source files to open on startup."
            )

    # switches/options:
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Enable debugging messages to console'
        )

    #(settings, args) = parser.parse_args(argv)
    args = parser.parse_args(argv)

    return args

def log_debug_main():
    """Log basic system information
    """
    # log situation before doing anything else
    LOGGER.info("%s UTC", time.asctime(time.gmtime()))
    LOGGER.info("Marcam version %s", const.VERSION_STR)
    # os.uname doesn't work on Windows (platform.uname more portable)
    uname_obj = platform.uname()
    log_string = "platform.uname" + "\n"
    log_string += "    system:" + uname_obj.system + "\n"
    log_string += "    node:" + uname_obj.node + "\n"
    log_string += "    release:" + uname_obj.release + "\n"
    log_string += "    version:" + uname_obj.version + "\n"
    log_string += "    machine:" + uname_obj.machine + "\n"
    log_string += "    processor:" + uname_obj.processor
    LOGGER.info(log_string)
    log_string = "Python info" + "\n"
    log_string += "    python:" + sys.version.replace('\n', '') + "\n"
    log_string += "    wxPython:" + wx.__version__
    LOGGER.info(log_string)
    LOGGER.info("sys.argv:%s", repr(sys.argv))

def another_instance_running(srcfile_args):
    """Check if another instance of app is running, process open file arguments
        on Windows if they are present.

    Args:
        srcfile_args (list): list of files to open in main App instance.
            (Only applies to Windows as MacOpenFiles in main instance receives
            files to open in Mac without trying to start new App.)

    Returns:
        (bool): True if another instance of Marcam is already running for this
            user, False otherwise.
    """
    # make global to persist until app is closed
    global SINGLEINST_INSTANCE
    singleinst_name = "Marcam-%s"%wx.GetUserId()
    const.USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SINGLEINST_INSTANCE = wx.SingleInstanceChecker(
            singleinst_name,
            str(const.USER_CONFIG_DIR),
            )
    another_inst = SINGLEINST_INSTANCE.IsAnotherRunning()
    if another_inst and srcfile_args:
        # send our filename arguments to other instance running via Windows
        #   named pipe
        if const.PLATFORM == 'win':
            did_send_args = winpipe.client_write_strings(
                    WIN_FILE_PIPE_NAME,
                    srcfile_args
                    )
        else:
            did_send_args = False

        if not did_send_args:
            LOGGER.warning("We must shutdown with unopened srcfiles.")

    return another_inst

def win_file_receiver(wx_app):
    """
    Only to be used on Windows
    """
    def string_read_fxn(read_str):
        # post as an Event to App, so it can open filenames we receive
        wx.PostEvent(wx_app, myWinFileEvent(open_filename=read_str))

    # for as long as this thread lives, wait for clients to write to pipe
    winpipe.server_pipe_read(WIN_FILE_PIPE_NAME, string_read_fxn)

def sanity_checks():
    """Things to check before we startup wx.App

    Raises Exceptions and logs errors for problems, mainly internal to app.
    """
    # Make sure we have access to all bitmaps.
    bitmap_paths = [
            const.SELECTBMP_FNAME, const.MARKBMP_FNAME, const.TOCLIPBMP_FNAME,
            const.ZOOMOUTBMP_FNAME, const.ZOOMINBMP_FNAME, const.ZOOMFITBMP_FNAME
            ]
    for bitmap_path in bitmap_paths:
        if not bitmap_path.is_file():
            LOGGER.error("Unable to find file: %s", bitmap_path)
            raise Exception("Missing bitmap file: %s"%bitmap_path)

def main(argv=None):
    """Main entrance into app.  Setup logging, create App, and enter main loop
    """
    # allow setting of global from main
    global DEBUG

    # process command line if started from there
    # Also, py2app sends file(s) to open via argv if file is dragged on top
    #   of the application icon to start the icon
    args = process_command_line(argv)

    # if -d or --debug turn on full debug
    if args.debug:
        DEBUG = True
        log_level = logging.DEBUG
    else:
        # default loglevel
        log_level = logging.INFO

    # Make sure we are only running a single instance per user
    # If not, exit
    if another_instance_running(args.srcfiles):
        print("Another instance of Marcam is already running.  Exiting.")
        return 1

    if (const.USER_CONFIG_DIR / 'debug').exists():
        DEBUG = True
        log_level = logging.DEBUG

    # setup logging
    logging_setup(log_level)

    # Route stderr to log
    sys.stderr = marcam_extra.StderrToLog()

    # get basic debug info
    log_debug_main()

    # see what argv and args are
    LOGGER.info(repr(args))

    # Do some sanity checks before we start wx stuff, to avoid segfaults
    sanity_checks()

    # setup main wx event loop
    myapp = MarcamApp(args.srcfiles)
    myapp.MainLoop()

    # return 0 to indicate "STATUS OK"
    return 0


if __name__ == "__main__":
    try:
        STATUS = main(sys.argv)
    except KeyboardInterrupt:
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        STATUS = 130
    except:
        LOGGER.error("UNCAUGHT FATAL ERROR", exc_info=True)
        STATUS = 1

    sys.exit(STATUS)
