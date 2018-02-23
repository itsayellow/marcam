import sys
import wx 
import appdirs

APP_NAME = 'Marcam'
VERSION_STR = "0.3.0"

# OS-dependent
USER_CONFIG_DIR = appdirs.user_config_dir(APP_NAME)
USER_LOG_DIR = appdirs.user_log_dir(APP_NAME)
if sys.platform == 'darwin':
    PLATFORM = 'mac'
elif sys.platform == 'win32':
    PLATFORM = 'win'
else:
    PLATFORM = 'unix'

# what is one step of zoom? (1.2 might be better)
MAG_STEP = 1.1
# how many zoom steps from minimum to maximum zoom, centered on zoom 100%
TOTAL_MAG_STEPS = 69

# how much to scroll for an EVT_SROLLWIN_* 
SCROLL_WHEEL_SPEED = 2
# how much to scroll for an keypress
SCROLL_KEY_SPEED = 20

# how close can click to a mark to say we clicked on it (win pixels)
PROXIMITY_PX = 6

# how long in ms is a frame during an animated pan (right-click)
#   smaller -> smoother animation (30 looks smooth)
#   larger -> doesn't break with slow computers
PANIMATE_STEP_MS = 30

# appropriate for 11px x 11px cross
CROSS_REFRESH_SQ_SIZE = 12

# how many zoom_idx to zoom in on press of Option key
TEMP_ZOOM = 10

# BITMAPS

# useful for bitmaps below
pix_clear = b'\x00\x00\x00\x00'
pix_red = b'\xff\x00\x00\xff'
pix_yellow = b'\xff\xff\x00\xff'

# red cross, 5px x 5px
centerline_5 = pix_clear*2 + pix_red + pix_clear*2
crossline_5 = pix_red*5
CROSS_5x5_RED_BMP = wx.Bitmap.FromBufferRGBA(
        5, 5,
        centerline_5*2 + crossline_5 + centerline_5*2
        )

# red cross, 7px x 7px
centerline_7 = pix_clear*3 + pix_red + pix_clear*3
crossline_7 = pix_red*7
CROSS_7x7_RED_BMP = wx.Bitmap.FromBufferRGBA(
        7, 7,
        centerline_7*3 + crossline_7 + centerline_7*3
        )

# red cross, 9px x 9px
centerline_9 = pix_clear*4 + pix_red + pix_clear*4
crossline_9 = pix_red*9
CROSS_9x9_RED_BMP = wx.Bitmap.FromBufferRGBA(
        9, 9,
        centerline_9*4 + crossline_9 + centerline_9*4
        )

# red cross, 11px x 11px
centerline_11 = pix_clear*5 + pix_red + pix_clear*5
crossline_11 = pix_red*11
CROSS_11x11_RED_BMP = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*5 + crossline_11 + centerline_11*5
        )

# yellow cross, 11px x 11px
centerline_11 = pix_clear*5 + pix_yellow + pix_clear*5
crossline_11 = pix_yellow*11
CROSS_11x11_YELLOW_BMP = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*5 + crossline_11 + centerline_11*5
        )


# TODO: attempts to make bg shadow or glow just end up making it look like
#       marks are blurry or odd.  unsuccessful
pix_transluc50_black = b'\x00\x00\x00\x80'
pix_transluc50_white = b'\xff\xff\xff\x80'
pix_transluc25_black = b'\x00\x00\x00\x40'
pix_transluc25_white = b'\xff\xff\xff\x40'
pix_transluc25_cyan = b'\x00\xff\xff\x40'

# red cross with background shadow, 11px x 11px
centerline_11 = pix_clear*5 + pix_red + pix_transluc25_black + pix_clear*4
crossline_11 = pix_red*11
crossline_below_11 = pix_transluc25_black*5 + pix_red + pix_transluc25_black*5
CROSS_11x11_RED_SHADOW_BMP = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*5 + crossline_11 + crossline_below_11 + centerline_11*4
        )

# red cross with background glow, 11px x 11px
centerline_11 = pix_clear*4 + pix_transluc25_cyan + pix_red + pix_transluc25_cyan + pix_clear*4
crossline_above_11 = pix_transluc25_cyan*5 + pix_red + pix_transluc25_cyan*5
crossline_11 = pix_red*11
crossline_below_11 = pix_transluc25_cyan*5 + pix_red + pix_transluc25_cyan*5
CROSS_11x11_RED_GLOW_BMP = wx.Bitmap.FromBufferRGBA(
        11, 11,
        centerline_11*4 + crossline_above_11 + crossline_11 + crossline_below_11 + centerline_11*4
        )
