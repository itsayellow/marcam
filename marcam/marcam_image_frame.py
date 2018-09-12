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


from datetime import datetime
import json
import logging
import pathlib
import re
import shutil
import sys
import tempfile
import time

import wx
import wx.adv
import wx.lib.dialogs

import image_proc
from image_scrolled_canvas_marks import ImageScrolledCanvasMarks
import const
import common
import longtask
import marcam_extra
import mcmfile


# global logger obj for this file
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug, common.DEBUG_FXN_STATE)

class ImageFrame(wx.Frame):
    """Application Level Frame, one for each open image file.
    """
    def __init__(self, parent, **kwargs):
        # no parent window, so use None as only *arg
        super().__init__(None, **kwargs)

        # internal state
        self.frame_history = marcam_extra.EditHistory()
        self.img_path = None # NONE or pathlib.Path
        self.save_filepath = None # NONE or pathlib.Path
        self.temp_scroll_zoom_state = None
        self.parent = parent
        self.close_source = None
        # make dir for saving cache images of this window
        const.USER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.cache_dir = tempfile.mkdtemp(dir=const.USER_CACHE_DIR)

        # GUI-related
        self.html = None
        self.mark_tool_id = None
        self.select_tool_id = None
        self.mark_menu_item = None
        self.select_menu_item = None
        self.open_recent_menu = None
        self.toolbar = None
        self.started_temp_zoom = False
        self.menu_items_disable_no_image = None

        # FileHistory is held in MarcamApp parent
        self.file_history = self.parent.file_history

        if LOGGER.isEnabledFor(logging.DEBUG):
            start_time = time.time()
        self.init_ui()
        if LOGGER.isEnabledFor(logging.DEBUG):
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
        self.open_recent_menu = wx.Menu()
        file_menu = wx.Menu()
        file_open_item = file_menu.Append(wx.ID_OPEN,
                'Open Image...\tCtrl+O',
                'Open image file'
                )
        file_menu.AppendSubMenu(self.open_recent_menu,
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
        tools_imgautocontrastdialog_item = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast...",
                )
        self.tools_imgautocontrastlast_item = tools_menu.Append(wx.ID_ANY,
                "Image &Auto-Contrast (%d)\tShift+Ctrl+J"%(
                    self.parent.get_last_autocontrast_level(),
                    )
                )
        tools_imgfcolordialog_item = tools_menu.Append(wx.ID_ANY,
                "Image False Color...",
                )
        self.tools_imgfcolorlast_item = tools_menu.Append(wx.ID_ANY,
                "Image False Color (%s)\tShift+Ctrl+C"%(
                    self.parent.get_last_falsecolor().capitalize()
                    ),
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

        if LOGGER.isEnabledFor(logging.DEBUG):
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
                #file_save_item, # under EditHistory control
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
                tools_imgautocontrastdialog_item,
                self.tools_imgautocontrastlast_item,
                tools_imgfcolordialog_item,
                self.tools_imgfcolorlast_item,
                ]

        # register Open Recent menu, put under control of FileHistory obj
        self.file_history.UseMenu(self.open_recent_menu)
        self.file_history.AddFilesToMenu(self.open_recent_menu)

        # register Save, Undo, Redo menu items so EditHistory obj can
        #   enable or disable them as needed
        self.frame_history.register_save_menu_item(file_save_item)
        self.frame_history.register_undo_menu_item(edit_undo_item)
        self.frame_history.register_redo_menu_item(edit_redo_item)


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
        selectbmp = wx.Bitmap(str(const.SELECTBMP_FNAME))
        markbmp = wx.Bitmap(str(const.MARKBMP_FNAME))
        toclipbmp = wx.Bitmap(str(const.TOCLIPBMP_FNAME))
        zoomoutbmp = wx.Bitmap(str(const.ZOOMOUTBMP_FNAME))
        zoomfitbmp = wx.Bitmap(str(const.ZOOMFITBMP_FNAME))
        zoominbmp = wx.Bitmap(str(const.ZOOMINBMP_FNAME))

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

        # For marks display, find text width of "9999", to leave enough
        #   padding to have space to contain "999"
        self.toolbar.AddControl(wx.StaticText(self.toolbar, wx.ID_ANY, "Marks:"))
        # throwaway object with default constructor (with parent)
        #   to set default font for get_text_width_px
        textctrl_deleteme = wx.TextCtrl(self.toolbar)
        text_width_px = common.get_text_width_px(textctrl_deleteme, "9999")
        textctrl_deleteme.Destroy()
        self.marks_num_display = wx.TextCtrl(
                self.toolbar,
                wx.ID_ANY,
                size=wx.Size(text_width_px, -1),
                #style=wx.TE_READONLY | wx.BORDER_NONE
                style=wx.TE_READONLY
                )
        self.toolbar.AddControl(self.marks_num_display)
        tocliptool = self.toolbar.AddTool(
                wx.ID_ANY, 'Copy', toclipbmp,
                'Copy to Clipboard'
                )
        self.toolbar.Realize()

        # Setup StatusBar
        #   Field 0 is operating messages, menu hints, etc.
        #   Field 1 is current zoom ratio.
        self.statusbar = self.CreateStatusBar(
                number=2,
                style=wx.STB_DEFAULT_STYLE,
                )
        self.statusbar.SetFieldsCount(
                2,
                [-1, common.get_text_width_px(self.statusbar, "Zoom: 99999.9%")]
                )

        # Panel keeps things from spilling over the frame, statusbar, etc.
        #   also accepts key focus
        #   probably with more than one Panel we need to worry about which
        #       has keyboard focus
        # ImageScrolledCanvas is the cleanest, fastest implementation for
        #   what we need
        self.img_panel = ImageScrolledCanvasMarks(
                self,
                win_history=self.frame_history,
                marks_num_update_fxn=self.marks_num_update,
                cache_dir=self.cache_dir,
                # the following always makes scrollbars,
                #   Mac: they appear tiny and all the way to 0 (not
                #       disabled, and bad looking)
                #   Win: they appear properly disabled when canvas not bigger
                #style=wx.HSCROLL|wx.VSCROLL|wx.ALWAYS_SHOW_SB
                )
        # make ImageScrolledCanvas Drag and Drop Target
        self.img_panel.SetDropTarget(marcam_extra.FileDropTarget(self.img_panel))

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
        self.Bind(wx.EVT_MENU, self.on_imgautocontrastdialog, tools_imgautocontrastdialog_item)
        self.Bind(wx.EVT_MENU, self.on_imgautocontrastlast, self.tools_imgautocontrastlast_item)
        self.Bind(wx.EVT_MENU, self.on_imgfalsecolordialog, tools_imgfcolordialog_item)
        self.Bind(wx.EVT_MENU, self.on_imgfalsecolorlast, self.tools_imgfcolorlast_item)
        # Help menu items
        self.Bind(wx.EVT_MENU, self.on_about, help_about_item)
        self.Bind(wx.EVT_MENU, self.on_help, help_help_item)

        self.SetTitle('Marcam')

        # set icon in title bar for Windows (and unix?)
        my_icon_bundle = wx.IconBundle(str(const.ICON_DIR / 'marcam.ico'))
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
        """Bring window to the front and make the active window
        """
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
        """Convenience function returning whether img_panel has image.
        """
        return not self.img_panel.has_no_image()

    @debug_fxn
    def on_window_menu_activate(self, evt):
        """Activate this frame when it's selected from Window menu.  Used by
            FrameList.

        Also unchecks the menu item in other frame that was clicked.
        (Clicking on that item automatically checks it.)
        """
        # Activate this frame.
        self.activate()
        # Uncheck window entry in menu of other frame.  (User click checks it.)
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
            # remove cache dir for this window
            shutil.rmtree(self.cache_dir)
            winsize = self.GetSize()
            self.parent.config_data['winsize'] = list(winsize)
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
            evt (wx.KeyEvent): wx Event for this handler
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
                    self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100), 1)

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
            evt (wx.KeyEvent): wx Event for this handler
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
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100), 1)

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
        """File->Open Image... menu handler for Main Window

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
                    style=wx.OK | wx.ICON_EXCLAMATION
                    ).ShowModal()

    @debug_fxn
    def on_open_recent(self, evt):
        """File->Open Recent-> sub-menu handler for Main Window

        Args:
            evt (wx.CommandEvent): wx Event for this handler
        """
        # get path from file_history
        img_path = pathlib.Path(
                self.file_history.GetHistoryFile(evt.GetId() - wx.ID_FILE1)
                )
        if img_path.exists():
            img_ok = self.open_image(img_path)
            if not img_ok:
                # wx.ICON_ERROR has no effect on Mac
                wx.MessageDialog(None,
                        message="Unable to open file: %s"%img_path,
                        caption="File Read Error",
                        style=wx.OK | wx.ICON_EXCLAMATION
                        ).ShowModal()
        else:
            self.file_history.RemoveFileFromHistory(evt.GetId() - wx.ID_FILE1)
            wx.MessageDialog(self,
                    message="Unable to find file: %s"%img_path,
                    caption="File Not Found",
                    style=wx.OK
                    ).ShowModal()

    @debug_fxn
    def open_image(self, img_path):
        """Open new image, in this frame if it has no file, otherwise
        in new frame.

        Currently every function that calls this implements and error
        dialog if img_ok is returned False

        Args:
            img_path (pathlike): full path to image to open

        Returns:
            (bool) img_ok - whether image was successfully loaded into current
                or new frame
        """
        img_path = pathlib.Path(img_path)

        if self.img_panel.has_no_image():
            img_ok = self.open_image_this_frame(img_path)
        else:
            img_ok = self.parent.new_frame_open_file(img_path)

        return img_ok

    @debug_fxn
    def open_image_this_frame(self, img_path):
        """Open new image in this frame.

        Args:
            img_path (pathlike): full path to image.

        Returns:
            (bool) img_ok - whether image was successfully loaded into frame
        """
        img_path = pathlib.Path(img_path)

        if img_path.suffix == ".mcm":
            img_ok = self.load_mcmfile_from_path(img_path)
        else:
            # image or *.1sc file
            img_ok = self.load_image_from_file(img_path)
            # By not calling self.frame_history.save_notify(), indicate needs save

        if img_ok:
            zoom = self.img_panel.get_zoom_val()
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100), 1)
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
            imdata_path (pathlike): path to .mcm file to open
        """
        imdata_path = pathlib.Path(imdata_path)
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
            # self.img_path if from mcm is file path to file
            self.img_path = imdata_path
            self.save_filepath = imdata_path
            # Set window title to filename
            self.SetTitle(str(imdata_path.name))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(str(imdata_path))
            # on Mac update Window menu frame list with new title
            self.parent.file_windows.update_window_menu()
            # add successful file open to file history
            self.file_history.AddFileToHistory(str(imdata_path))
            # we just loaded .mcm file, so have nothing to save
            self.frame_history.save_notify()

        # img_ok will only be True if we successfully loaded file
        return img_ok

    @debug_fxn
    def load_image_from_file(self, img_file):
        """Given full (non *.mcm) img_file, load image into app

        Separate from on_open so we can use this with argv_emulation

        Args:
            img_file (pathlike): full path to image file (JPG, TIFF, etc.)
        """
        img_file = pathlib.Path(img_file)
        img_ok = False

        # check for 1sc files and get image data to send to Image

        if img_file.suffix == ".1sc":
            img = image_proc.file1sc_to_image(img_file)
        else:
            # disable logging, we don't care if there is e.g. TIFF image
            #   with unknown fields
            no_log = wx.LogNull()

            img = wx.Image(str(img_file))

            # re-enable logging
            del no_log

        # check if img loaded ok
        img_ok = img and img.IsOk()

        if img_ok:
            # reset img history in window to only new image, reset idx
            self.img_panel.new_img(img)
            # init image in window
            self.img_panel.init_image()
            # reset filepath for mcm file to nothing if we load new image
            self.img_path = img_file
            self.save_filepath = None
            # Set window title to filename
            self.SetTitle(str(img_file.name))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(str(img_file))
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
            image_to_close = self.img_path.name

            # changes list
            changes_list = self.frame_history.get_actions_since_save()
            if len(changes_list) > 4:
                extra_str = "[%d more...]"%(len(changes_list) - 3)
                changes_list = changes_list[:3] + [extra_str,]
            if changes_list is not None:
                changes_str = "\n".join(["    \u2022 "+x for x in changes_list])

            save_query = wx.MessageDialog(
                    self,
                    "\nChanges since last save:\n%s\n"%changes_str,
                    "Save changes to \"%s\" before closing?"%image_to_close,
                    wx.CANCEL | wx.YES_NO | wx.YES_DEFAULT
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
            # Set window title to generic app name
            self.SetTitle('Marcam')
            # Reset zoom portion of statusbar to show nothing
            self.statusbar.SetStatusText("", 1)

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
            # Normal Save
            longtask.ThreadedProgressPulse(
                    thread_fxn=self.on_save_thread,
                    thread_fxn_args=(),
                    post_thread_fxn=self.on_save_postthread,
                    progress_title="Saving Image",
                    progress_msg="Saving %s..."%self.save_filepath.name,
                    parent=self
                    )

    @debug_fxn
    def on_save_thread(self):
        """Thread portion of File->Save menu handler

        Returns:
            (bool): whether file was saved ok (to be passed to
                on_save_posttthread).
        """
        # use current filename/path to save
        save_ok = self.save_img_data(self.save_filepath)
        return save_ok

    @debug_fxn
    def on_save_postthread(self, save_ok):
        """Post-Thread portion of File->Save handler

        Args:
            save_ok (bool): whether file was saved successfully in
                on_save_thread
        """
        if save_ok:
            # signify we have saved content
            self.frame_history.save_notify()
        else:
            # error in saving dialog
            # wx.ICON_ERROR has no effect on Mac
            wx.MessageDialog(None,
                    message="Unable to save file: %s"%self.save_filepath,
                    caption="File Write Error",
                    style=wx.OK | wx.ICON_EXCLAMATION
                    ).ShowModal()

    @debug_fxn
    def on_saveas(self, _evt):
        """File->Save As... menu handler for Main Window

        Args:
            _evt (wx.CommandEvent):
        """
        if self.save_filepath is not None:
            default_dir = self.save_filepath.parent
            default_filename = self.save_filepath.name
        else:
            default_dir = self.img_path.parent
            default_filename = self.img_path.with_suffix(".mcm").name

        # native Mac open dialog has no title message
        with wx.FileDialog(
                self,
                "" if const.PLATFORM == 'mac' else "Save MCM file",
                wildcard="MCM files (*.mcm)|*.mcm",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultDir=str(default_dir),
                defaultFile=str(default_filename),
                ) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # save the current contents in the file
            pathname = pathlib.Path(file_dialog.GetPath())

            longtask.ThreadedProgressPulse(
                    thread_fxn=self.on_saveas_thread,
                    thread_fxn_args=(pathname,),
                    post_thread_fxn=self.on_saveas_postthread,
                    progress_title="Saving Image",
                    progress_msg="Saving %s..."%pathname.name,
                    parent=self
                    )

    @debug_fxn
    def on_saveas_thread(self, pathname):
        """Thread portion of File->Save As... menu handler

        Args:
            pathname (pathlib.Path): full path to save image file
        """
        save_ok = self.save_img_data(pathname)
        return (save_ok, pathname)

    @debug_fxn
    def on_saveas_postthread(self, save_ok, pathname):
        """Post-Thread portion of File->Save As... menu handler

        Args:
            save_ok (bool): whether file was saved successfully
            pathname (pathlib.Path): full path image file was saved to
        """
        if save_ok:
            self.save_filepath = pathname
            # set img_path
            self.img_path = pathname
            # signify we have saved content
            self.frame_history.save_notify()
            # add successful file save as to file history
            self.file_history.AddFileToHistory(str(pathname))
            # Set window title to newly-saved filename
            self.SetTitle(str(pathname.name))
            # on Mac sets file icon in titlebar with right-click showing
            #   dir hierarchy
            self.SetRepresentedFilename(str(pathname))
            # on Mac update Window menu frame list with new title
            self.parent.file_windows.update_window_menu()
        else:
            # error in saving dialog
            # wx.ICON_ERROR has no effect on Mac
            wx.MessageDialog(None,
                    message="Unable to save file: %s"%pathname,
                    caption="File Write Error",
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
            #   thus use self.img_path
            img_path = self.img_path

        # create new filename based on old one but ending with _export.png
        default_dir = img_path.parent
        default_filename = img_path.stem + "_export.png"

        # native Mac open dialog has no title message
        with wx.FileDialog(
                self,
                "" if const.PLATFORM == 'mac' else "Export Image and Marks as Image",
                wildcard=wx.Image.GetImageExtWildcard(),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultDir=str(default_dir),
                defaultFile=default_filename,
                ) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # save the current contents in the file
            pathname = file_dialog.GetPath()
            # saves from memorydc
            export_image = self.img_panel.export_to_image_marks()
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
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100), 1)

    @debug_fxn
    def on_zoomin(self, _evt):
        """View->Zoom In menu/toolbar button handler

        Args:
            _evt (wx.CommandEvent):
        """
        zoom = self.img_panel.zoom(1)
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100), 1)

    @debug_fxn
    def on_zoomfit(self, _evt):
        """View->Zoom to Fit menu/toolbar button handler

        Args:
            _evt (wx.CommandEvent):
        """
        zoom = self.img_panel.zoom_fit()
        if zoom:
            self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100), 1)

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
    def on_imgfalsecolordialog(self, _evt):
        """Tools->False Color... menu item

        Args:
            _evt (wx.CommandEvent):
        """
        dialog = marcam_extra.ImageFalseColorDialog(
                self,
                wx.ID_ANY,
                style=wx.DEFAULT_DIALOG_STYLE
                )
        dialog_val = dialog.ShowModal()
        if dialog_val == wx.ID_OK:
            cmap = dialog.get_colormap()
            self.parent.set_last_falsecolor(cmap=cmap)
            self.img_panel.image_remap_colormap(cmap=cmap)

    @debug_fxn
    def on_imgfalsecolorlast(self, _evt):
        """Tools->False Color menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_remap_colormap(
                cmap=self.parent.get_last_falsecolor()
                )

    @debug_fxn
    def on_imgautocontrastdialog(self, _evt):
        """Tools->Image Auto-Contrast... menu item

        Args:
            _evt (wx.CommandEvent):
        """
        dialog = marcam_extra.ImageAutoContrastDialog(
                self,
                wx.ID_ANY,
                style=wx.DEFAULT_DIALOG_STYLE
                )
        dialog_val = dialog.ShowModal()
        if dialog_val == wx.ID_OK:
            slider_val = dialog.slider.GetValue()
            self.parent.set_last_autocontrast_level(level=slider_val)
            self.img_panel.image_autocontrast(cutoff=slider_val)

    @debug_fxn
    def on_imgautocontrastlast(self, _evt):
        """Tools->Image Auto-Contrast 0 menu item

        Args:
            _evt (wx.CommandEvent):
        """
        self.img_panel.image_autocontrast(
                cutoff=self.parent.get_last_autocontrast_level()
                )

    @debug_fxn
    def save_img_data(self, imdata_path):
        """Save image and mark locations to .mcm file

        Args:
            imdata_path (pathlike): full path to filename to save to
        """
        returnval = mcmfile.save(
                imdata_path,
                self.img_panel.get_current_img(),
                self.img_panel.marks
                )
        return returnval

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
        self.html = marcam_extra.HelpFrame(self, id=wx.ID_ANY)
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
        """Companion to on_debug_benchzoom that executes one zoom level and
            sets timer to call itself again until done.
        """
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
            data_filename = const.USER_LOG_DIR / \
                    "data_benchzoom_" + benchzoom_data['datetime'] + ".json"
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
