#!/usr/bin/env python3

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

# TODO: Mac OS X specific things to possibly try:
#   wx.TopLevelWindow.OSXSetModified()

import argparse
from datetime import datetime
import json
import logging
import os
import os.path # TODO: consider pathlib
import platform
import re
import sys
import threading
import time

import wx
import wx.adv
import wx.html2
import wx.lib.dialogs

import image_proc
from image_scrolled_canvas import ImageScrolledCanvasMarks
import const
import common
import mcmfile

# DEBUG defaults to False.  Is set to True if debug switch found
DEBUG = False

# which modules are we logging
LOGGED_MODULES = [
        __name__, 'image_scrolled_canvas', 'image_proc', 'mcmfile', 'common'
        ]

# global logger obj for this file
LOGGER = logging.getLogger(__name__)

LOGGER.info("MSC:ICON_DIR=%s", const.ICON_DIR)

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)


class MarcamFormatter(logging.Formatter):
    def format(self, record):
        """Overload of default format fxn, make all lines after first indented
        of a log message

        Args:
            record (Logger.LogRecord): log message

        Returns:
            out_string: processed log message
        """
        out_string = super().format(record)
        # indent all lines after main format string
        out_string = out_string.replace("\n", "\n    ")
        return out_string


@debug_fxn
def can_read_image(image_path):
    """Detect if this image is readable by this program.

    Detects any readable plain image file, or .mcm file.
    """
    (_, image_path_ext) = os.path.splitext(image_path)
    if mcmfile.is_valid(image_path):
        img_ok = True
    elif image_path_ext == ".1sc":
        img_ok = not not image_proc.file1sc_to_image(image_path)
    else:
        # for all other image files
        # wx.Image.CanRead has its own error log, which is setup to cause
        #   error dialog.  Disable it if because want to use our own
        no_log = wx.LogNull()
        img_ok = wx.Image.CanRead(image_path)
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
    formatter = MarcamFormatter(
            "%(asctime)s:%(name)s:%(levelname)s:\n%(message)s"
            )

    # make sure log file dir exists
    os.makedirs(const.USER_LOG_DIR, exist_ok=True)

    # canonical logfile full path
    logfile_path = os.path.join(
            const.USER_LOG_DIR,
            'marcam.log'
            )

    # rename all old log files
    #   (log.txt.2 -> log.txt.3, log.txt.1 -> log.txt.2, log.txt -> log.txt.1
    num_logfile_hist = 10
    for i in range(num_logfile_hist-1, -1, -1):
        fname = logfile_path + ".%d"%i if i != 0 else logfile_path
        fname_plus_1 = logfile_path + ".%d"%(i+1)
        if os.path.exists(fname):
            os.replace(fname, fname_plus_1)

    # file handler
    file_handler = logging.FileHandler(logfile_path)
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

@debug_fxn
def default_config_data():
    """Canonical default config data

    Used when creating new config data file, or as defaults when reading
    From an old config data file with fewer keys.
    """
    config_data = {}
    config_data['winsize'] = [800, 600]
    config_data['debug'] = False

    return config_data

@debug_fxn
def create_config_file(config_filepath):
    config_data = default_config_data()

    try:
        with open(config_filepath, 'w') as config_fh:
            json.dump(
                    config_data,
                    config_fh,
                    )
    except OSError as err:
        LOGGER.warning("Can't create config file '%s': %s", config_filepath, err)

@debug_fxn
def load_config():
    # start with defaults, override later with any/all actual config data
    config_data = default_config_data()

    # create config dir if necessary
    os.makedirs(const.USER_CONFIG_DIR, exist_ok=True)

    config_filepath = os.path.join(
            const.USER_CONFIG_DIR,
            "config.json"
            )
    try:
        with open(config_filepath, 'r') as config_fh:
            config_data.update(json.load(config_fh))
    except FileNotFoundError:
        # if no config.json file, create
        create_config_file(config_filepath)

    return config_data

@debug_fxn
def save_config(config_data):
    # create config dir if necessary
    os.makedirs(const.USER_CONFIG_DIR, exist_ok=True)

    config_filepath = os.path.join(
            const.USER_CONFIG_DIR,
            "config.json"
            )
    # if no config.json file, create
    try:
        with open(config_filepath, 'w') as config_fh:
            json.dump(
                    config_data,
                    config_fh
                    )
        status = True
    except OSError as err:
        LOGGER.warning("Can't save config file '%s': %s", config_filepath, err)
        status = False

    return status


class EditHistory():
    """Keeps track of Edit History, undo, redo, whether save is needed
    """
    def __init__(self):
        self.undo_menu_item = None
        self.redo_menu_item = None
        self.history = []
        self.history_ptr = -1
        self._update_menu_items()

    @debug_fxn
    def reset(self):
        """Reset Edit History so it has no entries and ptr is reset
        """
        self.history = []
        self.history_ptr = -1
        self._update_menu_items()

    @debug_fxn
    def new(self, item, description=""):
        """Make a new Edit History item

        Args:
            item (list): list with first item being action string, and
                following items information concerning that action
            description (str): Short text description of the action,
                for putting after "Undo" or "Redo" in menu items.
                e.g. "Undo Add Marks", "Undo Invert Image"
        """
        # truncate list so current item is last item (makes empty list
        #   if self.history_ptr == -1)
        self.history = self.history[:self.history_ptr + 1]
        self.history.append(
                {
                    'edit_action':item,
                    'description':description,
                    'save_flag':False
                    }
                )
        self.history_ptr = len(self.history) - 1
        self._update_menu_items()

    @debug_fxn
    def save_notify(self):
        """Set save flag for current history action only, erase flag for all
        other actions in history

        save flag indicates that at this point in history, the file can be
        considered "saved" and we don't have to query user on close of file
        """
        # set all edit history save flags to False
        for i in range(len(self.history)):
            self.history[i]['save_flag'] = False

        # set current edit history action save flags to True
        if self.history_ptr > -1:
            self.history[self.history_ptr]['save_flag'] = True

    @debug_fxn
    def is_saved(self):
        """At this point in history, has user most recently saved document?

        Returns:
            bool: True if this point in history is saved
        """
        if self.history_ptr == -1:
            # no edit history, so no save needed
            return True

        return self.history[self.history_ptr]['save_flag']

    @debug_fxn
    def undo(self):
        """Return action to undo, and move history pointer to prev. action
        in history

        Returns:
            list: action, first item is str of action, remainig items
                are action info.  Returns None if nothing left to redo
        """
        if self._can_undo():
            undo_action = self.history[self.history_ptr]['edit_action']
            self.history_ptr -= 1
        else:
            undo_action = None

        self._update_menu_items()
        return undo_action

    @debug_fxn
    def redo(self):
        """Return action to redo, and move history pointer to next action
        in history

        Returns:
            list: action, first item is str of action, remainig items
                are action info.  Returns None if nothing left to undo
        """
        if self._can_redo():
            self.history_ptr += 1
            redo_action = self.history[self.history_ptr]['edit_action']
        else:
            redo_action = None

        self._update_menu_items()
        return redo_action

    @debug_fxn
    def get_actions_since_save(self):
        if self.is_saved():
            # no edit history or no actions since save
            return None

        try:
            save_loc = [x['save_flag'] for x in self.history].index(True)
        except ValueError:
            # never saved
            save_loc = -1

        if save_loc < self.history_ptr:
            edits_since_save = self.history[save_loc+1:self.history_ptr+1]
            edits_since_save = [x['description'] for x in edits_since_save]
        else:
            # save_loc > self.history_ptr:
            edits_since_save = self.history[self.history_ptr+1:save_loc+1]
            edits_since_save = ["Undo " + x['description'] for x in edits_since_save]
            edits_since_save.reverse()

        item_count = 1
        edits_since_save_new = []
        for (i, this_edit) in enumerate(edits_since_save):
            if i+1 < len(edits_since_save) and edits_since_save[i+1] == this_edit:
                item_count += 1
            else:
                edits_since_save_new.append(
                        this_edit + (" [x%d]"%item_count if item_count > 1 else "")
                        )
                item_count = 1

        return edits_since_save_new

    @debug_fxn
    def _can_undo(self):
        """Is there an action to undo back in history?

        Returns:
            bool: True if can undo
        """
        return (len(self.history) > 0) and (self.history_ptr >= 0)

    @debug_fxn
    def _can_redo(self):
        """Is there an action to redo next in history?

        Returns:
            bool: True if can redo
        """
        return (len(self.history) > 0) and (self.history_ptr < len(self.history) - 1)

    @debug_fxn
    def _update_menu_items(self):
        """Update the Enabled/Disabled quality of Undo, Redo Menu items
        """
        if self.undo_menu_item is not None:
            self.undo_menu_item.Enable(self._can_undo())
            if self._can_undo():
                key_accel = self.undo_menu_item.GetItemLabel().split('\t')[1]
                undo_descrip = self.history[self.history_ptr]['description']
                self.undo_menu_item.SetItemLabel(
                        "Undo " + undo_descrip + "\t" + key_accel
                        )
            else:
                key_accel = self.undo_menu_item.GetItemLabel().split('\t')[1]
                self.undo_menu_item.SetItemLabel(
                        "Undo\t" + key_accel
                        )

        if self.redo_menu_item is not None:
            self.redo_menu_item.Enable(self._can_redo())
            if self._can_redo():
                key_accel = self.redo_menu_item.GetItemLabel().split('\t')[1]
                undo_descrip = self.history[self.history_ptr + 1]['description']
                self.redo_menu_item.SetItemLabel(
                        "Redo " + undo_descrip + "\t" + key_accel
                        )
            else:
                key_accel = self.redo_menu_item.GetItemLabel().split('\t')[1]
                self.redo_menu_item.SetItemLabel(
                        "Redo\t" + key_accel
                        )

    @debug_fxn
    def register_undo_menu_item(self, undo_menu_item):
        """Give this class instance the Undo menu item instance so it can
        Enable and Disable menu item on its own

        Args:
            undo_menu_item (wx.MenuItem): menu item instance for Undo
        """
        self.undo_menu_item = undo_menu_item
        self._update_menu_items()

    @debug_fxn
    def register_redo_menu_item(self, redo_menu_item):
        """Give this class instance the Redo menu item instance so it can
        Enable and Disable menu item on its own

        Args:
            redo_menu_item (wx.MenuItem): menu item instance for Redo
        """
        self.redo_menu_item = redo_menu_item
        self._update_menu_items()


