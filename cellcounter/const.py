#!/usr/bin/env python3

import wx 

print("Loading const.py")

# OR'able debug values
DEBUG_FXN_ENTRY = 1
DEBUG_KEYPRESS = 2
DEBUG_TIMING = 4
DEBUG_MISC = 1024

# global debug level
DEBUG = 0
DEBUG = DEBUG_FXN_ENTRY | DEBUG_TIMING | DEBUG_MISC
DEBUG = DEBUG_FXN_ENTRY | DEBUG_KEYPRESS | DEBUG_TIMING | DEBUG_MISC
DEBUG = DEBUG_KEYPRESS | DEBUG_TIMING | DEBUG_MISC


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
