#!/usr/bin/env python3

import wx
 
class MyForm(wx.Frame):
 
    def __init__(self):
        wx.Frame.__init__(self, None, wx.ID_ANY, "Focus Finder")
 
        # Add a panel so it looks the correct on all platforms
        panel = wx.Panel(self, wx.ID_ANY)
        panel.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        txt = wx.StaticText(panel, wx.ID_ANY, 
                   "This label cannot receive focus")
 
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer)
        self.timer.Start(1000)
 
    def onFocus(self, event):
        print("panel received focus!")
 
    def onTimer(self, evt):
        print('Focused window:', wx.Window.FindFocus())
 
# Run the program
if __name__ == "__main__":
    app = wx.PySimpleApp()
    frame = MyForm().Show()
    app.MainLoop()
