#!/usr/bin/env python3
  
import time
import wx

TBFLAGS = wx.TB_HORIZONTAL
#TBFLAGS = wx.TB_VERTICAL

#my_bitmap = 'diagonal_128_128.png'
#my_bitmap = 'diagonal_100_100.png'
#my_bitmap = 'diagonal_84_84.png'
#my_bitmap = 'diagonal_64_64.png'
#my_bitmap = 'diagonal_48_48.png'
#my_bitmap = 'diagonal_36_36.png'
my_bitmap = 'diagonal_32_32.png'
#my_bitmap = 'diagonal_28_28.png'
#my_bitmap = 'diagonal_24_24.png'
#my_bitmap = 'diagonal_20_20.png'
#my_bitmap = 'diagonal_16_16.png'

class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.SetSize((800, 600))

        #tb = self.CreateToolBar( TBFLAGS )
        #tsize = wx.Size(16,16)
        #hd_bmp =  wx.ArtProvider.GetBitmap(wx.ART_HARDDISK, wx.ART_TOOLBAR, tsize)
        #flop_bmp =  wx.ArtProvider.GetBitmap(wx.ART_FLOPPY, wx.ART_TOOLBAR, tsize)
        #flop_bmp = wx.Bitmap('pencil6c_mac_24.png')
        #cd_bmp =  wx.ArtProvider.GetBitmap(wx.ART_CDROM, wx.ART_TOOLBAR, tsize)
        #test_bmp = wx.Bitmap(my_bitmap)
        #tb.SetToolBitmapSize(tsize)
        #tool = tb.AddRadioTool( wx.ID_ANY, "Radio0", hd_bmp,
        #        shortHelp="Radio 0")
        #tool = tb.AddRadioTool(wx.ID_ANY, "Radio1", flop_bmp,
        #        shortHelp="Radio 1")
        #tool = tb.AddRadioTool(wx.ID_ANY, "Radio2", test_bmp,
        #        shortHelp="Radio 2")
        #tb.Realize()

        self.mybutton = wx.Button(
                self,
                label="press me"
                )
        self.Show(True)

        #dialog = wx.MessageDialog(
        #        self,
        #        message="hello",
        #        caption="ho ho!",
        #        style=wx.OK
        #        )

        #dialog.Hide()
        #dialog.ShowModal()

        wx.CallLater(1000, print, "Disable")
        wx.CallLater(1000, self.Enable, False)
        wx.CallLater(3000, print, "Enable")
        wx.CallLater(3000, self.Enable, True)

def main():
    my_app = wx.App()
    main_win = MainWindow(None)
    my_app.MainLoop()

if __name__ == '__main__':
    main()
