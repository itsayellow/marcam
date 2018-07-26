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
import json
import logging
import os
import os.path # TODO: consider pathlib
import platform
import re
import sys
import tempfile
import time
import zipfile

import wx
import wx.adv
import wx.html2
import wx.lib.dialogs
import numpy as np

import biorad1sc_reader
from biorad1sc_reader import BioRadInvalidFileError, BioRadParsingError

from image_scrolled_canvas import ImageScrolledCanvasMarks
import const
import common

# DEBUG sets global debug message verbosity

# NOTE: wx.DC.GetAsBitmap() to grab a DC as a bitmap

# which modules are we logging
LOGGED_MODULES = [__name__, 'image_scrolled_canvas']

# global logger obj for this file
LOGGER = logging.getLogger(__name__)

LOGGER.info("MSC:ICON_DIR=%s", const.ICON_DIR)

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info)


class MarcamFormatter(logging.Formatter):
    def format(self, record):
        """Overload of default format fxn, make all lines after first indented
        of a log message

        Args:
            record (str): log message

        Returns:
            out_string: processed log message
        """
        out_string = super().format(record)
        # indent all lines after main format string
        out_string = out_string.replace("\n", "\n    ")
        return out_string


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
    except:
        # TODO specific exception
        LOGGER.warn("Can't create config file: %s", config_filepath)

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
    # if no config.json file, create
    try:
        with open(config_filepath, 'r') as config_fh:
            config_data.update(json.load(config_fh))
    except:
        # TODO specific exception
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
            config_data = json.dump(
                    config_data,
                    config_fh
                    )
        status = True
    except:
        # TODO specific exception
        LOGGER.warn("Can't save config file: %s", config_filepath)
        status = False

    return status

@debug_fxn
def file1sc_to_Image(file1sc_file):
    """Read in file1sc file and convert to wx.Image

    Args:
        file1sc_file (str): path to .1sc file

    Returns:
        wx.Image: image object
    """
    try:
        read1sc = biorad1sc_reader.Reader(file1sc_file)
    except (BioRadInvalidFileError, BioRadParsingError):
        # img_ok is false if 1sc is not valid 1sc file
        return False

    (img_x, img_y, img_data) = read1sc.get_img_data()

    # TODO: wx.Image is probably only 8-bits each color channel
    #   yet we have 16-bit images
    # wx.Image wants img_x * img_y * 3
    # TODO: shadow data with full 16-bit info
    img_data_rgb = np.zeros(img_data.size*3, dtype='uint8')
    img_data_rgb[0::3] = img_data//256
    img_data_rgb[1::3] = img_data//256
    img_data_rgb[2::3] = img_data//256
    img = wx.Image(img_x, img_y, bytes(img_data_rgb))
    return img


class EditHistory():
    """Keeps track of Edit History, undo, redo
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
    def new(self, item):
        """Make a new Edit History item

        Args:
            item (list): list with first item being action string, and
                following items information concerning that action
        """
        # truncate list so current item is last item (makes empty list
        #   if self.history_ptr == -1)
        self.history = self.history[:self.history_ptr + 1]
        self.history.append({'edit_action':item, 'save_flag':False})
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
            # no edit history, so no save needed (TODO?)
            return True
        else:
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
        if self.redo_menu_item is not None:
            self.redo_menu_item.Enable(self._can_redo())

    @debug_fxn
    def register_undo_menu_item(self, undo_menu_item):
        """Give this class instance the Undo menu item instance so it can
        Enable and Disable menu item on its own

        Args:
            undo_menu_item (wx.MenuItem): menud item instance for Undo
        """
        self.undo_menu_item = undo_menu_item
        self._update_menu_items()

    @debug_fxn
    def register_redo_menu_item(self, redo_menu_item):
        """Give this class instance the Redo menu item instance so it can
        Enable and Disable menu item on its own

        Args:
            redo_menu_item (wx.MenuItem): menud item instance for Redo
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
    def OnDropFiles(self, x, y, filenames):
        """Dropped File Handler

        Args:
            x (int): x coordinate of mouse
            y (int): y coordinate of mouse
            filenames (list): A list of filepaths
        """
        filename = filenames[0]
        LOGGER.info("MSC:Drag and Drop filename:\n    %s", repr(filename))
        # Close any existing image
        self.window_target.parent.close_image(keep_win_open=True)
        # Open Drag-and-Dropped image file
        self.window_target.parent.open_image(filename)

        # TODO: which one of these??
        #return wx.DragCopy
        return True


