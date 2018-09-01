#!/usr/bin/env python3
  
import wx

class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # FileHistory
        self.file_history = wx.FileHistory()

        # menu bar stuff
        menubar = wx.MenuBar()
        
        # File
        open_recent_menu = wx.Menu()
        file_menu = wx.Menu()
        file_open_item = file_menu.Append(wx.ID_OPEN,
                'Open File...\tCtrl+O',
                'Open file'
                )
        file_menu.AppendSubMenu(open_recent_menu,
                'Open Recent',
                'Open recent files'
                )

        menubar.Append(file_menu, '&File')

        # register Open Recent menu, put under control of FileHistory obj
        self.file_history.UseMenu(open_recent_menu)
        self.file_history.AddFilesToMenu(open_recent_menu)

        self.SetMenuBar(menubar)

        # setup event handlers for menus
        # File menu items
        self.Bind(wx.EVT_MENU, self.on_open, file_open_item)

        self.Show(True)

    def on_open(self, evt):
        open_file_dialog = wx.FileDialog(self,
                "Open File",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_file_dialog.ShowModal() == wx.ID_CANCEL:
            # the user canceled
            return

        file_path = open_file_dialog.GetPath()
        self.file_history.AddFileToHistory(file_path)

def main():
    my_app = wx.App()
    main_win = MainWindow(None)
    my_app.MainLoop()

if __name__ == '__main__':
    main()
