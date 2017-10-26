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


# useful for bitmaps below
pix_clear = b'\x00\x00\x00\x00'
pix_red = b'\xff\x00\x00\xff'

# red cross, 5px x 5px
centerline_5 = pix_clear*2 + pix_red + pix_clear*2
crossline_5 = pix_red*5
CROSS_BMP_5x5 = wx.Bitmap.FromBufferRGBA(
        5, 5,
        centerline_5*2 + crossline_5 + centerline_5*2
        )

# red cross, 7px x 7px
centerline_7 = pix_clear*3 + pix_red + pix_clear*3
crossline_7 = pix_red*7
CROSS_BMP_7x7 = wx.Bitmap.FromBufferRGBA(
        7, 7,
        centerline_7*3 + crossline_7 + centerline_7*3
        )

# red cross, 9px x 9px
centerline_9 = pix_clear*4 + pix_red + pix_clear*4
crossline_9 = pix_red*9
CROSS_BMP_9x9 = wx.Bitmap.FromBufferRGBA(
        9, 9,
        centerline_9*4 + crossline_9 + centerline_9*4
        )

# red cross, 11px x 11px
centerline_11 = pix_clear*5 + pix_red + pix_clear*5
crossline_11 = pix_red*11
CROSS_BMP_11x11 = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*5 + crossline_11 + centerline_11*5
        )
