#!/usr/bin/env python3
  
import wx

TBFLAGS = wx.TB_HORIZONTAL
#TBFLAGS = wx.TB_VERTICAL

class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.SetSize((800, 600))

        tb = self.CreateToolBar( TBFLAGS )
        tsize = (32,32)
        hd_bmp =  wx.ArtProvider.GetBitmap(wx.ART_HARDDISK, wx.ART_TOOLBAR, tsize)
        flop_bmp =  wx.ArtProvider.GetBitmap(wx.ART_FLOPPY, wx.ART_TOOLBAR, tsize)
        cd_bmp =  wx.ArtProvider.GetBitmap(wx.ART_CDROM, wx.ART_TOOLBAR, tsize)
        tb.SetToolBitmapSize(tsize)
        tool = tb.AddRadioTool( wx.ID_ANY, "Radio0", hd_bmp,
                shortHelp="Radio 0")
        tool = tb.AddRadioTool(wx.ID_ANY, "Radio1", flop_bmp,
                shortHelp="Radio 1")
        tool = tb.AddRadioTool(wx.ID_ANY, "Radio2", cd_bmp,
                shortHelp="Radio 2")
        tb.Realize()

        self.Show(True)

def main():
    my_app = wx.App()
    main_win = MainWindow(None)
    my_app.MainLoop()

if __name__ == '__main__':
    main()