class FileDropTarget(wx.FileDropTarget):
    """FileDropTarget Facilitating dragging file into window to open
    """
    def __init__(self, window_target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_target = window_target

    @debug_fxn
    def OnDropFiles(self, _x, _y, filenames):
        """Dropped File Handler

        Args:
            _x (int): x coordinate of mouse
            _y (int): y coordinate of mouse
            filenames (list): A list of filepaths
        """
        filename = filenames[0]
        LOGGER.info("MSC:Drag and Drop filename:\n    %s", repr(filename))

        # ---------
        # OPTION 1: Open new frame or put image in existing blank frame
        img_ok = self.window_target.parent.open_image(filename)
        # ---------
        ## OPTION 2: Replace existing image in same frame
        ## Close any existing image
        #self.window_target.parent.close_image(keep_win_open=True)
        ## Open Drag-and-Dropped image file
        #img_ok = self.window_target.parent.open_image_this_frame(filename)
        # ---------

        # True to accept data, False to veto
        return img_ok


class ImageWindow(wx.Frame):
    def __init__(self, parent, **kwargs):
        # no parent window, so use None as only *arg
        super().__init__(None, **kwargs)

        # internal state
        self.frame_history = EditHistory()
        self.img_path = None
        self.save_filepath = None
        self.temp_scroll_zoom_state = None
        self.parent = parent
        self.close_source = None

        # GUI-related
        self.html = None
        self.mark_tool_id = None
        self.select_tool_id = None
        self.mark_menu_item = None
        self.select_menu_item = None
        self.toolbar = None
        self.started_temp_zoom = False
        self.menu_items_disable_no_image = None

        # App configuration
        self.config = wx.Config("Marcam", "itsayellow.com")

        # File history
        self.file_history = wx.FileHistory()
        self.file_history.Load(self.config)

        if DEBUG:
            start_time = time.time()
        self.init_ui()
        if DEBUG:
            eltime = time.time() - start_time
            LOGGER.debug("init_ui elapsed time: %.3fms", eltime*1000)

        # On init, we will always have no image, so this just disables
        #   unneeded menus
        self.menu_items_enable_disable()

    @debug_fxn
    def init_ui(self):
        """Initialize the GUI widgets of the main window
        """
        # Save original size so that we can make sure we are still that
        #   size after adding toolbar.  Toolbar on Mac adds 35 to height.
        orig_size = self.GetSize()

        # menu bar stuff
        menubar = wx.MenuBar()
        # File
        open_recent_menu = wx.Menu()
        file_menu = wx.Menu()
        file_open_item = file_menu.Append(wx.ID_OPEN,
                'Open Image...\tCtrl+O',
                'Open image file'
                )
        file_menu.AppendSubMenu(open_recent_menu,
                'Open Recent',
                'Open recent .mcm files'
                )
        file_menu.Append(wx.ID_SEPARATOR)
        file_close_item = file_menu.Append(wx.ID_CLOSE,
                'Close\tCtrl+W',
                'Close image'
                )
        file_save_item = file_menu.Append(wx.ID_SAVE,
                'Save Image Data\tCtrl+S',
                'Save .mcm image and data file'
                )
        file_saveas_item = file_menu.Append(wx.ID_SAVEAS,
                'Save Image Data As...\tShift+Ctrl+S',
                'Save .mcm image and data file'
                )
        file_exportimage_item = file_menu.Append(wx.ID_ANY,
                'Export Image...\tCtrl+E',
                'Export image with marks to image file'
                )
        file_quit_item = file_menu.Append(wx.ID_EXIT,
                'Quit\tCtrl+Q',
                'Quit application'
                )
        menubar.Append(file_menu, '&File')
        # Edit
        edit_menu = wx.Menu()
        edit_undo_item = edit_menu.Append(wx.ID_UNDO,
                'Undo\tCtrl+Z',
                'Undo last action'
                )
        edit_redo_item = edit_menu.Append(wx.ID_REDO,
                'Redo\tShift+Ctrl+Z',
                'Redo last undone action'
                )
        edit_menu.Append(wx.ID_SEPARATOR)
        edit_copy_item = edit_menu.Append(wx.ID_COPY,
                'Copy Marks Total\tCtrl+C',
                'Copy total marks number to Clipboard.'
                )
        self.selallitem = edit_menu.Append(wx.ID_SELECTALL,
                'Select All\tCtrl+A',
                'Select all marks'
                )
        menubar.Append(edit_menu, '&Edit')
        # View
        view_menu = wx.Menu()
        zoom_zoomout_item = view_menu.Append(wx.ID_ZOOM_OUT,
                'Zoom Out\t[',
                'Decrease image magnification.'
                )
        zoom_zoomin_item = view_menu.Append(wx.ID_ZOOM_IN,
                'Zoom In\t]',
                'Increase image magnification.'
                )
        zoom_zoomfit_item = view_menu.Append(wx.ID_ZOOM_FIT,
                'Zoom to Fit\tCtrl+0',
                'Zoom image to fill window.'
                )
        if const.PLATFORM == 'mac':
            # SUPER STOOPID HACK: Call this menu "View " instead of "View" to
            #   disable Mac inserting OS menu items for "Show Tab Bar", etc.
            #   which currently are non-functional. (We don't manage tabs.)
            # Note on Mac the trailing space is not visible in menu.
            menubar.Append(view_menu, '&View ')
        else:
            # Normal menu name for everyone else.
            menubar.Append(view_menu, '&View')

        # Tools
        tools_menu = wx.Menu()
        self.select_menu_item = tools_menu.Append(wx.ID_ANY, "&Select Mode\tCtrl+T")
        # we start in select mode, so disable menu to enable select mode
        self.select_menu_item.Enable(False)
        self.mark_menu_item = tools_menu.Append(wx.ID_ANY, "&Mark Mode\tCtrl+K")
        tools_menu.Append(wx.ID_SEPARATOR)
        tools_imginfo_item = tools_menu.Append(wx.ID_ANY,
                "&Image Info\tShift+Ctrl+I",
                )
        tools_imginvert_item = tools_menu.Append(wx.ID_ANY,
                "I&nvert Image\tShift+Ctrl+N",
                )
        tools_imgautocontrast0_item = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast 0\tShift+Ctrl+J",
                )
        tools_imgautocontrast2_item = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast 2",
                )
        tools_imgautocontrast4_item = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast 4",
                )
        tools_imgautocontrast6_item = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast 6",
                )
        tools_imgfcolorviridis_item = tools_menu.Append(wx.ID_ANY,
                "Image False Color (Viridis)\tShift+Ctrl+C",
                )
        tools_imgfcolorplasma_item = tools_menu.Append(wx.ID_ANY,
                "Image False Color (Plasma)",
                )
        tools_imgfcolormagma_item = tools_menu.Append(wx.ID_ANY,
                "Image False Color (Magma)",
                )
        tools_imgfcolorinferno_item = tools_menu.Append(wx.ID_ANY,
                "Image False Color (Inferno)",
                )
        menubar.Append(tools_menu, "&Tools")
        # Window
        if const.PLATFORM == 'mac':
            window_menu = wx.Menu()
            self.window_minimize_item = window_menu.Append(wx.ID_ANY,
                    'Minimize\tCtrl+M',
                    'Minimize window.'
                    )
            window_zoom_item = window_menu.Append(wx.ID_ANY,
                    'Zoom',
                    'Zoom window to fill screen.'
                    )
            window_menu.Append(wx.ID_SEPARATOR)
            menubar.Append(window_menu, "&Window")
            # register menu with file_windows FrameList to add window list at
            #   end of window_menu
            self.parent.file_windows.register_window_menu(self, window_menu)
            self.Bind(wx.EVT_MENU, self.on_minimize, self.window_minimize_item)
            self.Bind(wx.EVT_MENU, self.on_window_zoom, window_zoom_item)

        if DEBUG:
            # Debug menu (only if debug mode set)
            debug_menu = wx.Menu()
            debug_benchzoom_item = debug_menu.Append(wx.ID_ANY,
                    "Benchmark Zoom",
                    )
            menubar.Append(debug_menu, "&Debug")

            # Debug menu items function bindings
            self.Bind(wx.EVT_MENU, self.on_debug_benchzoom, debug_benchzoom_item)
        # Help
        help_menu = wx.Menu()
        help_about_item = help_menu.Append(wx.ID_ABOUT,
                "&About Marcam"
                )
        help_help_item = help_menu.Append(wx.ID_HELP,
                "&Marcam Help"
                )
        menubar.Append(help_menu,
                "&Help"
                )

        self.SetMenuBar(menubar)
        self.menu_items_disable_no_image = [
                file_close_item,
                file_save_item,
                file_saveas_item,
                file_exportimage_item,
                # Edit
                #edit_undo_item, # under EditHistory control
                #edit_redo_item, # under EditHistory control
                edit_copy_item,
                self.selallitem,
                # View
                zoom_zoomout_item,
                zoom_zoomin_item,
                zoom_zoomfit_item,
                # Tools
                tools_imginfo_item,
                tools_imginvert_item,
                tools_imgautocontrast0_item,
                tools_imgautocontrast2_item,
                tools_imgautocontrast4_item,
                tools_imgautocontrast6_item,
                tools_imgfcolorviridis_item,
                tools_imgfcolorplasma_item,
                tools_imgfcolormagma_item,
                tools_imgfcolorinferno_item,
                ]

        # register Open Recent menu, put under control of FileHistory obj
        self.file_history.UseMenu(open_recent_menu)
        self.file_history.AddFilesToMenu()

        # register Undo, Redo menu items so EditHistory obj can
        #   enable or disable them as needed
        self.frame_history.register_undo_menu_item(edit_undo_item)
        self.frame_history.register_redo_menu_item(edit_redo_item)

        # For marks display, find text width of "9999", to leave enough
        #   padding to have space to contain "999"
        screen_dc = wx.ScreenDC()
        screen_dc.SetFont(self.GetFont())
        (text_width_px, _) = screen_dc.GetTextExtent("9999")
        del screen_dc

        # Toolbar
        # INFO: wx toolbar buttons
        #   Mac: seem to be either 24x24 (retina 48x48) or 32x32 (retina 64x64)
        #   Mac: only those two sizes, and only square
        # INFO: Mac buttons:
        #   regular: monochrome
        #   activated: blue fg
        #   bg color: 243, 243, 243
        #   fg color: 115, 115, 115
        #   button outline color: 165, 165, 165 ?
        #   size: ~82w x48h including single pixel outline
        #       width can be variable (78w seen)
        #   in wx pixels use 24h x >24w
        #   rounded corners
        try:
            selectbmp = wx.Bitmap(const.SELECTBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: %s", const.SELECTBMP_FNAME)
        try:
            markbmp = wx.Bitmap(const.MARKBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: %s", const.MARKBMP_FNAME)
        try:
            toclipbmp = wx.Bitmap(const.TOCLIPBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: %s", const.TOCLIPBMP_FNAME)
        try:
            zoomoutbmp = wx.Bitmap(const.ZOOMOUTBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: %s", const.ZOOMOUTBMP_FNAME)
        try:
            zoomfitbmp = wx.Bitmap(const.ZOOMFITBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: %s", const.ZOOMFITBMP_FNAME)
        try:
            zoominbmp = wx.Bitmap(const.ZOOMINBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: %s", const.ZOOMINBMP_FNAME)
        #obmp = wx.Bitmap(os.path.join(ICON_DIR, 'topen32.png'))

        self.toolbar = self.CreateToolBar()
        #self.toolbar.SetToolBitmapSize(wx.Size(24,24))
        #otool = self.toolbar.AddTool(wx.ID_OPEN, 'Open', obmp)
        selecttool = self.toolbar.AddRadioTool(
                wx.ID_ANY, 'Select Mode', selectbmp, wx.NullBitmap,
                'Enter Select Mode'
                )
        self.select_tool_id = selecttool.GetId()
        marktool = self.toolbar.AddRadioTool(
                wx.ID_ANY, 'Mark Mode', markbmp, wx.NullBitmap,
                'Enter Mark Mode'
                )
        self.mark_tool_id = marktool.GetId()
        self.toolbar.AddStretchableSpace()
        zoomouttool = self.toolbar.AddTool(
                wx.ID_ANY, 'Zoom Out', zoomoutbmp,
                'Zoom Out'
                )
        zoomintool = self.toolbar.AddTool(
                wx.ID_ANY, 'Zoom In', zoominbmp,
                'Zoom In'
                )
        zoomfittool = self.toolbar.AddTool(
                wx.ID_ANY, 'Zoom to Fit', zoomfitbmp,
                'Zoom to Fit'
                )
        self.toolbar.AddStretchableSpace()
        # Create marks tally text control
        # init marks_num_display before ImageScrolledCanvas so ISC can
        #   update number on its init
        # using TextCtrl to allow copy to clipboard
        self.toolbar.AddControl(wx.StaticText(self.toolbar, wx.ID_ANY, "Marks:"))
        self.marks_num_display = wx.TextCtrl(
                self.toolbar, wx.ID_ANY, size=wx.Size(text_width_px, -1),
                #style=wx.TE_READONLY | wx.BORDER_NONE
                style=wx.TE_READONLY
                )
        self.toolbar.AddControl(self.marks_num_display)
        tocliptool = self.toolbar.AddTool(
                wx.ID_ANY, 'Copy', toclipbmp,
                'Copy to Clipboard'
                )
        self.toclip_tool_id = tocliptool.GetId()
        self.toolbar.Realize()

        # status bar stuff
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText('Ready.')

        # Panel keeps things from spilling over the frame, statusbar, etc.
        #   also accepts key focus
        #   probably with more than one Panel we need to worry about which
        #       has keyboard focus
        # ImageScrolledCanvas is the cleanest, fastest implementation for
        #   what we need
        self.img_panel = ImageScrolledCanvasMarks(
                self,
                self.frame_history,
                self.marks_num_update,
                # the following always makes scrollbars,
                #   Mac: they appear tiny and all the way to 0 (not
                #       disabled, and bad looking)
                #   Win: they appear properly disabled when canvas not bigger
                #style=wx.HSCROLL|wx.VSCROLL|wx.ALWAYS_SHOW_SB
                )
        # make ImageScrolledCanvas Drag and Drop Target
        self.img_panel.SetDropTarget(FileDropTarget(self.img_panel))

        # Vertical top-level sizer for main window
        #   unnecessary because Frame has only one child (self.img_panel) and
        #   so it automatically takes up entire window (except for toolbar,
        #   statusbar)
        #mybox = wx.BoxSizer(wx.VERTICAL) # MAC
        #mybox.Add(self.img_panel, proportion=1, flag=wx.EXPAND) # MAC
        #self.SetSizer(mybox) # MAC

        # setup event handlers for Frame events
        self.Bind(wx.EVT_CLOSE, self.on_evt_close)
        self.Bind(wx.EVT_ICONIZE, self.on_evt_iconize)

        # debug event handlers
        #self.Bind(wx.EVT_ACTIVATE, common.on_evt_debug)
        #self.Bind(wx.EVT_ACTIVATE_APP, common.on_evt_debug)
        #self.Bind(wx.EVT_HIBERNATE, common.on_evt_debug)
        #self.Bind(wx.EVT_KILL_FOCUS, common.on_evt_debug)
        #self.Bind(wx.EVT_MAXIMIZE, common.on_evt_debug)
        #self.Bind(wx.EVT_SET_FOCUS, common.on_evt_debug)
        #self.Bind(wx.EVT_SHOW, common.on_evt_debug)
        #self.Bind(wx.EVT_SIZE, common.on_evt_debug)
        #self.Bind(wx.EVT_SIZING, common.on_evt_debug)
        #self.Bind(wx.EVT_WINDOW_CREATE, common.on_evt_debug)
        #self.Bind(wx.EVT_WINDOW_DESTROY, common.on_evt_debug)

        # setup event handlers for toolbar
        self.Bind(wx.EVT_TOOL, self.on_selectmode, selecttool)
        self.Bind(wx.EVT_TOOL, self.on_markmode, marktool)
        self.Bind(wx.EVT_TOOL, self.on_toclip, tocliptool)
        self.Bind(wx.EVT_TOOL, self.on_zoomout, zoomouttool)
        self.Bind(wx.EVT_TOOL, self.on_zoomin, zoomintool)
        self.Bind(wx.EVT_TOOL, self.on_zoomfit, zoomfittool)

        # setup event handlers for menus
        # File menu items
        self.Bind(wx.EVT_MENU, self.on_open, file_open_item)
        self.Bind(wx.EVT_MENU, self.on_close, file_close_item)
        self.Bind(wx.EVT_MENU, self.on_save, file_save_item)
        self.Bind(wx.EVT_MENU, self.on_saveas, file_saveas_item)
        self.Bind(wx.EVT_MENU, self.on_export_image, file_exportimage_item)
        self.Bind(wx.EVT_MENU, self.on_quit, file_quit_item)
        # open recent handler
        self.Bind(wx.EVT_MENU_RANGE, self.on_open_recent,
                id=wx.ID_FILE1, id2=wx.ID_FILE9
                )
        # Edit menu items
        self.Bind(wx.EVT_MENU, self.on_undo, edit_undo_item)
        self.Bind(wx.EVT_MENU, self.on_redo, edit_redo_item)
        self.Bind(wx.EVT_MENU, self.on_toclip, edit_copy_item)
        self.Bind(wx.EVT_MENU, self.on_select_all, self.selallitem)
        # View menu items
        self.Bind(wx.EVT_MENU, self.on_zoomout, zoom_zoomout_item)
        self.Bind(wx.EVT_MENU, self.on_zoomin, zoom_zoomin_item)
        self.Bind(wx.EVT_MENU, self.on_zoomfit, zoom_zoomfit_item)
        # Tools menu items
        self.Bind(wx.EVT_MENU, self.on_selectmode, self.select_menu_item)
        self.Bind(wx.EVT_MENU, self.on_markmode, self.mark_menu_item)
        self.Bind(wx.EVT_MENU, self.on_imginfo, tools_imginfo_item)
        self.Bind(wx.EVT_MENU, self.on_imginvert, tools_imginvert_item)
        self.Bind(wx.EVT_MENU, self.on_imgautocontrast0, tools_imgautocontrast0_item)
        self.Bind(wx.EVT_MENU, self.on_imgautocontrast2, tools_imgautocontrast2_item)
        self.Bind(wx.EVT_MENU, self.on_imgautocontrast4, tools_imgautocontrast4_item)
        self.Bind(wx.EVT_MENU, self.on_imgautocontrast6, tools_imgautocontrast6_item)
        self.Bind(wx.EVT_MENU, self.on_imgfalsecolorviridis, tools_imgfcolorviridis_item)
        self.Bind(wx.EVT_MENU, self.on_imgfalsecolorplasma, tools_imgfcolorplasma_item)
        self.Bind(wx.EVT_MENU, self.on_imgfalsecolormagma, tools_imgfcolormagma_item)
        self.Bind(wx.EVT_MENU, self.on_imgfalsecolorinferno, tools_imgfcolorinferno_item)
        # Help menu items
        self.Bind(wx.EVT_MENU, self.on_about, help_about_item)
        self.Bind(wx.EVT_MENU, self.on_help, help_help_item)

        self.SetTitle('Marcam')

        # set icon in title bar for Windows (and unix?)
        my_icon_bundle = wx.IconBundle(os.path.join(const.ICON_DIR, 'marcam.ico'))
        self.SetIcons(my_icon_bundle)

        # Make sure we are the same size we meant to be at start of this fxn.
        # So that adding a toolbar won't make us taller than we were specified
        #   to be.
        self.SetSize(orig_size)

        # finally render app
        self.Show(True)

        LOGGER.info(
                "MSC:self.img_panel size: %s",
                repr(self.img_panel.GetClientSize())
                )

    @debug_fxn
    def activate(self):
        self.Raise()
        self.SetFocus()

    @debug_fxn
    def menu_items_enable_disable(self):
        """Enable or disable list of menu items if image frame has image

        Notices:
            self.menu_items_disable_no_image

        Affects:
            Enable state of menu items in self.menu_items_disable_no_image
        """
        enable_state = not self.img_panel.has_no_image()
        for item in self.menu_items_disable_no_image:
            item.Enable(enable_state)

    @debug_fxn
    def marks_num_update(self, mark_total):
        """Update the Total Marks display with argument.  Registered with
        img_panel so it can update this automatically

        Args:
            mark_total (int): number of marks to display in UI
        """
        self.marks_num_display.SetLabel("%d"%mark_total)

    @debug_fxn
    def has_image(self):
        return not self.img_panel.has_no_image()

    @debug_fxn
    def on_window_menu_activate(self, evt):
        self.activate()
        menu = evt.GetEventObject()
        menuitem_id = evt.GetId()
        menuitem = menu.FindItemById(menuitem_id)
        menuitem.Check(False)

    @debug_fxn
    def on_minimize(self, _evt):
        """Minimize Menu handler: for Window->Minimize

        Args:
            evt (wx.CommandEvt):
        """
        self.Iconize()

    @debug_fxn
    def on_window_zoom(self, _evt):
        """Zoom Menu handler: for Window->Zoom

        Toggles whether window is enlarged to boundaries of screen.
        Note this is different than "Full Screen" Mac button.

        Args:
            evt (wx.CommandEvt):
        """
        self.Maximize(not self.IsMaximized())

    @debug_fxn
    def on_evt_iconize(self, evt):
        """Event Handler for Iconize (Minimize, Unminimize) Window

        Args:
            evt (wx.IconizeEvt):
        """
        try:
            self.window_minimize_item.Enable(not self.IsIconized())
        except NameError:
            # if no window_minimize_item, silently ignore
            pass
        evt.Skip()

    @debug_fxn
    def on_evt_close(self, evt):
        """EVT_CLOSE Handler: anytime user or prog closes frame in any way

        Causes of this event:
            System Close button
            System Close command
            wx.Window.Close()

        Args:
            evt (wx.CloseEvt):
        """
        # can also use this to determine if last closed window shuts down app:
        #   def wx.PyApp.SetExitOnFrameDelete(self, flag)
        # https://wxpython.org/Phoenix/docs/html/wx.PyApp.html#wx.PyApp.SetExitOnFrameDelete
        # but this may delete menus

        # See if we can shutdown this frame.
        # If it is kept open for any reason, we need to veto this close event
        # shutdown_frame has the logic for what to do on attempting to close
        #   a window, including asking user about saving unsaved changes.
        veto_close = self.parent.shutdown_frame(
                self.GetId(),
                force_close=not evt.CanVeto(),
                from_close_menu=self.close_source == 'close_menu',
                from_quit_menu=self.close_source == 'quit_menu'
                )
        # reset self.close_source
        self.close_source = None

        if veto_close:
            # don't close window
            evt.Veto()
        else:
            # normally close window
            winsize = self.GetSize()
            self.parent.config_data['winsize'] = list(winsize)
            # TODO: do we only need to save file_history on quit?
            self.file_history.Save(self.config)
            # continue with normal event handling
            evt.Skip()


    @debug_fxn
    def on_close(self, _evt):
        """File->Close menu handler

        Args:
            _evt (wx.CommandEvent):
        """
        # send EVT_CLOSE event, next is on_evt_close()
        self.close_source = 'close_menu'
        self.Close()

    @debug_fxn
    def on_quit(self, _evt):
        """File->Quit menu handler

        Args:
            _evt (wx.CommandEvent):
        """
        self.parent.quit_app()

    @debug_fxn
    def on_key_down(self, evt):
        """EVT_KEY_DOWN Handler: pressing a key down event.

        Holding a key down (at least on macOS) generates repeated EVT_KEY_DOWN
        events but only one EVT_KEY_UP when user releases the key.

        Args:
            evt (wx.): TODO
        """

        key_code = evt.GetKeyCode()
        LOGGER.debug(
                "KEY:Key Down    key_code: %d    RawKeyCode: %d    Position: %s",
                key_code, evt.GetRawKeyCode(), evt.GetPosition()
                )

        # Don't need these anymore since we have menu keystrokes
        #if key_code == 91:
        #    # [ key
        #    #  key_code: 91
        #    #  RawKeyCode: 33
        #    # zoom out
        #    self.on_zoomout(self, evt)
        #if key_code == 93:
        #    # ] key
        #    #  key_code: 93
        #    #  RawKeyCode: 30
        #    # zoom in
        #    self.on_zoomin(self, evt)

        # keys usually scroll, so down arrow makes image go up, etc.
        # "arrow keys move virtual viewport over image"
        # NOTE: if we wanted to automatically implement panning, we could
        #   just evt.Skip in the following if statements
        if key_code == 314:
            # left key
            self.img_panel.pan_right(-const.SCROLL_KEY_SPEED)
        if key_code == 315:
            # up key
            self.img_panel.pan_down(-const.SCROLL_KEY_SPEED)
        if key_code == 316:
            # right key
            self.img_panel.pan_right(const.SCROLL_KEY_SPEED)
        if key_code == 317:
            # down key
            self.img_panel.pan_down(const.SCROLL_KEY_SPEED)

        if key_code in (127, 8):
            # Delete (127) or Backspace (8)
            deleted_marks = self.img_panel.delete_selected_marks()
            self.frame_history.new(
                    ['DELETE_MARK_LIST', deleted_marks],
                    description="Delete Mark" + ("s" if len(deleted_marks) > 1 else "")
                    )

        #if key_code == 307:
            # option key - initiate temporary zoom
            #LOGGER.debug("Option key down")
        if key_code == 32:
            # space bar
            LOGGER.debug("Space key down")

            if not self.started_temp_zoom:
                # only temp zoom if this is the first Key Down event without
                #   a Key Up event

                # save zoom / scroll state
                self.temp_scroll_zoom_state = self.img_panel.get_scroll_zoom_state()

                zoom = self.img_panel.zoom_point(
                        const.TEMP_ZOOM,
                        evt.GetPosition()
                        )
                if zoom:
                    self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

                # indicate we have actually initiated a temp zoom (so we
                #   don't keep zooming if user holds down temp zoom key
                #   and we get repeated Key Down events.)
                self.started_temp_zoom = True

        if key_code == 366:
            # PAGE UP
            # skip to process page up
            evt.Skip()
        if key_code == 367:
            # PAGE DOWN
            # skip to process page up
            evt.Skip()
        if key_code == 313:
            # HOME
            # skip to process HOME
            evt.Skip()
        if key_code == 312:
            # END
            # skip to process END
            evt.Skip()

        if key_code == 32:
            # Space Bar
            pass

    @debug_fxn
    def on_key_up(self, evt):
        """EVT_KEY_UP Handler: releasing a key event.

        Holding a key down (at least on macOS) generates repeated EVT_KEY_DOWN
        events but only one EVT_KEY_UP when user releases the key.

        Args:
            evt (wx.): TODO
        """
        key_code = evt.GetKeyCode()
        LOGGER.debug(
                "KEY:Key Up  key_code: %d    RawKeyCode: %d    Position: %s",
                key_code, evt.GetRawKeyCode(), evt.GetPosition()
                )

        #if key_code == 307:
            # option key - release temporary zoom
        if key_code == 32:
            # space bar - release temporary zoom
            LOGGER.debug("Space key up")

            self.img_panel.set_scroll_zoom_state(
                    self.temp_scroll_zoom_state
                    )
            # update statusbar zoom message
            zoom = self.img_panel.zoom_list[self.temp_scroll_zoom_state[1]]
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

            # indicate end of temp zoom state
            self.started_temp_zoom = False

        evt.Skip()

    @debug_fxn
    def on_selectmode(self, _evt):
        """Tools->Select Mode Menuitem, or Arrow tool button handler
        Go into Select Mode.

        Args:
            _evt (wx.CommandEvent):
        """
        # SELECT MODE
        self.img_panel.mark_mode = False

        self.mark_menu_item.Enable(True)
        self.select_menu_item.Enable(False)
        self.selallitem.Enable(True)
        # NOTE: must use this, can't talk to ToolbarBase item directly
        self.toolbar.ToggleTool(self.select_tool_id, True) # works!
        # NOTE: wx.CURSOR_NONE doesn't work on Windows
        self.img_panel.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    @debug_fxn
    def on_markmode(self, _evt):
        """Tools->Mark Mode Menuitem, or Mark tool button handler
        Go into Mark Mode.

        Args:
            _evt (wx.CommandEvent):
        """
        # MARK MODE
        self.img_panel.mark_mode = True

        self.mark_menu_item.Enable(False)
        self.select_menu_item.Enable(True)
        self.selallitem.Enable(False)
        # NOTE: must use this, can't talk to ToolbarBase item directly
        self.toolbar.ToggleTool(self.mark_tool_id, True) # works!
        # exiting select mode so no marks can be selected
        self.img_panel.deselect_all_marks()
        self.img_panel.SetCursor(wx.Cursor(wx.CURSOR_CROSS))

    @debug_fxn
    def on_toclip(self, _evt):
        """Edit->Copy Marks Total menu/toolbar button handler

        Copy the total number of marks to the Clipboard.

        Args:
            _evt (wx.CommandEvent):
        """
        marks_total_text = self.marks_num_display.GetLineText(0)
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(marks_total_text))
            # to ensure text stays on clipboard even after app exits
            #   Necessary for Windows.
            #   Not necessary for Mac.
            wx.TheClipboard.Flush()
            wx.TheClipboard.Close()

    @debug_fxn
    def on_open(self, _evt):
        """File->Open Image Data... menu handler for Main Window

        Args:
            _evt (wx.CommandEvent):
        """
        # create wildcard for:
        #   native *.mcm files
        #   Image files
        #   *.1sc files (Bio-Rad)
        image_wildcards = wx.Image.GetImageExtWildcard()
        image_exts = re.search(r"\(([^)]+)\)", image_wildcards).group(1)
        image_exts = "*.mcm;*.1sc;" + image_exts

        # wildcard_all is technically redundant, but is useful for Windows
        #   which has a pulldown menu filtering for each category of files.
        #   Thus the first "category" will show all applicable files.
        wildcard_all = "All openable files (" + image_exts + ")|" + \
                image_exts + "|"
        wildcard_mcm = "Marcam Image Data files (*.mcm)|*.mcm|"
        wildcard_img = "Image Files " + image_wildcards + "|"
        wildcard_1sc = "Bio-Rad 1sc Files|*.1sc"
        wildcard = wildcard_all + wildcard_mcm + wildcard_img + wildcard_1sc
        # native Mac open dialog has no title message
        open_file_dialog = wx.FileDialog(self,
                "" if const.PLATFORM == 'mac' else "Open Image file",
                wildcard=wildcard,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_file_dialog.ShowModal() == wx.ID_CANCEL:
            # the user canceled
            return

        # get filepath and attempt to open image into bitmap
        img_path = open_file_dialog.GetPath()
        img_ok = self.open_image(img_path)
        if not img_ok:
            # wx.ICON_ERROR has no effect on Mac
            wx.MessageDialog(None,
                    message="Unable to open file: %s"%img_path,
                    caption="File Read Error",
                    #style=wx.OK
                    #style=wx.OK | wx.ICON_ERROR
                    style=wx.OK | wx.ICON_EXCLAMATION
                    ).ShowModal()

    @debug_fxn
    def on_open_recent(self, evt):
        """File->Open Recent-> sub-menu handler for Main Window

        Args:
            evt (wx.): TODO
        """
        # get path from file_history
        img_path = self.file_history.GetHistoryFile(evt.GetId() - wx.ID_FILE1)
        if os.path.exists(img_path):
            img_ok = self.open_image(img_path)
            if not img_ok:
                # wx.ICON_ERROR has no effect on Mac
                wx.MessageDialog(None,
                        message="Unable to open file: %s"%img_path,
                        caption="File Read Error",
                        #style=wx.OK
                        #style=wx.OK | wx.ICON_ERROR
                        style=wx.OK | wx.ICON_EXCLAMATION
                        ).ShowModal()
        else:
            self.file_history.RemoveFileFromHistory(evt.GetId() - wx.ID_FILE1)
            wx.MessageDialog(self,
                    message="Unable to find file: %s"%img_path,
                    caption="File Not Found",
                    style=wx.OK
                    #style=wx.OK | wx.ICON_ERROR
                    #style=wx.OK | wx.ICON_EXCLAMATION
                    ).ShowModal()

    @debug_fxn
    def open_image(self, img_path):
        """Open new image, in this frame if it has no file, otherwise
        in new frame.

        Currently every function that calls this implements and error
        dialog if img_ok is returned False

        Args:
            img_path (str): full path to image to open

        Returns:
            (bool) img_ok - whether image was successfully loaded into current
                or new frame
        """
        if self.img_panel.has_no_image():
            img_ok = self.open_image_this_frame(img_path)
        else:
            img_ok = self.parent.new_frame_open_file(img_path)

        return img_ok

    # TODO: If we cannot succesfully open a file, make error dialog
    @debug_fxn
    def open_image_this_frame(self, img_path):
        (_, imgfile_ext) = os.path.splitext(img_path)
        if imgfile_ext == ".mcm":
            img_ok = self.load_mcmfile_from_path(img_path)
        else:
            # image or *.1sc file
            img_ok = self.load_image_from_file(img_path)
            # By not calling self.frame_history.save_notify(), indicate needs save

        if img_ok:
            self.menu_items_enable_disable()
            if const.PLATFORM == 'mac':
                # on Mac we hide the last frame we close.  So when opening
                #   we need to make sure to show it again
                self.Show()

        # if we successfully loaded the file return True, else False
        return img_ok

    @debug_fxn
    def load_mcmfile_from_path(self, imdata_path):
        """Load native app .mcm file

        Args:
            imdata_path (str): path to .mcm file to open
        """
        # init img_ok to False in case we don't load image
        img_ok = False

        # first load image from zip
        try:
            (img, marks, img_name) = mcmfile.load(imdata_path)
            # need: img, img_name, marks
        except mcmfile.McmFileError:
            img = None
            LOGGER.warning(
                    "Cannot open data in file '%s'.", imdata_path,
                    exc_info=True
                    )

        img_ok = img is not None

        if img_ok:
            self.img_panel.mark_point_list(marks)
            # reset img history in window to only new image, reset idx
            self.img_panel.new_img(img)
            # init image in window
            self.img_panel.init_image()
            # set save_filepath to path of mcm file we loaded
            # self.img_path if from mcm is list: [<mcmfilepath>, <member_name>]
            # TODO: do we even care about this list, or img_name?
            self.img_path = [imdata_path, img_name]
            self.save_filepath = imdata_path
            # TODO: is this superfluous?
            self.statusbar.SetStatusText(
                    "Image Data " + imdata_path + " loaded OK."
                    )
            # Set window title to filename
            self.SetTitle(os.path.basename(imdata_path))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(imdata_path)
            # on Mac update Window menu frame list with new title
            self.parent.file_windows.update_window_menu()
            # add successful file open to file history
            self.file_history.AddFileToHistory(imdata_path)
            # we just loaded .mcm file, so have nothing to save
            self.frame_history.save_notify()

        # img_ok will only be True if we successfully loaded file
        return img_ok

    @debug_fxn
    def load_image_from_file(self, img_file):
        """Given full (non *.mcm) img_file, load image into app

        Separate from on_open so we can use this with argv_emulation

        Args:
            img_file (str): full path to image file (JPG, TIFF, etc.)
        """
        img_ok = False

        # check for 1sc files and get image data to send to Image
        (_, imgfile_ext) = os.path.splitext(img_file)
        if imgfile_ext == ".1sc":
            img = image_proc.file1sc_to_image(img_file)
        else:
            # disable logging, we don't care if there is e.g. TIFF image
            #   with unknown fields
            # TODO: could also just raise loglevel to Error and above
            #       wx.Log.SetLogLevel()
            #       wx.Log.EnableLogging(True or False)
            #       wx.Log.Suspend(), wx.Log.Resume()
            no_log = wx.LogNull()

            img = wx.Image(img_file)

            # re-enable logging
            del no_log

        # check if img loaded ok
        img_ok = img and img.IsOk()

        if img_ok:
            # reset img history in window to only new image, reset idx
            self.img_panel.new_img(img)
            # init image in window
            self.img_panel.init_image()
            # TODO: is this superfluous?
            self.statusbar.SetStatusText("Image " + img_file + " loaded OK.")
            # reset filepath for mcm file to nothing if we load new image
            self.img_path = img_file
            self.save_filepath = None
            # Set window title to filename
            self.SetTitle(os.path.basename(img_file))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(img_file)
            # on Mac update Window menu frame list with new title
            self.parent.file_windows.update_window_menu()

        # img_ok will only be True if we successfully loaded file
        return img_ok

    @debug_fxn
    def close_image(self, keep_win_open=False):
        """Closes image in window

        Returns:
            bool: Whether the image was closed.
        """
        if not self.frame_history.is_saved():
            self.activate()
            try:
                image_to_close = os.path.basename(self.img_path)
            except TypeError:
                image_to_close = os.path.basename(self.img_path[0])

            # changes list
            changes_list = self.frame_history.get_actions_since_save()
            if len(changes_list) > 4:
                extra_str = "[%d more...]"%(len(changes_list) - 3)
                changes_list = changes_list[:3] + [extra_str,]
            if changes_list is not None:
                changes_str = "\n".join(["    - "+x for x in changes_list])

            save_query = wx.MessageDialog(
                    self,
                    "\nChanges since last save:\n%s\n"%changes_str,
                    "Save changes to \"%s\" before closing?"%image_to_close,
                    wx.CANCEL | wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION,
                    )
            save_query.SetYesNoLabels("&Save", "&Don't Save")
            save_query_response = save_query.ShowModal()
            if save_query_response == wx.ID_YES:
                self.on_save(None)
            elif save_query_response == wx.ID_CANCEL:
                return False

        # image is closed--if we still keep this frame open then reset state
        if keep_win_open:
            # reset edit/save history
            self.frame_history.reset()
            # reset filepath for mcm file to nothing on close
            self.save_filepath = None
            # make scrolled window show no image
            self.img_panel.set_no_image()
            # update statusbar text
            self.statusbar.SetStatusText('Ready.')
            # Set window title to generic app name
            self.SetTitle('Marcam')

        self.menu_items_enable_disable()

        return True

    @debug_fxn
    def on_save(self, evt):
        """File->Save menu handler for Main Window

        Args:
            evt (wx.CommandEvent):
        """
        if self.save_filepath is None:
            # we've never "Save As..." so do that instead
            self.on_saveas(evt)
        else:
            # use current filename/path to save
            if self.save_img_data(self.save_filepath) is not None:
                # signify we have saved content
                self.frame_history.save_notify()
            else:
                # error in saving dialog
                # wx.ICON_ERROR has no effect on Mac
                wx.MessageDialog(None,
                        message="Unable to save file: %s"%self.save_filepath,
                        caption="File Write Error",
                        #style=wx.OK
                        #style=wx.OK | wx.ICON_ERROR
                        style=wx.OK | wx.ICON_EXCLAMATION
                        ).ShowModal()

    @debug_fxn
    def on_saveas(self, _evt):
        """File->Save As... menu handler for Main Window

        Args:
            _evt (wx.CommandEvent):
        """
        if self.save_filepath:
            (default_dir, default_filename) = os.path.split(self.save_filepath)
        else:
            if isinstance(self.img_path, list):
                img_path = self.img_path[0]
            else:
                img_path = self.img_path
            (img_path_root, _) = os.path.splitext(
                    os.path.basename(img_path)
                    )
            default_save_path = img_path_root + ".mcm"
            (default_dir, default_filename) = os.path.split(default_save_path)

        # native Mac open dialog has no title message
        with wx.FileDialog(
                self,
                "" if const.PLATFORM == 'mac' else "Save MCM file",
                wildcard="MCM files (*.mcm)|*.mcm",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultDir=default_dir,
                defaultFile=default_filename,
                ) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # save the current contents in the file
            pathname = file_dialog.GetPath()
            arc_names = self.save_img_data(pathname)
            if arc_names is not None:
                self.save_filepath = pathname
                # set img_path
                self.img_path = [pathname, arc_names[0]]
                # signify we have saved content
                self.frame_history.save_notify()
                # add successful file save as to file history
                self.file_history.AddFileToHistory(pathname)
                # Set window title to newly-saved filename
                self.SetTitle(os.path.basename(pathname))
                # on Mac sets file icon in titlebar with right-click showing
                #   dir hierarchy
                self.SetRepresentedFilename(pathname)
                # on Mac update Window menu frame list with new title
                self.parent.file_windows.update_window_menu()
            else:
                # error in saving dialog
                # wx.ICON_ERROR has no effect on Mac
                wx.MessageDialog(None,
                        message="Unable to save file: %s"%pathname,
                        caption="File Write Error",
                        #style=wx.OK
                        #style=wx.OK | wx.ICON_ERROR
                        style=wx.OK | wx.ICON_EXCLAMATION
                        ).ShowModal()

    @debug_fxn
    def on_export_image(self, _evt):
        """File->Export Image... menu handler for Main Window

        Args:
            _evt (wx.CommandEvent):
        """
        if self.save_filepath is not None:
            img_path = self.save_filepath
        else:
            # if we have no save_filepath, we have not loaded .mcm image
            #   thus self.img_path cannot be list, but must be string
            img_path = self.img_path

        # create new filename based on old one but ending with _export.png
        (default_dir, default_filename) = os.path.split(img_path)
        (filename_root, _) = os.path.splitext(default_filename)
        default_filename = filename_root + "_export.png"

        # native Mac open dialog has no title message
        with wx.FileDialog(
                self,
                "" if const.PLATFORM == 'mac' else "Export Image and Marks as Image",
                wildcard=wx.Image.GetImageExtWildcard(),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultDir=default_dir,
                defaultFile=default_filename,
                ) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # save the current contents in the file
            pathname = file_dialog.GetPath()
            # saves from memorydc
            export_image = self.img_panel.export_to_image()
            export_image.SaveFile(pathname)

    @debug_fxn
    def on_undo(self, _evt):
        """Edit->Undo handler

        Possible actions:
            ['MARK', <one new mark coordinate>]
            ['DELETE_MARK_LIST', <list of mark coordinates deleted>]
            ['MOVE_MARK', <src mark coordinate>, <dest mark coordinate>]
            ['IMAGE_XFORM', <orig image>, <modified image>]
        Args:
            _evt (wx.CommandEvent):
        """
        action = self.frame_history.undo()
        LOGGER.info("MSC:undo: %s", repr(action))
        if action[0] == 'MARK':
            self.img_panel.delete_mark(action[1], internal=False)
        if action[0] == 'DELETE_MARK_LIST':
            self.img_panel.mark_point_list(action[1])
        if action[0] == 'MOVE_MARK':
            self.img_panel.move_mark(action[2], action[1], is_selected=False)
        if action[0] == 'IMAGE_XFORM':
            self.img_panel.set_img_idx(action[1])
            self.img_panel.init_image(do_zoom_fit=False)

    @debug_fxn
    def on_redo(self, _evt):
        """Edit->Redo handler

        Args:
            _evt (wx.CommandEvent):
        """
        action = self.frame_history.redo()
        LOGGER.info("MSC:redo: %s", repr(action))
        if action[0] == 'MARK':
            self.img_panel.mark_point(action[1])
        if action[0] == 'DELETE_MARK_LIST':
            self.img_panel.delete_mark_point_list(action[1])
        if action[0] == 'MOVE_MARK':
            self.img_panel.move_mark(action[1], action[2], is_selected=False)
        if action[0] == 'IMAGE_XFORM':
            self.img_panel.set_img_idx(action[2])
            self.img_panel.init_image(do_zoom_fit=False)

    @debug_fxn
    def on_select_all(self, _evt):
        """Edit->Select All handler

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.select_all_marks()

    @debug_fxn
    def on_zoomout(self, _evt):
        """View->Zoom Out menu/toolbar button handler

        Args:
            _evt (wx.CommandEvent):
        """
        zoom = self.img_panel.zoom(-1)
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

    @debug_fxn
    def on_zoomin(self, _evt):
        """View->Zoom In menu/toolbar button handler

        Args:
            _evt (wx.CommandEvent):
        """
        zoom = self.img_panel.zoom(1)
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

    @debug_fxn
    def on_zoomfit(self, _evt):
        """View->Zoom to Fit menu/toolbar button handler

        Args:
            _evt (wx.CommandEvent):
        """
        zoom = self.img_panel.zoom_fit()
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

    @debug_fxn
    def on_imginfo(self, _evt):
        """Tools->Image Info menu item

        Args:
            _evt (wx.CommandEvent):
        """
        image_info_text = self.img_panel.get_image_info()
        if image_info_text is None:
            image_info_text = "Error retrieving image data."
        image_dialog = wx.lib.dialogs.ScrolledMessageDialog(
                parent=self,
                msg=image_info_text,
                caption="Image Info",
                size=(800, 600),
                )
        image_dialog.ShowModal()

    @debug_fxn
    def on_imginvert(self, _evt):
        """Tools->Invert Image menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_invert()

    @debug_fxn
    def on_imgfalsecolorviridis(self, _evt):
        """Tools->False Color menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_remap_colormap(cmap='viridis')

    @debug_fxn
    def on_imgfalsecolorplasma(self, _evt):
        """Tools->False Color menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_remap_colormap(cmap='plasma')

    @debug_fxn
    def on_imgfalsecolormagma(self, _evt):
        """Tools->False Color menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_remap_colormap(cmap='magma')

    @debug_fxn
    def on_imgfalsecolorinferno(self, _evt):
        """Tools->False Color menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_remap_colormap(cmap='inferno')

    @debug_fxn
    def on_imgautocontrast0(self, _evt):
        """Tools->Image Auto-Contrast 0 menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_autocontrast(cutoff=0)

    @debug_fxn
    def on_imgautocontrast2(self, _evt):
        """Tools->Image Auto-Contrast 2 menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_autocontrast(cutoff=2)

    @debug_fxn
    def on_imgautocontrast4(self, _evt):
        """Tools->Image Auto-Contrast 4 menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_autocontrast(cutoff=4)

    @debug_fxn
    def on_imgautocontrast6(self, _evt):
        """Tools->Image Auto-Contrast 6 menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_autocontrast(cutoff=6)

    @debug_fxn
    def save_img_data(self, imdata_path):
        """Save image and mark locations to .mcm file

        Args:
            imdata_path (str): full path to filename to save to
        """
        return mcmfile.save(
                imdata_path,
                self.img_panel.get_current_img(),
                self.img_panel.marks
                )

    @debug_fxn
    def on_about(self, _evt):
        """Help->About Menuitem: Open the About window

        Args:
            _evt (wx.CommandEvent):
        """
        info = wx.adv.AboutDialogInfo()
        info.SetName("Marcam")
        info.SetVersion(const.VERSION_STR)
        info.SetDescription("Counting objects in images.")
        info.SetCopyright("(C) 2017-2018 Matthew A. Clapp")

        wx.adv.AboutBox(info)

    @debug_fxn
    def on_help(self, _evt):
        """Help->Help Menuitem: Open a brief help window (html)

        Args:
            _evt (wx.CommandEvent):
        """
        self.html = HelpFrame(self, id=wx.ID_ANY)
        self.html.Show(True)

    @debug_fxn
    def on_debug_benchzoom(self, _evt):
        """Zoom through the range and log all on_paint elapsed times

        Args:
            _evt (wx.CommandEvent):
        """
        desired_panel_size = wx.Size(1024, 768)

        # get current size of window
        self.benchzoom_origwinsize = self.GetSize()

        # set windows size so panel size is desired panel size
        panel_size = self.img_panel.GetSize()
        self.SetSize(
                self.benchzoom_origwinsize + (desired_panel_size - panel_size)
                )

        # get zoom to max zoom
        self.on_zoomfit(None)
        for _ in range(69):
            self.img_panel.zoom(1)

        LOGGER.debug("Start Debug Benchmark Zoom")
        # set paint_times to dict so on_paint records paint times
        self.img_panel.paint_times = {}

        self.benchzoom_iteration = 0
        self.benchzoom_zoom_num = 0
        # initiate CallLater loop calling self.debugzoom_helper
        #   (which then repeatedly calls itself until done)
        wx.CallLater(35, self.debugzoom_helper)

    @debug_fxn
    def debugzoom_helper(self):
        # on mac, we need to wait to zoom again after each zoom (CallLater), or
        #   else macOS (or wxOSX?) will skip paint events.
        # 10ms is too small.  35ms for safety (< 30Hz)
        # Maybe caused by beam synchronization?  Does that mean we just need to
        #   update slower than 60Hz (> 16ms) for most monitors?
        # https://arstechnica.com/gadgets/2007/04/beam-synchronization-friend-or-foe/

        total_iterations = 10
        wait_ms = 35

        if self.benchzoom_zoom_num < 68:
            # zoom out
            self.img_panel.zoom(-1)
            self.benchzoom_zoom_num += 1
            wx.CallLater(wait_ms, self.debugzoom_helper)
        elif self.benchzoom_zoom_num < 136:
            # zoom back in
            self.img_panel.zoom(1)
            self.benchzoom_zoom_num += 1
            wx.CallLater(wait_ms, self.debugzoom_helper)
        elif self.benchzoom_iteration < total_iterations-1:
            # start new iteration of zooms
            self.benchzoom_iteration += 1
            self.benchzoom_zoom_num = 0
            # zoom out
            self.img_panel.zoom(-1)
            self.benchzoom_zoom_num += 1
            wx.CallLater(wait_ms, self.debugzoom_helper)
        else:
            # finish timing, save data
            benchzoom_data = {}
            benchzoom_data['dataset_name'] = 'benchzoom'
            benchzoom_data['paint_times'] = self.img_panel.paint_times
            benchzoom_data['panel_size'] = self.img_panel.GetSize().Get()
            benchzoom_data['image_size'] = (
                    self.img_panel.img_size_x,
                    self.img_panel.img_size_y
                    )
            benchzoom_data['platform_uname'] = platform.uname()
            benchzoom_data['python_ver'] = sys.version.replace('\n', '')
            benchzoom_data['wx_ver'] = wx.__version__
            benchzoom_data['datetime'] = datetime.now().strftime('%Y%m%d_%H:%M:%S')
            data_filename = os.path.join(
                    const.USER_LOG_DIR,
                    "data_benchzoom_" + datetime.now().strftime('%Y%m%d_%H%M%S')+ ".json"
                    )
            with open(data_filename, 'w') as data_fh:
                json.dump(benchzoom_data, data_fh, separators=(',', ':'))
            LOGGER.debug("Wrote benchzoom data to file: %s", data_filename)
            LOGGER.debug("Finish Debug Benchmark Zoom")
            # reset paint_times to None so on_paint doesn't record
            self.img_panel.paint_times = None
            # set size of window to original size before benchmark
            self.SetSize(self.benchzoom_origwinsize)
            # zoom back to normal
            self.on_zoomfit(None)


class HelpFrame(wx.Frame):
    """Separate window to contain HTML help viewer
    """
    def __init__(self, *args, **kwargs):
        """Constructor"""
        super().__init__(*args, **kwargs)

        if const.PLATFORM == 'mac':
            help_filename = 'marcam_help_mac.html'
        else:
            help_filename = 'marcam_help.html'

        # use wx.html2 to allow better rendering (and CSS in future)
        self.html = wx.html2.WebView.New(self)
        self.html.LoadURL(
                'file://' + os.path.join(const.ICON_DIR, help_filename)
                )

        self.SetTitle("Marcam Help")
        self.SetSize((500, 600))


class FrameList():
    @debug_fxn
    def __init__(self):
        # index dict by ID, as we use this most often
        self.frame_dict = {}
        self.win_menu_list = []
        self.is_handling_window_menu = False

    @debug_fxn
    def active_frame(self):
        """Return the frame in FrameList that is currently active.
        """
        for frame_id in self.frame_dict:
            if self.frame_dict[frame_id]['frame'].IsActive():
                return_frame = self.frame_dict[frame_id]['frame']
                break
        return return_frame

    @debug_fxn
    def frame_with_file(self, img_file):
        """Return the frame in FrameList that has img_file inside it.
        """
        return_frame = None
        for frame_id in self.frame_dict:
            if (
                    self.frame_dict[frame_id]['frame'].img_path == img_file or
                    (
                        isinstance(self.frame_dict[frame_id]['frame'].img_path, list) and
                        self.frame_dict[frame_id]['frame'].img_path[0] == img_file
                        )
                    ):
                return_frame = self.frame_dict[frame_id]['frame']
                break
        return return_frame

    @debug_fxn
    def has_zero(self):
        """FrameList contains zero frames (empty).
        """
        return not self.frame_dict

    @debug_fxn
    def has_one(self):
        """FrameList contains only one frame.
        """
        return len(self.frame_dict) == 1

    @debug_fxn
    def all_have_image(self):
        """All FrameList frames contain images (has_image()==True)
        """
        # We assume the only possibility of a frame not having an image is if
        #   it is the only one.  Thus it is "safe" to just check [0].
        # self.frame_dict.values is a dictionary view object, we must convert
        #   it to list before indexing
        return len(self.frame_dict) > 0 and list(self.frame_dict.values())[0]['frame'].has_image()

    @debug_fxn
    def has_multiple(self):
        """FrameList has multiple frames.
        """
        return len(self.frame_dict) > 1

    @debug_fxn
    def frame_from_id(self, frame_id):
        """Return the frame specified by frame ID.
        """
        return self.frame_dict[frame_id]['frame']

    @debug_fxn
    def only_frame(self):
        """Return the only frame in the list
        """
        assert len(self.frame_dict) == 1
        # self.frame_dict.values is a dictionary view object, we must convert
        #   it to list before indexing
        return list(self.frame_dict.values())[0]['frame']

    @debug_fxn
    def append(self, frame_to_append):
        """Add the specified frame to the FrameList
        """
        # init to empty dict if not already
        self.frame_dict.setdefault(frame_to_append.GetId(), {})
        self.frame_dict[frame_to_append.GetId()]['frame'] = frame_to_append
        # if wxpython ever automatically manages the Window menu on Mac, the
        #   following will be unnecessary
        self.win_menu_list.append(frame_to_append.GetId())
        self.update_window_menu()

    @debug_fxn
    def update_window_menu(self):
        """Update the frame list part of the Window Menu on Mac

        if wxpython ever automatically manages the Window menu on Mac, the
        following will be unnecessary

        """
        if not self.is_handling_window_menu:
            return

        for frame_id in self.frame_dict:
            # we update each frame's Window menu list of windows
            this_frame = self.frame_dict[frame_id]['frame']
            win_menu = self.frame_dict[frame_id]['menu']
            win_menu_origcount = self.frame_dict[frame_id]['menu_origcount']
            for (i, menuitem_frame_id) in enumerate(self.win_menu_list):
                menuitem_frame = self.frame_dict[menuitem_frame_id]['frame']
                menuitem_frame_title = menuitem_frame.GetTitle()
                if win_menu_origcount + i < win_menu.GetMenuItemCount():
                    win_menu_item = win_menu.FindItemByPosition(i + win_menu_origcount)
                    if win_menu_item.GetItemLabel() == menuitem_frame_title:
                        # Current menu item is correct, set this_menuitem
                        this_menuitem = win_menu_item
                    else:
                        # Current menu item is not correct, replace it
                        win_menu.Remove(win_menu_item)
                        this_menuitem = win_menu.InsertCheckItem(
                                i + win_menu_origcount,
                                wx.ID_ANY,
                                menuitem_frame_title
                                )
                else:
                    # We don't have a menu item yet, so append one
                    this_menuitem = win_menu.AppendCheckItem(
                            wx.ID_ANY,
                            menuitem_frame_title
                            )
                if menuitem_frame_title == this_frame.GetTitle():
                    # For the Window menu item that is for our own window,
                    #   check it to show that's where we are
                    this_menuitem.Check(True)

                # Bind this menuitem to the appropriate frame's activation
                #   function
                this_frame.Bind(
                        wx.EVT_MENU,
                        menuitem_frame.on_window_menu_activate,
                        this_menuitem
                        )

    #@debug_fxn
    #def remove(self, frame_to_remove):
    #    self.frame_dict.pop(frame_to_remove.GetId())

    @debug_fxn
    def remove_id(self, frame_id_to_remove):
        """Remove the frame specified by frame ID from the FrameList
        """
        self.frame_dict.pop(frame_id_to_remove)

    @debug_fxn
    def register_window_menu(self, frame_inst, window_menu):
        # init to empty dict if not already
        self.frame_dict.setdefault(frame_inst.GetId(), {})
        self.frame_dict[frame_inst.GetId()]['menu'] = window_menu
        self.frame_dict[frame_inst.GetId()]['menu_origcount'] = window_menu.GetMenuItemCount()
        self.is_handling_window_menu = True

    @debug_fxn
    def get_list_copy(self):
        # TODO: hopefully we won't need this forever, stopgap
        return [self.frame_dict[id]['frame'] for id in self.frame_dict]


# NOTE: closing window saves size, opening new window uses saved size
class MarcamApp(wx.App):
    @debug_fxn
    def __init__(self, open_files, config_data, *args, **kwargs):
        # reset this before calling super().__init__(), which calls
        #   MacOpenFiles()
        self.file_windows = FrameList()
        self.config_data = config_data
        self.last_frame_pos = wx.DefaultPosition
        self.trying_to_quit = False

        # may call MacOpenFiles and add files to self.file_windows and make
        #   new frames
        super().__init__(*args, **kwargs)

        # this next statement can only be after calling __init__ of wx.App
        # gives just window-placeable screen area
        self.display_size = wx.Display().GetClientArea().GetSize()

        for open_file in open_files:
            # TODO: what to do with files that can't open because error
            img_ok = self.new_frame_open_file(open_file)

        # if after giving chances to open files from command-line, OS events,
        #   etc., we still don't have any open frames, open an empty one
        #   on startup
        if self.file_windows.has_zero():
            # open an empty frame
            img_ok = self.new_frame_open_file(None)

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

    def on_key_down(self, evt):
        self.file_windows.active_frame().on_key_down(evt)

    def on_key_up(self, evt):
        self.file_windows.active_frame().on_key_up(evt)

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

        if hide_window:
            # on Mac we hide the last frame we close.
            frame_to_close.Hide()

        veto_close = not close_window

        return veto_close

    @debug_fxn
    def new_frame_open_file(self, open_file):
        if open_file is not None:
            already_open_frame = self.file_windows.frame_with_file(open_file)
            if already_open_frame:
                # Already have a frame with that file open, don't open a dup
                #   just move it to front
                already_open_frame.activate()
                # because our image is already open in a frame, we
                #   return img_ok = True
                return True
            else:
                # verify ok image before opening new frame
                img_ok = can_read_image(open_file)
        else:
            # force img_ok to True if open_file is None
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
            new_frame = ImageWindow(
                    self,
                    size=new_size,
                    pos=new_pos
                    )
            self.file_windows.append(new_frame)
            if open_file is not None:
                ## TODO: handle what happens if bad image, if img_ok==False
                new_frame.open_image_this_frame(open_file)
            # need to actually GetPosition to get real position, in case both
            #   self.last_frame_pos = (-1, -1) and new_pos = (-1, -1)
            self.last_frame_pos = new_frame.GetPosition()

        return img_ok

    @debug_fxn
    def quit_app(self):
        self.trying_to_quit = True
        # we need to copy this because frame.Close() will end up modifying
        #   self.file_windows, which will corrupt the loop in progress
        for frame in self.file_windows.get_list_copy():
            frame.close_source = 'quit_menu'
            frame_closed = frame.Close()
            if not frame_closed:
                break
        self.trying_to_quit = False

    @debug_fxn
    def MacOpenFiles(self, file_names):
        """wx.PyApp standard function to accept Cocoa "openFiles" events.
        Over-ridden to process files.

        Args:
            file_names: list of file names to open
        """
        # NOTE: works great in bundled app,
        #   but cmd-line invocation causes file_names to be last argument
        #       of cmd-line, even if that's the script name (???)
        LOGGER.debug(file_names)
        for open_file in file_names:
            # open in blank window, or
            #   add to file_windows list of file windows
            if self.file_windows.has_zero() or self.file_windows.all_have_image():
                img_ok = self.new_frame_open_file(open_file)
            else:
                # only one frame, and it has no image
                img_ok = self.file_windows.only_frame().open_image_this_frame(open_file)
            # TODO: figure out how to ignore bad openFiles from command-line
            #   what to do with files that can't open because error
            if img_ok:
                LOGGER.info("MacOpenFiles: img_ok: %s", open_file)
            else:
                LOGGER.info("MacOpenFiles: not img_ok: %s", open_file)

    def OnExit(self):
        # save config_data right before app is about to exit
        save_config(self.config_data)
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

def another_instance_running(app_args):
    # make global to persist until app is closed
    global singleinst_instance
    singleinst_name = "Marcam-%s"%wx.GetUserId()
    os.makedirs(const.USER_CONFIG_DIR, exist_ok=True)
    singleinst_path = const.USER_CONFIG_DIR
    singleinst_instance = wx.SingleInstanceChecker(
            singleinst_name,
            singleinst_path,
            )
    returnval = singleinst_instance.IsAnotherRunning()
    if returnval and app_args.srcfiles:
        print("We must shutdown but we have srcfiles")

    return returnval

def win_file_receiver():
    i = 0
    while True:
        time.sleep(1)
        i += 1
        print("I'm still awake after %d iterations."%i)

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
    if another_instance_running(args):
        print("Another instance of Marcam is already running.  Exiting.")
        return 1

    # Since we're the master instance, on Windows startup a thread to field
    #   requests to open files from possible other instances started and ended
    if const.PLATFORM == 'win':
        threading.Thread(
                target=win_file_receiver,
                daemon=True,
                )

    # fetch configuration from file
    config_data = load_config()

    # allow debug mode to turn on also from config_data
    if config_data['debug']:
        DEBUG = True
        log_level = logging.DEBUG

    # setup logging
    logging_setup(log_level)

    # get basic debug info
    log_debug_main()

    # see what argv and args are
    LOGGER.info(repr(args))

    # setup main wx event loop
    myapp = MarcamApp(args.srcfiles, config_data)
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
