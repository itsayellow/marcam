"""Constants that setup parameters and behavior of application
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

import sys
import wx
import appdirs
import pathlib

APP_NAME = 'Marcam'
VERSION_STR = "0.8.0"

# OS-dependent
# Use appauthor=False (only applicable to Windows) to indicate only one
#   dir level with name appname
USER_CONFIG_DIR = pathlib.Path(
        appdirs.user_config_dir(appname=APP_NAME, appauthor=False)
        )
USER_LOG_DIR = pathlib.Path(
        appdirs.user_log_dir(appname=APP_NAME, appauthor=False)
        )
USER_CACHE_DIR = pathlib.Path(
        appdirs.user_cache_dir(appname=APP_NAME, appauthor=False)
        )
if sys.platform == 'darwin':
    PLATFORM = 'mac'
elif sys.platform == 'win32':
    PLATFORM = 'win'
else:
    PLATFORM = 'unix'

# Determine exe and icon dir, for frozen/nonfrozen
#   EXE_DIR is the same dir where the executable lives
if getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', False):
    EXE_DIR = pathlib.Path(sys._MEIPASS)
    #   on mac: "Marcam.app/Contents/MacOS/"
    #   on win: "Marcam/"
    # mac has symlink in EXE_DIR to media in "Marcam.app/Contents/Resources"
else:
    EXE_DIR = pathlib.Path(__file__).resolve().parent
    # for now the paths are the same

ICON_DIR = EXE_DIR / 'media'

if PLATFORM == 'mac':
    SELECTBMP_FNAME = ICON_DIR / 'selectmode24_mac.png'
    MARKBMP_FNAME = ICON_DIR / 'markmode24_mac.png'
    TOCLIPBMP_FNAME = ICON_DIR / 'toclip24_mac.png'
    ZOOMOUTBMP_FNAME = ICON_DIR / 'zoomout24_mac.png'
    ZOOMINBMP_FNAME = ICON_DIR / 'zoomin24_mac.png'
    ZOOMFITBMP_FNAME = ICON_DIR / 'zoomfit24_mac.png'
else:
    SELECTBMP_FNAME = ICON_DIR / 'selectmode32.png'
    MARKBMP_FNAME = ICON_DIR / 'marktool32.png'
    TOCLIPBMP_FNAME = ICON_DIR / 'toclip32.png'
    ZOOMOUTBMP_FNAME = ICON_DIR / 'zoomout32.png'
    ZOOMINBMP_FNAME = ICON_DIR / 'zoomin32.png'
    ZOOMFITBMP_FNAME = ICON_DIR / 'zoomfit32.png'

# for mag_step=1.1, total_mag_steps=69:
#   error_tol      max numerator
#   ----------------------------
#   0.001          209
#   0.002          148
#   0.003--0.004   127
#   0.005          107
#   0.006           83
#   0.007           79
#   0.008--0.009    70
#   0.010           58
#   0.011--0.017    51
#   0.018--0.025    35
#   0.026--0.029    29
#   0.030--inf      25
# what is one step of zoom? (1.05 too slow, 1.1 looks smooth, 1.15 a little jerky, 1.2 may
#   be too much?)
MAG_STEP = 1.1
# how many zoom steps from minimum to maximum zoom, centered on zoom 100%
TOTAL_MAG_STEPS = 69
# The multiplicative error tolerance, when constructing a zoom from a rational
#   number compared to the "ideal" zoom from magstep
# Hard upper limit: 0.1 for mag_step=1.1, so that zoom stays monotonic!
# Soft upper limit: 0.03 for mag_step=1.1, zoom is just barely jerky
# 0.05 yields jerky zoom
# Lower value: closer to "ideal" zoom ratios, bigger on_paint patch size
# Higher value: smaller on_paint patch size, farther from "ideal" zoom
ZOOM_MAX_ERROR_TOL = 0.011

# how much to scroll for an EVT_SROLLWIN_*
SCROLL_WHEEL_SPEED = 2
# how much to scroll for an keypress
SCROLL_KEY_SPEED = 20

# how many pixels to offset a new window position from last window opened
NEW_FRAME_OFFSET = 20

# how close can click to a mark to say we clicked on it (win pixels)
PROXIMITY_PX = 6

# how long in ms is a frame during an animated pan (right-click)
#   smaller -> smoother animation (30 looks smooth)
#   larger -> doesn't break with slow computers
PANIMATE_STEP_MS = 30

# how many zoom_idx to zoom in on press of Option key
TEMP_ZOOM = 10

# BITMAPS
# Luminance (after undoing gamma):
#   Y = 0.2126 R + 0.7152 G + 0.0722 B

# Red has more contrast on white background than black background
# Red could also be on cyan background

# useful for bitmaps below
pix_clr = b'\x00\x00\x00\x00'
pix_red = b'\xff\x00\x00\xff'
pix_ylw = b'\xff\xff\x00\xff'
pix_grn = b'\x00\xff\x00\xff'
pix_blu = b'\x00\x00\xff\xff'
pix_wht = b'\xff\xff\xff\xff'

# red cross, 11px x 11px
centerline_11 = pix_clr*5 + pix_red + pix_clr*5
crossline_11 = pix_red*11
CROSS_11x11_RED_BMP = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*5 + crossline_11 + centerline_11*5
        )

# yellow cross, 11px x 11px
centerline_11 = pix_clr*5 + pix_ylw + pix_clr*5
crossline_11 = pix_ylw*11
CROSS_11x11_YELLOW_BMP = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*5 + crossline_11 + centerline_11*5
        )

# appropriate for 11px x 11px cross
CROSS_REFRESH_SQ_SIZE = 12
CROSS_UNSEL_BMP = CROSS_11x11_RED_BMP
CROSS_SEL_BMP = CROSS_11x11_YELLOW_BMP
CROSS_CENTER_COORDS = (6, 6)

# UNUSED (ARCHIVE) BELOW ------------------------------------------------------

## blue cross white bg, 11px x 11px - a good cross
#centerline_11 = pix_clr*4 + pix_wht + pix_blu + pix_wht + pix_clr*4
#off_crossline_11 = pix_wht*5 + pix_blu + pix_wht*5
#crossline_11 = pix_blu*11
#CROSS_11x11_BLUE_WHT_BMP = wx.Bitmap.FromBufferRGBA(
#        11, 11,
#        centerline_11*4 + off_crossline_11 + crossline_11 + off_crossline_11 + centerline_11*4
#        )
#
## NOTE: attempts to make bg shadow or glow just end up making it look like
##       marks are blurry or odd.  unsuccessful
#pix_transluc50_black = b'\x00\x00\x00\x80'
#pix_transluc50_white = b'\xff\xff\xff\x80'
#pix_transluc25_black = b'\x00\x00\x00\x40'
#pix_transluc25_white = b'\xff\xff\xff\x40'
#pix_transluc25_cyan = b'\x00\xff\xff\x40'
#
## red cross with background shadow, 11px x 11px
#centerline_11 = pix_clr*5 + pix_red + pix_transluc25_black + pix_clr*4
#crossline_11 = pix_red*11
#crossline_below_11 = pix_transluc25_black*5 + pix_red + pix_transluc25_black*5
#CROSS_11x11_RED_SHADOW_BMP = wx.Bitmap.FromBufferRGBA(
#        11, 11,
#        centerline_11*5 + crossline_11 + crossline_below_11 + centerline_11*4
#        )
#
## red cross with background glow, 11px x 11px
#centerline_11 = pix_clr*4 + pix_transluc25_cyan + pix_red + pix_transluc25_cyan + pix_clr*4
#crossline_above_11 = pix_transluc25_cyan*5 + pix_red + pix_transluc25_cyan*5
#crossline_11 = pix_red*11
#crossline_below_11 = pix_transluc25_cyan*5 + pix_red + pix_transluc25_cyan*5
#CROSS_11x11_RED_GLOW_BMP = wx.Bitmap.FromBufferRGBA(
#        11, 11,
#        centerline_11*4 + crossline_above_11 + crossline_11 + crossline_below_11 + centerline_11*4
#        )
