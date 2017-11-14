#!/usr/bin/env python3
#
# GUI for displaying an image and counting cells

import sys
import argparse
import os.path
import zipfile
import json
import wx
import wx.adv
import wx.html
import numpy as np
import biorad1sc_reader
from biorad1sc_reader import BioRadInvalidFileError, BioRadParsingError

from image_scrolled_canvas import ImageScrolledCanvas

import const
from const import (
        DEBUG, DEBUG_FXN_ENTRY, DEBUG_KEYPRESS, DEBUG_TIMING, DEBUG_MISC
        )

# DEBUG sets global debug message verbosity

# NOTE: wx.DC.GetAsBitmap() to grab a DC as a bitmap

DEBUG_FILE = sys.stdout
ICON_DIR = os.path.dirname(os.path.realpath(__file__))

if ICON_DIR.endswith("Cellcounter.app/Contents/Resources"):
    # if we're being executed from inside a Mac app, turn off DEBUG
    logfile = os.path.join(os.path.expanduser("~"),'cellcounter.log')
    out_fh = open(logfile, 'w')
    print("Hello.", file=out_fh)

    #DEBUG = 0
    DEBUG_FILE = out_fh


def debugmsg(debug_bit, *args, **kwargs):
    if DEBUG & debug_bit:
        print(*args, **kwargs, file=DEBUG_FILE)


# debug decorator that announces function call/entry and lists args
def debug_fxn(func):
    """Function decorator that (if enabled by DEBUG_FXN_ENTRY bit in DEBUG)
    prints the function name and the arguments used in the function call
    before executing the function
    """
    def func_wrapper(*args, **kwargs):
        if DEBUG & DEBUG_FXN_ENTRY:
            print("FXN:" + func.__qualname__ + "(", flush=True)
            for arg in args[1:]:
                print("    " + repr(arg) + ", ", flush=True)
            for key in kwargs:
                print("    " + key + "=" + repr(kwargs[key]) + ", ", flush=True)
            print("    )", flush=True)
        return func(*args, **kwargs)
    return func_wrapper


class EditHistory():
    """Keeps track of Edit History, undo, redo
    """
    def __init__(self):
        self.undo_menu_item = None
        self.redo_menu_item = None
        self.history = []
        self.history_ptr = -1
        self.update_menu_items()

    @debug_fxn
    def reset(self):
        self.history = []
        self.history_ptr = -1
        self.update_menu_items()

    @debug_fxn
    def new(self, item):
        # truncate list so current item is last item (makes empty list
        #   if self.history_ptr == -1)
        self.history = self.history[:self.history_ptr + 1]
        self.history.append(item)
        self.history_ptr = len(self.history) - 1
        self.update_menu_items()

    @debug_fxn
    def undo(self):
        if self.can_undo():
            undo_action = self.history[self.history_ptr]
            self.history_ptr -= 1
        else:
            undo_action = None

        self.update_menu_items()
        return undo_action

    @debug_fxn
    def redo(self):
        if self.can_redo():
            self.history_ptr += 1
            redo_action = self.history[self.history_ptr]
        else:
            redo_action = None

        self.update_menu_items()
        return redo_action
    
    @debug_fxn
    def can_undo(self):
        return (len(self.history) > 0) and (self.history_ptr >= 0)

    @debug_fxn
    def can_redo(self):
        return (len(self.history) > 0) and (self.history_ptr < len(self.history) - 1)

    @debug_fxn
    def update_menu_items(self):
        if self.undo_menu_item is not None:
            self.undo_menu_item.Enable(self.can_undo())
        if self.redo_menu_item is not None:
            self.redo_menu_item.Enable(self.can_redo())

    @debug_fxn
    def register_undo_menu_item(self, undo_menu_item):
        self.undo_menu_item = undo_menu_item
        self.update_menu_items()

    @debug_fxn
    def register_redo_menu_item(self, redo_menu_item):
        self.redo_menu_item = redo_menu_item
        self.update_menu_items()


