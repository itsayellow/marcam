#!/usr/bin/env python3

import sys
import argparse
import os.path
import wx


class MainWindow(wx.Frame):
    def __init__(self, srcfiles, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mark_mode = False
        self.marktool = None
        self.save_filepath = None
        # this can be set to false by child by change in state
        self.content_saved = True

        self.init_ui()
        if srcfiles:
            # TODO: are we able to load more than one file?
            self.load_image_from_path(srcfiles[0])

    def init_ui(self):
        # menu bar stuff
        menubar = wx.MenuBar()
        # File
        file_menu = wx.Menu()
        fitem = file_menu.Append(wx.ID_EXIT,
                'Quit', 'Quit application\tCtrl+Q')
        oitem = file_menu.Append(wx.ID_OPEN,
                'Open...\tCtrl+O', 'Open')
        citem = file_menu.Append(wx.ID_CLOSE,
                'Close\tCtrl+W', 'Close')
        sitem = file_menu.Append(wx.ID_SAVE,
                'Save\tCtrl+S', 'Save')
        saitem = file_menu.Append(wx.ID_SAVEAS,
                'Save As...\tShift+Ctrl+S', 'Save As')
        menubar.Append(file_menu, '&File')
        # Tools
        tools_menu = wx.Menu()
        self.markmodeitem = tools_menu.Append(wx.ID_ANY, "&Enable Mark Mode\tCtrl+M")
        menubar.Append(tools_menu, "&Tools")

        self.SetMenuBar(menubar)

        # toolbar stuff
        self.toolbar = self.CreateToolBar()
        obmp = os.path.join(".", 'topen32.png')
        otool = self.toolbar.AddTool(wx.ID_OPEN, 'Open', wx.Bitmap(obmp))
        markbmp = os.path.join(".", 'marktool32.png')
        self.marktool = self.toolbar.AddCheckTool(
                wx.ID_ANY,
                'Point/Mark',
                wx.Bitmap(markbmp),
                )
        self.mark_id = self.marktool.GetId()
        self.toolbar.Realize()

        # status bar stuff
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText('Ready.')

        # Panel keeps things from spilling over the frame, statusbar, etc.
        #   also accepts key focus
        #   probably with more than one Panel we need to worry about which
        #       has keyboard focus

        # expand img_panel to fill space
        mybox = wx.BoxSizer(wx.VERTICAL)

        # ImageScrolledCanvas is the cleanest, probably most portable
        #self.img_panel = ImageScrolledCanvas(self)

        #mybox.Add(self.img_panel, 1, wx.EXPAND)
        self.SetSizer(mybox)

        # setup event handlers for toolbar, menus
        self.Bind(wx.EVT_TOOL, self.on_open, otool)
        self.Bind(wx.EVT_TOOL, self.on_markmode_toggle, self.marktool)

        self.Bind(wx.EVT_MENU, self.on_quit, fitem)
        self.Bind(wx.EVT_MENU, self.on_open, oitem)
        self.Bind(wx.EVT_MENU, self.on_markmode_toggle, self.markmodeitem)

        # finally render app
        self.SetSize((800, 600))
        self.SetTitle('wx Test Window')
        self.Centre()

        self.Show(True)

    def on_open(self, evt):
        print("Open!!")

    def on_quit(self, evt):
        self.Close()

    def on_key_down(self, evt):
        KeyCode = evt.GetKeyCode()
        evt.Skip()

    def on_markmode_toggle(self, evt):
        # toggle state
        self.mark_mode = not self.mark_mode
        # update toolbartoolbase
        # update menu item
        if self.mark_mode:
            self.markmodeitem.SetItemLabel("Disable &Mark Mode\tCtrl+M")
            self.toolbar.ToggleTool(self.mark_id, True) # works!
            #self.marktool.Toggle(True) # toggles state but not bitmap!
        else:
            self.markmodeitem.SetItemLabel("Enable &Mark Mode\tCtrl+M")
            self.toolbar.ToggleTool(self.mark_id, False) # works!
            # self.marktool.Toggle(False) # toggles state but not bitmap!


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
            description="Simple test window for wx stuff.")

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
