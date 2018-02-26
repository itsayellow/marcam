#!/usr/bin/env python3
#
# GUI for displaying an image and counting cells

import argparse
import json
import logging
import os
import os.path
import platform
import sys
import tempfile
import time
import zipfile

import wx
import wx.adv
import wx.html2
import numpy as np

import biorad1sc_reader
from biorad1sc_reader import BioRadInvalidFileError, BioRadParsingError

from image_scrolled_canvas import ImageScrolledCanvasMarks
import const
import common

# DEBUG sets global debug message verbosity

# NOTE: wx.DC.GetAsBitmap() to grab a DC as a bitmap


EXE_DIR = os.path.dirname(os.path.realpath(__file__))
# for now the paths are the same
ICON_DIR = EXE_DIR

# which modules are we logging
LOGGED_MODULES = [__name__, 'image_scrolled_canvas']

# global logger obj for this file
LOGGER = logging.getLogger(__name__)

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER)


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
def create_config_file(config_filepath):
    config_data = {}
    config_data['winsize'] = [800, 600]
    config_data['debug'] = False

    try:
        with open(config_filepath, 'w') as config_fh:
            json.dump(
                    config_data,
                    config_fh,
                    )
    except:
        # TODO specific exception
        LOGGER.warn("Can't create config file: %s", config_filepath)
        return config_data

    return config_data

@debug_fxn
def load_config():
    config_data = None

    # create config dir if necessary
    os.makedirs(const.USER_CONFIG_DIR, exist_ok=True)

    config_filepath = os.path.join(
            const.USER_CONFIG_DIR,
            "config.json"
            )
    # if no config.json file, create
    try:
        with open(config_filepath, 'r') as config_fh:
            config_data = json.load(config_fh)
    except:
        # TODO specific exception
        config_data = create_config_file(config_filepath)

    return config_data 

@debug_fxn
def save_config(config_data):
    config_data = None

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