class DropTarget(wx.FileDropTarget):
    """DropTarget Facilitating dragging file into window to open
    """
    def __init__(self, window_target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_target = window_target

    @debug_fxn
    def OnDropFiles(self, x, y, filenames):
        filename = filenames[0]
        debugmsg(DEBUG_MISC,
            "MSC:Drag and Drop filename:\n" + "    "+repr(filename)
            )
        self.window_target.init_image_from_file(filename)

        # TODO: which one of these??
        #return wx.DragCopy
        return True


class MainWindow(wx.Frame):
    def __init__(self, srcfiles, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # internal state
        self.app_history = EditHistory()
        self.content_saved = True
        self.save_filepath = None

        # GUI-related
        self.html = None
        self.mark_id = None
        self.toolbar = None

        self.init_ui()
        if srcfiles:
            # TODO: are we able to load more than one file?
            self.load_image_from_path(srcfiles[0])

    @debug_fxn
    def init_ui(self):
        # menu bar stuff
        menubar = wx.MenuBar()
        # File
        file_menu = wx.Menu()
        fitem = file_menu.Append(wx.ID_EXIT,
                'Quit', 'Quit application\tCtrl+Q')
        oitem = file_menu.Append(wx.ID_OPEN,
                'Open Image...\tCtrl+O', 'Open image file')
        citem = file_menu.Append(wx.ID_CLOSE,
                'Close\tCtrl+W', 'Close image')
        sitem = file_menu.Append(wx.ID_SAVE,
                'Save Image Data\tCtrl+S', 'Save image file and associated data')
        saitem = file_menu.Append(wx.ID_SAVEAS,
                'Save Image Data As...\tShift+Ctrl+S', 'Save image file and associated data')
        menubar.Append(file_menu, '&File')
        # Edit
        edit_menu = wx.Menu()
        undoitem = edit_menu.Append(wx.ID_UNDO,
                'Undo\tCtrl+Z', 'Undo last action')
        redoitem = edit_menu.Append(wx.ID_REDO,
                'Redo\tShift+Ctrl+Z', 'Redo last undone action')
        selallitem = edit_menu.Append(wx.ID_SELECTALL,
                'Select All\tCtrl+A', 'Select all marks')
        menubar.Append(edit_menu, '&Edit')
        # Tools
        tools_menu = wx.Menu()
        self.markmodeitem = tools_menu.Append(wx.ID_ANY, "&Enable Mark Mode\tCtrl+M")
        menubar.Append(tools_menu, "&Tools")
        # Help
        help_menu = wx.Menu()
        aboutitem = help_menu.Append(wx.ID_ABOUT, "&About Cellcounter")
        helpitem = help_menu.Append(wx.ID_HELP, "&Cellcounter Help")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        # register Undo, Redo menu items so EditHistory obj can 
        #   enable or disable them as needed
        self.app_history.register_undo_menu_item(undoitem)
        self.app_history.register_redo_menu_item(redoitem)

        # toolbar stuff
        self.toolbar = self.CreateToolBar()
        debugmsg(DEBUG_MISC, "MSC:ICON_DIR=%s"%(ICON_DIR))
        obmp = wx.Bitmap(os.path.join(ICON_DIR, 'topen32.png'))
        otool = self.toolbar.AddTool(wx.ID_OPEN, 'Open', obmp)
        markbmp = wx.Bitmap(os.path.join(ICON_DIR, 'marktool32.png'))
        marktool = self.toolbar.AddCheckTool(
                wx.ID_ANY,
                'Point/Mark',
                markbmp,
                )
        self.mark_id = marktool.GetId()
        self.toolbar.Realize()

        # status bar stuff
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText('Ready.')

        # Panel keeps things from spilling over the frame, statusbar, etc.
        #   also accepts key focus
        #   probably with more than one Panel we need to worry about which
        #       has keyboard focus

        # init marks_num_display before ImageScrolledCanvas so ISC can
        #   update number on its init
        # TODO: find width of "999" text to give to size
        self.marks_num_display = wx.StaticText(self, wx.ID_ANY, size=wx.Size(30,-1))

        # ImageScrolledCanvas is the cleanest, fastest implementation for
        #   what we need
        self.img_panel = ImageScrolledCanvas(
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

        # setup event handlers for toolbar
        self.Bind(wx.EVT_TOOL, self.on_open, otool)
        self.Bind(wx.EVT_TOOL, self.on_markmode_toggle, marktool)

        # setup event handlers for menus
        self.Bind(wx.EVT_MENU, self.on_quit, fitem)
        # File menu items
        self.Bind(wx.EVT_MENU, self.on_open, oitem)
        self.Bind(wx.EVT_MENU, self.on_close, citem)
        self.Bind(wx.EVT_MENU, self.on_save, sitem)
        self.Bind(wx.EVT_MENU, self.on_saveas, saitem)
        # Edit menu items
        self.Bind(wx.EVT_MENU, self.on_undo, undoitem)
        self.Bind(wx.EVT_MENU, self.on_redo, redoitem)
        self.Bind(wx.EVT_MENU, self.on_select_all, selallitem)
        # Tools menu items
        self.Bind(wx.EVT_MENU, self.on_markmode_toggle, self.markmodeitem)
        # Help menu items
        self.Bind(wx.EVT_MENU, self.on_about, aboutitem)
        self.Bind(wx.EVT_MENU, self.on_help, helpitem)

        # finally render app
        self.SetSize((800, 600))
        self.SetTitle('Cellcounter')
        self.Centre()

        #self.img_panel.subpanel.Centre()

        self.Show(True)

        debugmsg(DEBUG_MISC,
                "MSC:self.img_panel size: " + \
                repr(self.img_panel.GetClientSize())
                )

    @debug_fxn
    def marks_num_update(self, mark_total):
        self.marks_num_display.SetLabel("%d"%mark_total)

    @debug_fxn
    def on_quit(self, evt):
        is_closed = self.on_close(None)
        if is_closed:
            self.Close()

    @debug_fxn
    def on_key_down(self, evt):
        KeyCode = evt.GetKeyCode()
        debugmsg(DEBUG_KEYPRESS,
                "KEY:Key Down" + \
                "    KeyCode: %d"%KeyCode + \
                "    RawKeyCode: %d"%(evt.GetRawKeyCode()) + \
                "    Position: " + repr(evt.GetPosition())
                )

        if KeyCode == 91:
            # [ key
            #  KeyCode: 91
            #  RawKeyCode: 33
            zoom = self.img_panel.zoom_out(1)
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))
        if KeyCode == 93:
            # ] key
            #  KeyCode: 93
            #  RawKeyCode: 30
            zoom = self.img_panel.zoom_in(1)
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

        # keys usually scroll, so down arrow makes image go up, etc.
        # "arrow keys move virtual viewport over image"
        # NOTE: if we wanted to automatically implement panning, we could
        #   just evt.Skip in the following if statements
        if KeyCode == 314:
            # left key
            self.img_panel.pan_left(const.SCROLL_KEY_SPEED)
        if KeyCode == 315:
            # up key
            self.img_panel.pan_up(const.SCROLL_KEY_SPEED)
        if KeyCode == 316:
            # right key
            self.img_panel.pan_right(const.SCROLL_KEY_SPEED)
        if KeyCode == 317:
            # down key
            self.img_panel.pan_down(const.SCROLL_KEY_SPEED)

        if KeyCode == 127 or KeyCode == 8:
            # Delete (127) or Backspace (8)
            self.img_panel.delete_selected_marks()

        if KeyCode == 366:
            # PAGE UP
            # skip to process page up
            evt.Skip()
        if KeyCode == 367:
            # PAGE DOWN
            # skip to process page up
            evt.Skip()
        if KeyCode == 313:
            # HOME
            # skip to process HOME
            evt.Skip()
        if KeyCode == 312:
            # END
            # skip to process END
            evt.Skip()

        if KeyCode == 32:
            # Space Bar
            pass

    @debug_fxn
    def on_markmode_toggle(self, evt):
        # toggle state
        self.img_panel.mark_mode = not self.img_panel.mark_mode
        # update toolbartoolbase
        # update menu item
        if self.img_panel.mark_mode:
            self.markmodeitem.SetItemLabel("Disable &Mark Mode\tCtrl+M")
            # NOTE: must use this, can't talk to ToolbarBase item directly
            self.toolbar.ToggleTool(self.mark_id, True) # works!
            # exiting select mode so no marks can be selected
            self.img_panel.deselect_all_marks()
            self.img_panel.SetCursor(wx.Cursor(wx.CURSOR_CROSS))
        else:
            self.markmodeitem.SetItemLabel("Enable &Mark Mode\tCtrl+M")
            # NOTE: must use this, can't talk to ToolbarBase item directly
            self.toolbar.ToggleTool(self.mark_id, False) # works!
            self.img_panel.SetCursor(wx.Cursor(wx.CURSOR_NONE))

    @debug_fxn
    def on_open(self, evt):
        """Open Image... menu handler for Main Window
        """
        # first close current image (if it exists)
        is_closed = self.on_close(None)

        if not is_closed:
            return

        # create wildcard for Image files, and for *.1sc files (Bio-Rad)
        wildcard = wx.Image.GetImageExtWildcard()
        wildcard = "Image Files " + wildcard + "|Bio-Rad 1sc Files|*.1sc"
        open_file_dialog = wx.FileDialog(self,
                "Open image file",
                wildcard=wildcard,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_file_dialog.ShowModal() == wx.ID_CANCEL:
            # the user canceled
            return

        # get filepath and attempt to open image into bitmap
        img_path = open_file_dialog.GetPath()
        self.load_image_from_path(img_path)

    @debug_fxn
    def load_image_from_path(self, img_path):
        """Given full img_path, load image into app

        Separate from on_open so we can use this with argv_emulation
        """
        # check for 1sc files and get image data to send to Image
        (_, imgfile_ext) = os.path.splitext(img_path)
        if imgfile_ext == ".1sc":
            try:
                read1sc = biorad1sc_reader.Reader(img_path)
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
        else:
            img = wx.Image(img_path)

        # check if img loaded ok
        img_ok = img.IsOk()

        if img_ok:
            self.img_panel.init_image(img)
            self.statusbar.SetStatusText("Image " + img_path + " loaded OK.")
            # reset filepath for cco file to nothing if we load new image
            self.save_filepath = None
        else:
            self.statusbar.SetStatusText(
                    "Image " + img_path + " loading ERROR."
                    )

    @debug_fxn
    def on_close(self, evt):
        """Close Image menu handler for Main Window
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

        # else: proceed asking to the user the new file to open

        # reset edit history
        self.app_history.reset()
        # reset filepath for cco file to nothing on close
        self.save_filepath = None
        # reset content_saved in case user didn't save
        self.content_saved = True
        # make scrolled window show no image
        self.img_panel.set_no_image()

        return True

    @debug_fxn
    def on_save(self, evt):
        """Save menu handler for Main Window
        """
        if self.save_filepath == None:
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
        """
        (img_path_root, _) = os.path.splitext(
                os.path.basename(self.img_panel.img_path)
                )
        default_save_filename = img_path_root + ".cco"

        with wx.FileDialog(
                self,
                "Save CCO file", wildcard="CCO files (*.cco)|*.cco",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                defaultFile=default_save_filename,
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

    @debug_fxn
    def on_undo(self, evt):
        # TODO
        print("self.app_history.undo()")
        print(self.app_history.undo())

    @debug_fxn
    def on_redo(self, evt):
        # TODO
        print("self.app_history.redo()")
        print(self.app_history.redo())

    @debug_fxn
    def on_select_all(self, evt):
        # TODO
        print("Select ALL")

    @debug_fxn
    def save_notify(self):
        # tell self and children data was saved now
        self.content_saved = True
        self.img_panel.save_notify()

    @debug_fxn
    def needs_save(self):
        # poll self and children to determine if we need to save document
        return not self.content_saved or self.img_panel.needs_save()

    @debug_fxn
    def save_img_data(self, pathname):
        """Save image and mark locations to zipfile filename
        """
        try:
            with zipfile.ZipFile(pathname, 'w') as container_fh:
                img_filename = os.path.basename(self.img_panel.img_path)
                container_fh.write(self.img_panel.img_path, arcname=img_filename)
                container_fh.writestr(
                        "marks.txt",
                        json.dumps(self.img_panel.marks, separators=(',',':'))
                        )
        except IOError:
            # TODO: need real error dialog
            print("Cannot save current data in file '%s'." % pathname)



    @debug_fxn
    def on_about(self, evt):
        info = wx.adv.AboutDialogInfo()
        info.SetName("Cellcounter")
        info.SetVersion(const.VERSION_STR)
        info.SetDescription("Counting cells in biological images.")
        info.SetCopyright("(C) 2017 Matthew A. Clapp")

        print("iblik: Matthew A Clapp")

        wx.adv.AboutBox(info)

    @debug_fxn
    def on_help(self, evt):
        """Open a brief help window (html)
        """
        self.html = HelpFrame(self, id=wx.ID_ANY)
        self.html.Show(True)


class HelpFrame(wx.Frame):
    """
    """
    def __init__(self, *args, **kwargs):
        """Constructor"""
        super().__init__(*args, **kwargs)
        # TODO: consider using wx.html2.WebView if we want to make Help look
        #   nicer than crummy html4 (e.g. being able to use CSS)
        self.html = wx.html.HtmlWindow(self)
        self.html.SetRelatedFrame(self, "%s")
        self.html.LoadPage(os.path.join(ICON_DIR, 'cellcounter_help.html'))
        self.SetSize((400, 600))


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
    #parser.add_argument(
    #    '-d', '--debug', action='store_true',
    #    help='Enable debugging messages to console'
    #    )

    #(settings, args) = parser.parse_args(argv)
    args = parser.parse_args(argv)

    return args

def main(argv=None):
    # process command line if started from there
    # Also, py2app sends file(s) to open via argv if file is dragged on top
    #   of the application icon to start the icon
    args = process_command_line(argv)

    debugmsg(DEBUG_MISC, repr(argv))
    debugmsg(DEBUG_MISC, repr(args))
    # setup main wx event loop
    myapp = wx.App()
    main_win = MainWindow(args.srcfiles, None)
    # binding to App is surest way to catch keys accurately, not having
    #   to worry about focus
    # binding to a panel can end up it not having focus, just donk, donk, donk,
    #   bell sounds
    # The reason is because a Panel will not accept focus if it has a child
    #   window that can accept focus
    #   wx.Panel.SetFocus: "In practice, if you call this method and the
    #   control has at least one child window, the focus will be given to the
    #   child window."
    #   (see wx.Panel.AcceptsFocus, wx.Panel.SetFocus,
    #   wx.Panel.SetFocusIgnoringChildren)
    myapp.Bind(wx.EVT_KEY_DOWN, main_win.on_key_down)
    myapp.MainLoop()

    # TODO: meaningless
    return 0


if __name__ == "__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130

    sys.exit(status)
