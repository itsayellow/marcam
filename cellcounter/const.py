#!/usr/bin/env python3

import wx 

print("Loaded constants")

# red cross, 5px x 5px
CROSS_BMP = wx.Bitmap.FromBufferRGBA(
        5, 5,
        b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\xff' + \
                b'\xff\x00\x00\x00' + \
                b'\xff\x00\x00\x00'
        )