class DropTarget(wx.FileDropTarget):
    """DropTarget Facilitating dragging file into window to open
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
        self.window_target.init_image_from_file(filename)

        # TODO: which one of these??
        #return wx.DragCopy
        return True


class ImageWindow(wx.Frame):
    def __init__(self, parent, srcfile, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # internal state
        self.app_history = EditHistory()
        self.content_saved = True
        self.img_path = None
        self.save_filepath = None
        self.temp_scroll_zoom_state = None
        self.parent = parent

        # GUI-related
        self.html = None
        self.mark_tool_id = None
        self.select_tool_id = None
        self.mark_menu_item = None
        self.select_menu_item = None
        self.toolbar = None

        # App configuration
        self.config = wx.Config("Marcam", "itsayellow.com")

        # File history
        self.file_history = wx.FileHistory()
        self.file_history.Load(self.config)

        self.init_ui()
        if srcfile is not None:
            # TODO: are we able to load more than one file?
            if srcfile.endswith(".mcm"):
                self.load_mcmfile_from_path(srcfile)
            else:
                self.load_image_from_file(srcfile)

    @debug_fxn
    def init_ui(self):
        """Initialize the GUI widgets of the main window
        """
        # menu bar stuff
        menubar = wx.MenuBar()
        # File
        open_recent_menu = wx.Menu()
        file_menu = wx.Menu()
        oitem = file_menu.Append(wx.ID_OPEN,
                'Open Image...\tCtrl+O', 'Open image file'
                )
        orecentitem = file_menu.Append(wx.ID_ANY,
                'Open Recent', open_recent_menu, 'Open recent .mcm files')
        citem = file_menu.Append(wx.ID_CLOSE,
                'Close\tCtrl+W', 'Close image'
                )
        sitem = file_menu.Append(wx.ID_SAVE,
                'Save Image Data\tCtrl+S', 'Save .mcm image and data file'
                )
        saitem = file_menu.Append(wx.ID_SAVEAS,
                'Save Image Data As...\tShift+Ctrl+S',
                'Save .mcm image and data file'
                )
        eiitem = file_menu.Append(wx.ID_SAVEAS,
                'Export Image...\tCtrl+E',
                'Export image with marks to image file'
                )
        # TODO: On Windows Ctrl+Q doesn't appear, need to be Alt-F4?
        quititem = file_menu.Append(wx.ID_EXIT,
                'Quit', 'Quit application\tCtrl+Q'
                )
        menubar.Append(file_menu, '&File')
        # Edit
        edit_menu = wx.Menu()
        undoitem = edit_menu.Append(wx.ID_UNDO,
                'Undo\tCtrl+Z', 'Undo last action')
        redoitem = edit_menu.Append(wx.ID_REDO,
                'Redo\tShift+Ctrl+Z', 'Redo last undone action')
        self.selallitem = edit_menu.Append(wx.ID_SELECTALL,
                'Select All\tCtrl+A', 'Select all marks')
        menubar.Append(edit_menu, '&Edit')
        # Tools
        tools_menu = wx.Menu()
        self.select_menu_item = tools_menu.Append(wx.ID_ANY, "&Select Mode\tCtrl+T")
        # we start in select mode, so disable menu to enable select mode
        self.select_menu_item.Enable(False)
        self.mark_menu_item = tools_menu.Append(wx.ID_ANY, "&Mark Mode\tCtrl+M")
        menubar.Append(tools_menu, "&Tools")
        # Help
        help_menu = wx.Menu()
        aboutitem = help_menu.Append(wx.ID_ABOUT, "&About Marcam")
        helpitem = help_menu.Append(wx.ID_HELP, "&Marcam Help")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        # register Open Recent menu, put under control of FileHistory obj
        self.file_history.UseMenu(open_recent_menu)
        self.file_history.AddFilesToMenu()

        # register Undo, Redo menu items so EditHistory obj can
        #   enable or disable them as needed
        self.app_history.register_undo_menu_item(undoitem)
        self.app_history.register_redo_menu_item(redoitem)

        # toolbar stuff
        self.toolbar = self.CreateToolBar()
        LOGGER.info("MSC:ICON_DIR=%s", ICON_DIR)
        #obmp = wx.Bitmap(os.path.join(ICON_DIR, 'topen32.png'))
        #otool = self.toolbar.AddTool(wx.ID_OPEN, 'Open', obmp)
        selectbmp = wx.Bitmap(os.path.join(ICON_DIR, 'pointer32.png'))
        selecttool = self.toolbar.AddRadioTool(wx.ID_ANY, 'Select Mode', selectbmp)
        self.select_tool_id = selecttool.GetId()
        markbmp = wx.Bitmap(os.path.join(ICON_DIR, 'marktool32.png'))
        marktool = self.toolbar.AddRadioTool(wx.ID_ANY, 'Mark Mode', markbmp)
        self.mark_tool_id = marktool.GetId()
        self.toolbar.Realize()

        # status bar stuff
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText('Ready.')

        # Panel keeps things from spilling over the frame, statusbar, etc.
        #   also accepts key focus
        #   probably with more than one Panel we need to worry about which
        #       has keyboard focus

        # find text width of "9999", to leave enough padding to have space
        #   to contain "999"
        screen_dc = wx.ScreenDC()
        screen_dc.SetFont(self.GetFont())
        (text_width_px, _) = screen_dc.GetTextExtent("9999")
        del screen_dc

        # init marks_num_display before ImageScrolledCanvas so ISC can
        #   update number on its init
        # using TextCtrl to allow copy to clipboard
        self.marks_num_display = wx.TextCtrl(
                self, wx.ID_ANY, size=wx.Size(text_width_px, -1),
                style=wx.TE_READONLY | wx.BORDER_NONE
                )
        # set color to be the same as background color
        #self.marks_num_display.SetBackgroundColour(
        #        wx.SystemSettings().GetColour(wx.SYS_COLOUR_BACKGROUND)
        #        )

        # ImageScrolledCanvas is the cleanest, fastest implementation for
        #   what we need
        self.img_panel = ImageScrolledCanvasMarks(
                self,
                self.app_history,
                self.marks_num_update
                )
        # make ImageScrolledCanvas Drag and Drop Target
        self.img_panel.SetDropTarget(DropTarget(self.img_panel))

        # Horizontal sizer for home-made toolbar to allow for mark count
        mytoolbar = wx.BoxSizer(wx.HORIZONTAL)
        #but1 = wx.Button(self, wx.ID_ANY, style=wx.BU_EXACTFIT)
        #but1.SetBitmap(obmp)
        #but2 = wx.Button(self, wx.ID_ANY, style=wx.BU_EXACTFIT)
        #but2.SetBitmap(markbmp)
        #mytoolbar.Add(
        #        but1,
        #        proportion=0, flag=0, border=0
        #        )
        #mytoolbar.Add(
        #        but2,
        #        proportion=0, flag=0, border=0
        #        )
        mytoolbar.AddStretchSpacer(1)
        mytoolbar.Add(
                wx.StaticText(self, wx.ID_ANY, "Marks:"),
                proportion=0, flag=0, border=0)
        mytoolbar.Add(self.marks_num_display, proportion=0, flag=0, border=0)

        # Vertical top-level sizer for main window
        mybox = wx.BoxSizer(wx.VERTICAL)
        # Don't stretch vertical of toolbar,
        #   expand horiz to fill window width
        mybox.Add(mytoolbar, proportion=0, flag=wx.EXPAND)
        # Fully stretch vertical of img panel to fill window,
        #   expand horiz to fill window width
        mybox.Add(self.img_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(mybox)

        # setup event handlers for Frame events
        self.Bind(wx.EVT_CLOSE, self.on_evt_close)

        # setup event handlers for toolbar
        self.Bind(wx.EVT_TOOL, self.on_selectmode, selecttool)
        self.Bind(wx.EVT_TOOL, self.on_markmode, marktool)

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
        self.Bind(wx.EVT_MENU, self.on_select_all, self.selallitem)
        # Tools menu items
        self.Bind(wx.EVT_MENU, self.on_selectmode, self.select_menu_item)
        self.Bind(wx.EVT_MENU, self.on_markmode, self.mark_menu_item)
        # Help menu items
        self.Bind(wx.EVT_MENU, self.on_about, aboutitem)
        self.Bind(wx.EVT_MENU, self.on_help, helpitem)

        # finally render app
        self.SetSize((800, 600))
        self.SetTitle('Marcam')
        #self.Centre()

        #self.img_panel.subpanel.Centre()

        self.Show(True)

        LOGGER.info(
                "MSC:self.img_panel size: %s",
                repr(self.img_panel.GetClientSize())
                )

    @debug_fxn
    def register_key_bind(self, key_bind_fxn):
        self.key_bind_fxn = key_bind_fxn

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
        return self.img_panel.img_dc is not None
    
    @debug_fxn
    def on_evt_close(self, evt):
        """EVT_CLOSE Handler: anytime user quits program in any way

        Args:
            evt (wx.): TODO
        """
        self.file_history.Save(self.config)
        evt.Skip()

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

        if key_code == 91:
            # [ key
            #  key_code: 91
            #  RawKeyCode: 33
            # zoom out
            zoom = self.img_panel.zoom(-1)
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))
        if key_code == 93:
            # ] key
            #  key_code: 93
            #  RawKeyCode: 30
            # zoom in
            zoom = self.img_panel.zoom(1)
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

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

        if key_code == 307:
            # option key - initiate temporary zoom
            LOGGER.debug("Option key down")

            # save zoom / scroll state
            self.temp_scroll_zoom_state = self.img_panel.get_scroll_zoom_state()

            zoom = self.img_panel.zoom_point(
                    const.TEMP_ZOOM,
                    evt.GetPosition()
                    )
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

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

        if key_code == 307:
            # option key - release temporary zoom
            LOGGER.debug("Option key up")

            self.img_panel.set_scroll_zoom_state(
                    self.temp_scroll_zoom_state
                    )

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
    def on_open(self, evt):
        """File->Open Image Data... menu handler for Main Window

        Args:
            evt (wx.): TODO
        """
        # create wildcard for:
        #   native *.mcm files
        #   Image files
        #   *.1sc files (Bio-Rad)
        wildcard_mcm = "Marcam Image Data files (*.mcm)|*.mcm|"
        wildcard_img = "Image Files " + wx.Image.GetImageExtWildcard() + "|"
        wildcard_1sc = "Bio-Rad 1sc Files|*.1sc"
        wildcard = wildcard_mcm + wildcard_img + wildcard_1sc
        open_file_dialog = wx.FileDialog(self,
                "Open Image file",
                wildcard=wildcard,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_file_dialog.ShowModal() == wx.ID_CANCEL:
            # the user canceled
            return

        # get filepath and attempt to open image into bitmap
        img_path = open_file_dialog.GetPath()

        # TODO: img_panel needs fxn to ask if no image
        if self.img_panel.img_dc is not None:
            self.parent.new_frame_open_file(img_path)
        else:
            self.open_image(img_path)

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

        # first close current image (if it exists)
        is_closed = self.on_close(None)

        if not is_closed:
            return

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
                # reset filepath for mcm file to nothing if we load new image
                # self.img_path if from zip is list, zipfile, member_name
                self.img_path = [imdata_path, img_name]
                self.save_filepath = None
                self.statusbar.SetStatusText(
                        "Image Data " + imdata_path + " loaded OK."
                        )
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
        """Given full img_file, load image into app

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
        else:
            self.statusbar.SetStatusText(
                    "Image " + img_file + " loading ERROR."
                    )

    @debug_fxn
    def on_close(self, evt):
        self.parent.close_frame(self.GetId())

    @debug_fxn
    def close_image(self, keep_win_open=False):
        """Close Image menu handler for Main Window

        Args:
            evt (wx.): TODO
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
        # use wx.html2 to allow better rendering (and CSS in future)
        self.html = wx.html2.WebView.New(self)
        self.html.LoadURL('file://' + os.path.join(ICON_DIR, 'marcam_help.html'))

        self.SetTitle("Marcam Help")
        self.SetSize((500, 600))

# TODO: investigate wx.PyApp, including wx.PyApp.Mac* functions
class MarcamApp(wx.App):
    @debug_fxn
    def __init__(self, open_files, config_data, *args, **kwargs):
        # reset this before calling super().__init__(), which calls
        #   MacOpenFiles()
        self.file_windows = []

        super().__init__(*args, **kwargs)

        self.config_data = config_data

        if not self.file_windows and not open_files:
            open_files = [None,]

        for open_file in open_files:
            # add to file_windows list of file windows
            self.file_windows.append(ImageWindow(self, open_file, None))

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
        # TODO: handle App global events: Quit, New..., Open...
        for file_window in self.file_windows:
            if file_window.IsActive():
                file_window.on_key_down(evt)

    def on_key_up(self, evt):
        # TODO: handle App global events: Quit, New..., Open...
        for file_window in self.file_windows:
            if file_window.IsActive():
                file_window.on_key_up(evt)

    @debug_fxn
    def close_frame(self, frame_to_close_id, force_close=False):
        frame_closed = False

        for frame in self.file_windows:
            if frame.GetId() == frame_to_close_id:
                keep_win_open = not force_close and not len(self.file_windows) > 1
                frame_closed = frame.close_image(keep_win_open)

                if not keep_win_open and frame_closed:
                    self.file_windows.remove(frame)
                    frame.Close()
                break
        return frame_closed

    @debug_fxn
    def new_frame_open_file(self, open_file):
        self.file_windows.append(ImageWindow(self, open_file, None))

    @debug_fxn
    def quit_app(self):
        open_windows = self.file_windows.copy()
        for frame in open_windows:
            frame_closed = self.close_frame(frame.GetId(), force_close=True)
            if not frame_closed:
                break

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
            # TODO: img_panel needs fxn to ask if no image
            if not self.file_windows or self.file_windows[0].has_image():
                self.new_frame_open_file(open_file)
            else:
                self.file_windows[0].open_image(open_file)

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