class ImageWindow(wx.Frame):
    def __init__(self, parent, srcfile, **kwargs):
        # no parent window, so use None as only *arg
        super().__init__(None, **kwargs)

        # internal state
        self.app_history = EditHistory()
        self.content_saved = True
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

        # App configuration
        self.config = wx.Config("Marcam", "itsayellow.com")

        # File history
        self.file_history = wx.FileHistory()
        self.file_history.Load(self.config)

        self.init_ui()
        if srcfile is not None:
            if srcfile.endswith(".mcm"):
                self.load_mcmfile_from_path(srcfile)
            else:
                self.load_image_from_file(srcfile)

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
        oitem = file_menu.Append(wx.ID_OPEN,
                'Open Image...\tCtrl+O',
                'Open image file'
                )
        orecentitem = file_menu.AppendSubMenu(open_recent_menu,
                'Open Recent',
                'Open recent .mcm files'
                )
        file_menu.Append(wx.ID_SEPARATOR)
        citem = file_menu.Append(wx.ID_CLOSE,
                'Close\tCtrl+W',
                'Close image'
                )
        sitem = file_menu.Append(wx.ID_SAVE,
                'Save Image Data\tCtrl+S',
                'Save .mcm image and data file'
                )
        saitem = file_menu.Append(wx.ID_SAVEAS,
                'Save Image Data As...\tShift+Ctrl+S',
                'Save .mcm image and data file'
                )
        eiitem = file_menu.Append(wx.ID_ANY,
                'Export Image...\tCtrl+E',
                'Export image with marks to image file'
                )
        quititem = file_menu.Append(wx.ID_EXIT,
                'Quit\tCtrl+Q',
                'Quit application'
                )
        menubar.Append(file_menu, '&File')
        # Edit
        edit_menu = wx.Menu()
        undoitem = edit_menu.Append(wx.ID_UNDO,
                'Undo\tCtrl+Z',
                'Undo last action'
                )
        redoitem = edit_menu.Append(wx.ID_REDO,
                'Redo\tShift+Ctrl+Z',
                'Redo last undone action'
                )
        edit_menu.Append(wx.ID_SEPARATOR)
        copyitem = edit_menu.Append(wx.ID_COPY,
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
        zoomoutitem = view_menu.Append(wx.ID_ZOOM_OUT,
                'Zoom Out\t[',
                'Decrease image magnification.'
                )
        zoominitem = view_menu.Append(wx.ID_ZOOM_IN,
                'Zoom In\t]',
                'Increase image magnification.'
                )
        zoomfititem = view_menu.Append(wx.ID_ZOOM_FIT,
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
        self.mark_menu_item = tools_menu.Append(wx.ID_ANY, "&Mark Mode\tCtrl+M")
        tools_menu.Append(wx.ID_SEPARATOR)
        imginfoitem = tools_menu.Append(wx.ID_ANY,
                "&Image Info (Experimental)\tShift+Ctrl+I",
                )
        imgautocontrastitem = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast (Experimental)\tShift+Ctrl+J",
                )
        imginvertitem = tools_menu.Append(wx.ID_ANY,
                "I&nvert Image (Experimental)\tShift+Ctrl+N",
                )
        imgremapcoloritem = tools_menu.Append(wx.ID_ANY,
                "Re&map Colors in Image (Experimental)\tShift+Ctrl+M",
                )
        menubar.Append(tools_menu, "&Tools")
        # Help
        help_menu = wx.Menu()
        aboutitem = help_menu.Append(wx.ID_ABOUT,
                "&About Marcam"
                )
        helpitem = help_menu.Append(wx.ID_HELP,
                "&Marcam Help"
                )
        menubar.Append(help_menu,
                "&Help"
                )

        self.SetMenuBar(menubar)

        # register Open Recent menu, put under control of FileHistory obj
        self.file_history.UseMenu(open_recent_menu)
        self.file_history.AddFilesToMenu()

        # register Undo, Redo menu items so EditHistory obj can
        #   enable or disable them as needed
        self.app_history.register_undo_menu_item(undoitem)
        self.app_history.register_redo_menu_item(redoitem)

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
            LOGGER.error("MSC:Icon doesn't exist: " + const.SELECTBMP_FNAME)
        try:
            markbmp = wx.Bitmap(const.MARKBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: " + const.MARKBMP_FNAME)
        try:
            toclipbmp = wx.Bitmap(const.TOCLIPBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: " + const.TOCLIPBMP_FNAME)
        try:
            zoomoutbmp = wx.Bitmap(const.ZOOMOUTBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: " + const.ZOOMOUTBMP_FNAME)
        try:
            zoomfitbmp = wx.Bitmap(const.ZOOMFITBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: " + const.ZOOMFITBMP_FNAME)
        try:
            zoominbmp = wx.Bitmap(const.ZOOMINBMP_FNAME)
        except:
            LOGGER.error("MSC:Icon doesn't exist: " + const.ZOOMINBMP_FNAME)
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
        # TODO: think about putting border (invisible somehow?) back in
        #   so that count is justified with "Marks" label
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
                self.app_history,
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

        # setup event handlers for toolbar
        self.Bind(wx.EVT_TOOL, self.on_selectmode, selecttool)
        self.Bind(wx.EVT_TOOL, self.on_markmode, marktool)
        self.Bind(wx.EVT_TOOL, self.on_toclip, tocliptool)
        self.Bind(wx.EVT_TOOL, self.on_zoomout, zoomouttool)
        self.Bind(wx.EVT_TOOL, self.on_zoomin, zoomintool)
        self.Bind(wx.EVT_TOOL, self.on_zoomfit, zoomfittool)

        # setup event handlers for menus
        # File menu items
        self.Bind(wx.EVT_MENU, self.on_open, oitem)
        self.Bind(wx.EVT_MENU, self.on_close, citem)
        self.Bind(wx.EVT_MENU, self.on_save, sitem)
        self.Bind(wx.EVT_MENU, self.on_saveas, saitem)
        self.Bind(wx.EVT_MENU, self.on_export_image, eiitem)
        self.Bind(wx.EVT_MENU, self.on_quit, quititem)
        # open recent handler
        self.Bind(wx.EVT_MENU_RANGE, self.on_open_recent,
                id=wx.ID_FILE1, id2=wx.ID_FILE9
                )
        # Edit menu items
        self.Bind(wx.EVT_MENU, self.on_undo, undoitem)
        self.Bind(wx.EVT_MENU, self.on_redo, redoitem)
        self.Bind(wx.EVT_MENU, self.on_toclip, copyitem)
        self.Bind(wx.EVT_MENU, self.on_select_all, self.selallitem)
        # View menu items
        self.Bind(wx.EVT_MENU, self.on_zoomout, zoomoutitem)
        self.Bind(wx.EVT_MENU, self.on_zoomin, zoominitem)
        self.Bind(wx.EVT_MENU, self.on_zoomfit, zoomfititem)
        # Tools menu items
        self.Bind(wx.EVT_MENU, self.on_selectmode, self.select_menu_item)
        self.Bind(wx.EVT_MENU, self.on_markmode, self.mark_menu_item)
        self.Bind(wx.EVT_MENU, self.on_imginfo, imginfoitem)
        self.Bind(wx.EVT_MENU, self.on_imgautocontrast, imgautocontrastitem)
        self.Bind(wx.EVT_MENU, self.on_imginvert, imginvertitem)
        self.Bind(wx.EVT_MENU, self.on_imgremapcolor, imgremapcoloritem)
        # Help menu items
        self.Bind(wx.EVT_MENU, self.on_about, aboutitem)
        self.Bind(wx.EVT_MENU, self.on_help, helpitem)

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
    def register_key_bind(self, key_bind_fxn):
        # TODO: what is this for??
        self.key_bind_fxn = key_bind_fxn

    @debug_fxn
    def marks_num_update(self, mark_total):
        """Update the Total Marks display with argument.  Registered with
        img_panel so it can update this automatically

        Args:
            mark_total (int): number of marks to display in UI
        """
        self.marks_num_display.SetLabel("%d"%mark_total)

    def has_image(self):
        return not self.img_panel.has_no_image()

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
        veto_close = self.parent.shutdown_frame(
                self.GetId(),
                force_close=not evt.CanVeto(),
                from_close_menu=self.close_source=='close_menu',
                from_quit_menu=self.close_source=='quit_menu'
                )
        if veto_close:
            # don't close window
            evt.Veto()
        else:
            # normally close window
            winsize = self.GetSize()
            self.parent.config_data['winsize'] = list(winsize)
            self.file_history.Save(self.config)
            # continue with normal event handling
            evt.Skip()

        # reset self.close_source
        self.close_source = None


    @debug_fxn
    def on_close(self, evt):
        self.menu_close_file = True
        # send EVT_CLOSE event, next is on_evt_close()
        self.close_source = 'close_menu'
        self.Close()

    @debug_fxn
    def on_quit(self, evt):
        """Handler for menu Quit

        Args:
            evt (wx.): TODO
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

        if key_code == 127 or key_code == 8:
            # Delete (127) or Backspace (8)
            deleted_marks = self.img_panel.delete_selected_marks()
            self.app_history.new(['DELETE_MARK_LIST', deleted_marks])

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
    def on_selectmode(self, evt):
        """Tools->Select Mode Menuitem, or Arrow tool button handler
        Go into Select Mode.

        Args:
            evt (wx.): TODO
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
    def on_markmode(self, evt):
        """Tools->Mark Mode Menuitem, or Mark tool button handler
        Go into Mark Mode.

        Args:
            evt (wx.): TODO
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
    def on_toclip(self, evt):
        """When pressing the "To Clipboard" button next to Marks Tally display

        Copy the total number of marks to the Clipboard.

        Args:
            evt (wx.): TODO
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
    def on_open(self, evt):
        """File->Open Image Data... menu handler for Main Window

        Args:
            evt (wx.): TODO
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
        open_file_dialog = wx.FileDialog(self,
                "Open Image file",
                wildcard=wildcard,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_file_dialog.ShowModal() == wx.ID_CANCEL:
            # the user canceled
            return

        # get filepath and attempt to open image into bitmap
        img_path = open_file_dialog.GetPath()

        if self.img_panel.has_no_image():
            self.open_image(img_path)
            if const.PLATFORM == 'mac':
                # on Mac we hide the last frame we close.  So when opening
                #   we need to show it again
                self.Show()
        else:
            self.parent.new_frame_open_file(img_path)

    @debug_fxn
    def open_image(self, img_path):
        (_, imgfile_ext) = os.path.splitext(img_path)
        if imgfile_ext == ".mcm":
            self.load_mcmfile_from_path(img_path)
            self.save_filepath = img_path
            # add successful file open to file history
            self.file_history.AddFileToHistory(img_path)
            # we just loaded .mcm file, so have nothing to save
            self.save_notify()
        else:
            # image or *.1sc file
            self.load_image_from_file(img_path)
            # TODO: make it think it needs save immediately

    @debug_fxn
    def on_open_recent(self, evt):
        """File->Open Recent-> <File> menu handler for Main Window

        Args:
            evt (wx.): TODO
        """
        # TODO: open new window if this window is not blank

        # get path from file_history
        img_path = self.file_history.GetHistoryFile(evt.GetId() - wx.ID_FILE1)
        self.load_mcmfile_from_path(img_path)
        self.save_filepath = img_path
        # we just loaded, so have nothing to save
        self.save_notify()
        # add successful file open to file history
        self.file_history.AddFileToHistory(img_path)

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
            with zipfile.ZipFile(imdata_path, 'r') as container_fh:
                namelist = container_fh.namelist()
                for name in namelist:
                    if name.startswith("image."):
                        tmp_dir = tempfile.mkdtemp()
                        container_fh.extract(name, tmp_dir)

                        if name.endswith(".1sc"):
                            img = file1sc_to_Image(os.path.join(tmp_dir, name))
                        else:
                            # disable logging, we don't care if there is e.g. TIFF image
                            #   with unknown fields
                            # TODO: could also just raise loglevel to Error and above
                            no_log = wx.LogNull()

                            img = wx.Image(os.path.join(tmp_dir, name))

                            # re-enable logging
                            del no_log
                        # check if img loaded ok
                        img_ok = img.IsOk()
                        img_name = name

                        # remove temp dir
                        os.remove(os.path.join(tmp_dir, name))
                        os.rmdir(tmp_dir)

                    if name == "marks.txt":
                        with container_fh.open(name, 'r') as json_fh:
                            marks = json.load(json_fh)
                        marks = [tuple(x) for x in marks]
                        self.img_panel.mark_point_list(marks)
            if img_ok:
                self.img_panel.init_image(img)
                # set save_filepath to path of mcm file we loaded
                # self.img_path if from zip is list, zipfile, member_name
                self.img_path = [imdata_path, img_name]
                self.save_filepath = imdata_path
                self.statusbar.SetStatusText(
                        "Image Data " + imdata_path + " loaded OK."
                        )
                # Set window title to filename
                self.SetTitle(os.path.basename(imdata_path))
                # on Mac sets file icon in titlebar with right-click showing
                #   dir hierarchy
                self.SetRepresentedFilename(imdata_path)
            else:
                self.statusbar.SetStatusText(
                        "Image " + imdata_path+ " loading ERROR."
                        )

        except IOError:
            # TODO: need real error dialog
            LOGGER.warning(
                    "Cannot open data in file '%s'.", imdata_path,
                    exc_info=True
                    )

    @debug_fxn
    def load_image_from_file(self, img_file):
        """Given full (non *.mcm) img_file, load image into app

        Separate from on_open so we can use this with argv_emulation

        Args:
            img_file (str): full path to image file (JPG, TIFF, etc.)
        """
        # check for 1sc files and get image data to send to Image
        (_, imgfile_ext) = os.path.splitext(img_file)
        if imgfile_ext == ".1sc":
            img = file1sc_to_Image(img_file)
        else:
            # disable logging, we don't care if there is e.g. TIFF image
            #   with unknown fields
            # TODO: could also just raise loglevel to Error and above
            no_log = wx.LogNull()

            img = wx.Image(img_file)

            # re-enable logging
            del no_log

        # check if img loaded ok
        img_ok = img.IsOk()

        if img_ok:
            self.img_panel.init_image(img)
            self.statusbar.SetStatusText("Image " + img_file + " loaded OK.")
            # reset filepath for mcm file to nothing if we load new image
            self.img_path = img_file
            self.save_filepath = None
            # Set window title to filename
            self.SetTitle(os.path.basename(img_file))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(img_file)
        else:
            self.statusbar.SetStatusText(
                    "Image " + img_file + " loading ERROR."
                    )

    @debug_fxn
    def close_image(self, keep_win_open=False):
        """Close Image menu handler for Main Window

        Args:
            evt (wx.): TODO

        Returns:
            bool: Whether the image was closed.
        """
        if self.needs_save():
            save_query = wx.MessageDialog(
                    self,
                    "",
                    "Save changes to Image Data before closing this image?",
                    wx.CANCEL | wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION,
                    )
            save_query.SetYesNoLabels("&Save", "&Don't Save")
            save_query_response = save_query.ShowModal()
            if save_query_response == wx.ID_YES:
                self.on_save(None)
            elif save_query_response == wx.ID_CANCEL:
                return False

        # if image is closed, do we still keep this frame open?
        if keep_win_open:
            # reset edit history
            self.app_history.reset()
            # reset filepath for mcm file to nothing on close
            self.save_filepath = None
            # reset content_saved in case user didn't save
            self.content_saved = True
            # make scrolled window show no image
            self.img_panel.set_no_image()
            # update statusbar text
            self.statusbar.SetStatusText('Ready.')
            # Set window title to generic app name
            self.SetTitle('Marcam')

        return True

    @debug_fxn
    def on_save(self, evt):
        """Save menu handler for Main Window

        Args:
            evt (wx.): TODO
        """
        if self.save_filepath is None:
            # we've never "Save As..." so do that instead
            self.on_saveas(evt)
        else:
            # use current filename/path to save
            self.save_img_data(self.save_filepath)
            # signify we have saved content
            self.save_notify()

    @debug_fxn
    def on_saveas(self, evt):
        """Save As... menu handler for Main Window

        Args:
            evt (wx.): TODO
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
        with wx.FileDialog(
                self,
                "Save MCM file", wildcard="MCM files (*.mcm)|*.mcm",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultDir=default_dir,
                defaultFile=default_filename,
                ) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # save the current contents in the file
            pathname = file_dialog.GetPath()
            self.save_img_data(pathname)
            # TODO check if save_img_data worked before saving save name
            self.save_filepath = pathname
            # signify we have saved content
            self.save_notify()
            # add successful file save as to file history
            self.file_history.AddFileToHistory(pathname)
            # Set window title to newly-saved filename
            self.SetTitle(os.path.basename(pathname))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(pathname)

    @debug_fxn
    def on_export_image(self, evt):
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
            default_save_path = img_path_root + ".png"
            (default_dir, default_filename) = os.path.split(default_save_path)
        with wx.FileDialog(
                self,
                "Export Image and Marks as Image",
                wildcard=wx.Image.GetImageExtWildcard(),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultDir=default_dir,
                #defaultFile=default_filename,
                ) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # save the current contents in the file
            pathname = file_dialog.GetPath()
            export_image = self.img_panel.export_to_image()
            export_image.SaveFile(pathname)

    @debug_fxn
    def on_undo(self, evt):
        """Edit->Undo handler

        Args:
            evt (wx.): TODO
        """
        action = self.app_history.undo()
        LOGGER.info("MSC:undo: %s", repr(action))
        if action[0] == 'MARK':
            self.img_panel.delete_mark(action[1], internal=False)
        if action[0] == 'DELETE_MARK_LIST':
            self.img_panel.mark_point_list(action[1])
        if action[0] == 'MOVE_MARK':
            self.img_panel.move_mark(action[2], action[1], is_selected=False)

        # if we now are in a point in history that was saved, notify self
        #   and img_panel
        if self.app_history.is_saved():
            self.content_saved = True
            self.img_panel.save_notify()

    @debug_fxn
    def on_redo(self, evt):
        """Edit->Redo handler

        Args:
            evt (wx.): TODO
        """
        action = self.app_history.redo()
        LOGGER.info("MSC:redo: %s", repr(action))
        if action[0] == 'MARK':
            self.img_panel.mark_point(action[1])
        if action[0] == 'DELETE_MARK_LIST':
            self.img_panel.delete_mark_point_list(action[1])
        if action[0] == 'MOVE_MARK':
            self.img_panel.move_mark(action[1], action[2], is_selected=False)

        # if we now are in a point in history that was saved, notify self
        #   and img_panel
        if self.app_history.is_saved():
            self.content_saved = True
            self.img_panel.save_notify()

    @debug_fxn
    def on_select_all(self, evt):
        """Edit->Select All handler

        Args:
            evt (wx.): TODO
        """
        self.img_panel.select_all_marks()

    @debug_fxn
    def on_zoomout(self, evt):
        zoom = self.img_panel.zoom(-1)
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

    @debug_fxn
    def on_zoomin(self, evt):
        zoom = self.img_panel.zoom(1)
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

    @debug_fxn
    def on_zoomfit(self, evt):
        zoom = self.img_panel.zoom_fit()
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

    @debug_fxn
    def on_imginfo(self, evt):
        image_info_text = self.img_panel.get_image_info()
        image_dialog = wx.lib.dialogs.ScrolledMessageDialog(
                parent=self,
                msg=image_info_text,
                caption="Image Info",
                size=(800,600),
                )
        image_dialog.ShowModal()

    @debug_fxn
    def on_imgremapcolor(self, evt):
        # TODO: keep track of image operations to save to mcm image and
        #   allow undo
        self.img_panel.image_remap_colormap()

    @debug_fxn
    def on_imginvert(self, evt):
        # TODO: keep track of image operations to save to mcm image and
        #   allow undo
        self.img_panel.image_invert()

    @debug_fxn
    def on_imgautocontrast(self, evt):
        # TODO: keep track of image operations to save to mcm image and
        #   allow undo
        self.img_panel.image_autocontrast()

    @debug_fxn
    def save_notify(self):
        # tell self and children data was saved now
        self.content_saved = True
        self.img_panel.save_notify()
        self.app_history.save_notify()

    @debug_fxn
    def needs_save(self):
        """Function to determine if file has changed since last save or open

        Returns:
            bool: True if file has changed since save or open
        """
        # poll self and children to determine if we need to save document
        return not self.content_saved or self.img_panel.needs_save()

    @debug_fxn
    def save_img_data(self, imdata_path):
        """Save image and mark locations to .mcm zipfile

        Args:
            imdata_path (str): full path to filename to save to
        """
        # make temp file - must make actual file for use with zipfile
        (temp_img_fd, temp_img_name) = tempfile.mkstemp()
        temp_img = os.fdopen(temp_img_fd, mode='wb')
        # copy source image into temp file
        if isinstance(self.img_path, str):
            # pathname
            with open(self.img_path, 'rb') as img_fh:
                temp_img.write(img_fh.read())
        else:
            # zipfile mcm file
            with zipfile.ZipFile(self.img_path[0], 'r') as container_fh:
                temp_img.write(container_fh.open(self.img_path[1]).read())
        temp_img.close()

        # get archive name for image in zip
        if isinstance(self.img_path, str):
            (_, imgfile_ext) = os.path.splitext(self.img_path)
            img_arcname = "image" + imgfile_ext
        else:
            img_arcname = self.img_path[1]

        # write new save file
        try:
            with zipfile.ZipFile(imdata_path, 'w') as container_fh:
                container_fh.write(temp_img_name, arcname=img_arcname)
                container_fh.writestr(
                        "marks.txt",
                        json.dumps(self.img_panel.marks, separators=(',', ':'))
                        )
        except IOError:
            # TODO: need real error dialog
            LOGGER.warning("Cannot save current data in file '%s'.", imdata_path)
        finally:
            os.unlink(temp_img_name)

    @debug_fxn
    def on_about(self, evt):
        """Help->About Menuitem: Open the About window

        Args:
            evt (wx.): TODO
        """
        info = wx.adv.AboutDialogInfo()
        info.SetName("Marcam")
        info.SetVersion(const.VERSION_STR)
        info.SetDescription("Counting objects in images.")
        info.SetCopyright("(C) 2017-2018 Matthew A. Clapp")

        wx.adv.AboutBox(info)

    @debug_fxn
    def on_help(self, evt):
        """Help->Help Menuitem: Open a brief help window (html)

        Args:
            evt (wx.): TODO
        """
        self.html = HelpFrame(self, id=wx.ID_ANY)
        self.html.Show(True)


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


# NOTE: closing window saves size, opening new window uses saved size
class MarcamApp(wx.App):
    @debug_fxn
    def __init__(self, open_files, config_data, *args, **kwargs):
        # reset this before calling super().__init__(), which calls
        #   MacOpenFiles()
        self.file_windows = []
        self.config_data = config_data
        self.last_frame_pos = wx.DefaultPosition
        self.trying_to_quit = False

        # may call MacOpenFiles and add files to self.file_windows and make
        #   new frames
        super().__init__(*args, **kwargs)

        # this next statement can only be after calling __init__ of wx.App
        # gives just window-placeable screen area
        self.display_size = wx.Display().GetClientArea().GetSize()

        if not self.file_windows and not open_files:
            open_files = [None,]

        for open_file in open_files:
            # add to file_windows list of file windows
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
                    new_pos.y = 0
                elif y_too_big:
                    new_pos.x = 0
            self.file_windows.append(
                    ImageWindow(
                        self,
                        open_file,
                        size=new_size,
                        pos=new_pos
                        )
                    )
            self.last_frame_pos = self.file_windows[-1].GetPosition()

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
        for file_window in self.file_windows:
            if file_window.IsActive():
                file_window.on_key_down(evt)

    def on_key_up(self, evt):
        for file_window in self.file_windows:
            if file_window.IsActive():
                file_window.on_key_up(evt)

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

        for frame in self.file_windows:
            if frame.GetId() == frame_to_close_id:
                # we've found frame to close in 'frame'
                break

        # keep_win_open tells close_image() if it should reset the frame's
        #   settings if it successfully closes the image (in anticipation of
        #   keeping the frame open).
        # Logic is identical to (not close_window) with image_closed=True
        # Strictly speaking there is no problem with this being True always,
        #   except that it might possibly take more time.
        keep_win_open = not (
                force_close or
                (len(self.file_windows) > 1 ) or
                (len(self.file_windows) == 1 and from_quit_menu) or
                (
                    len(self.file_windows) == 1 and
                    not from_quit_menu and
                    not from_close_menu and
                    const.PLATFORM != 'mac'
                    )
                )

        # image_closed is False if user clicked "Cancel" when asked to save
        #   otherwise it is True
        image_closed = frame.close_image(keep_win_open=keep_win_open)

        # this tells whether we should continue in the process of closing window
        #   after the return of this function
        close_window = (
                force_close or
                (len(self.file_windows) > 1 and image_closed) or
                (len(self.file_windows) == 1 and image_closed and from_quit_menu) or
                (
                    len(self.file_windows) == 1 and
                    image_closed and
                    not from_quit_menu and
                    not from_close_menu and
                    const.PLATFORM != 'mac'
                    )
                )

        # on Mac, which conditions cause the last window to stay open and hid
        hide_window = (
            not force_close and
            (len(self.file_windows) == 1) and
            image_closed and
            not from_quit_menu and
            (const.PLATFORM == 'mac')
        )

        # if hide_window is True, close_window must also be False
        assert (hide_window and not close_window) or not hide_window

        if close_window:
            self.file_windows.remove(frame)

        if hide_window:
            # on Mac we hide the last frame we close.
            frame.Hide()

        veto_close = not close_window

        return veto_close

    @debug_fxn
    def new_frame_open_file(self, open_file):
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
        self.file_windows.append(
                ImageWindow(
                    self,
                    open_file,
                    size=new_size,
                    pos=new_pos
                    )
                )
        self.last_frame_pos = self.file_windows[-1].GetPosition()

    @debug_fxn
    def quit_app(self):
        self.trying_to_quit = True
        open_windows = self.file_windows.copy()
        for frame in open_windows:
            frame.close_source = 'quit_menu'
            frame_closed = frame.Close()
            if not frame_closed:
                break
        self.trying_to_quit = False

    @debug_fxn
    def MacOpenFiles(self, fileNames):
        """wx.PyApp standard function, over-ridden to accept Cocoa
        "openFiles" events

        Args:
            fileNames: list of file names to open
        """
        # NOTE: works great in bundled app,
        #   but cmd-line invocation causes fileNames to be last argument
        #       of cmd-line, even if that's the script name
        # TODO: figure out how to ignore bad openFiles from command-line
        LOGGER.debug(fileNames)
        for open_file in fileNames:
            # open in blank window, or
            #   add to file_windows list of file windows
            if not self.file_windows or self.file_windows[0].has_image():
                self.new_frame_open_file(open_file)
            else:
                self.file_windows[0].open_image(open_file)

    def OnExit(self):
        # save config_data right before app is about to exit
        save_config(self.config_data)
        return super().OnExit()

    # TODO: can use this to determine if last closed window shuts down app
    #def SetExitOnFrameDelete(self, flag)

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

def debug_main():
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

def main(argv=None):
    """Main entrance into app.  Setup logging, create App, and enter main loop
    """
    # process command line if started from there
    # Also, py2app sends file(s) to open via argv if file is dragged on top
    #   of the application icon to start the icon
    args = process_command_line(argv)

    # if -d or --debug turn on full debug
    if args.debug:
        log_level = logging.DEBUG
    else:
        # default loglevel
        log_level = logging.INFO

    # setup logging
    logging_setup(log_level)

    # fetch configuration from file
    config_data = load_config()

    # get basic debug info
    debug_main()

    # see what argv and args are
    LOGGER.info(repr(args))

    # setup main wx event loop
    myapp = MarcamApp(args.srcfiles, config_data)
    myapp.MainLoop()

    # return 0 to indicate "status OK"
    return 0


if __name__ == "__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130
    except:
        LOGGER.error("UNCAUGHT FATAL ERROR", exc_info=True)
        status = 1

    sys.exit(status)
