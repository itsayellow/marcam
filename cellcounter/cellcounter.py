#!/usr/bin/env python3
#
# GUI for displaying an image and counting cells

import sys
import time
import argparse
import os.path
import numpy as np
import biorad1sc_reader
import wx
import wx.adv
import wx.lib.statbmp
import wx.lib.scrolledpanel

import const
from const import (
        DEBUG, DEBUG_FXN_ENTRY, DEBUG_KEYPRESS, DEBUG_TIMING, DEBUG_MISC
        )

# DEBUG sets global debug message verbosity

# NOTE: wx.DC.GetAsBitmap() to grab a DC as a bitmap

ICON_DIR = os.path.dirname(os.path.realpath(__file__))

if ICON_DIR.endswith("Cellcounter.app/Contents/Resources"):
    # if we're being executed from inside a Mac app, turn off DEBUG
    DEBUG = 0
    #DEBUG_FILE = os.path.join(os.path.expanduser("~"),'cellcounter.log')
    #with open(DEBUG_FILE, 'w') as out_fh:
    #    print("Turning off debug.", file=out_fh)


# debug decorator that announces function call/entry and lists args
def debug_fxn(func):
    """Function decorator that (if enabled by DEBUG_FXN_ENTRY bit in DEBUG)
    prints the function name and the arguments used in the function call
    before executing the function
    """
    def func_wrapper(*args, **kwargs):
        if DEBUG & DEBUG_FXN_ENTRY:
            print("FXN:" + func.__qualname__ + "(", flush=True)
            for arg in args[1:]:
                print("    " + repr(arg) + ", ", flush=True)
            for key in kwargs:
                print("    " + key + "=" + repr(kwargs[key]) + ", ", flush=True)
            print("    )", flush=True)
        return func(*args, **kwargs)
    return func_wrapper


# really a Scrolled Window
class ImageScrolledCanvas(wx.ScrolledCanvas):
    """Window (in the wx sense) widget that displays an image, zooms in and
    out, and allows scrolling/panning in up/down and side/side if image is
    big enough.  If image is smaller than window it is auto-centered
    """
    @debug_fxn
    def __init__(self, parent, id_=wx.ID_ANY, *args, **kwargs):
        super().__init__(parent, id_, *args, **kwargs)

        # init all properties to None (cause error if accessed before
        #   proper init)
        self.img = None
        self.img_at_wincenter_x = None
        self.img_at_wincenter_y = None
        self.img_coord_xlation_x = None
        self.img_coord_xlation_y = None
        self.img_dc = None
        self.img_dc_div2 = None
        self.img_dc_div4 = None
        self.img_path = None
        self.img_size_x = None
        self.img_size_y = None
        self.parent = None
        self.points_record = []
        self.zoom = None
        self.zoom_idx = None
        self.zoom_list = None

        # ScrollRate of (10,10) is default
        # we set this to be as small as possible (1,1) so that positioning
        #   the scroll position during zoom can be as fine as possible.
        #   This avoids the image appearing to "jump around" during zoom in
        #   and zoom out due to subsampling the position.
        # This affects magnitude of panning and scrolling, so we multiply
        #   panning and scrolling manually in those event handlers
        # By default, pixels per unit scroll is (1,1)
        self.SetScrollRate(1, 1)

        # init parent pointer
        self.parent = parent

        # setup possible magnification list
        mag_frac = 0.1
        mag_len = 69
        lomags = [(1.0 - mag_frac)**x for x in range(1, (mag_len+1)//2)]
        lomags.reverse()
        himags = [(1.0 + mag_frac)**x for x in range(1, (mag_len+1)//2)]
        # possible mag list
        self.zoom_list = lomags + [1.0,] + himags
        # set zoom_idx to 1.00 scaling
        self.zoom_idx = self.zoom_list.index(1.0)
        self.zoom = self.zoom_list[self.zoom_idx]

        # setup blank image area
        self.blank_img()

        # setup handlers
        self.Bind(wx.EVT_PAINT, self.OnPaintRegion)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_SCROLLWIN, self.on_scroll)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right_down)

        # force a paint event with Refresh and Update
        # Refresh Invalidates the window
        self.Refresh()
        # Update immediately repaints invalidated areas
        #   without this, repainting will happen next iteration of event loop
        self.Update()

    @debug_fxn
    def get_img_wincenter(self):
        # find client size (visible image)
        (win_size_x, win_size_y) = self.GetClientSize()

        # translate client center to zoomed image center coords
        (self.img_at_wincenter_x, self.img_at_wincenter_y
                ) = self.img_coord_from_win_coord(win_size_x/2, win_size_y/2)

        if DEBUG & DEBUG_MISC:
            print(
                    "MSC:self.img_at_wincenter=(%.3f,%.3f)"%(
                        self.img_at_wincenter_x,
                        self.img_at_wincenter_y
                        )
                    )

    @debug_fxn
    def scroll_to_img_at_wincenter(self):
        (win_size_x, win_size_y) = self.GetClientSize()
        (scroll_ppu_x, scroll_ppu_y) = self.GetScrollPixelsPerUnit()

        img_zoom_wincenter_x = self.img_at_wincenter_x * self.zoom
        img_zoom_wincenter_y = self.img_at_wincenter_y * self.zoom

        origin_x = img_zoom_wincenter_x - win_size_x/2
        origin_y = img_zoom_wincenter_y - win_size_y/2

        scroll_x = round(origin_x/scroll_ppu_x)
        scroll_y = round(origin_y/scroll_ppu_y)
        self.Scroll(scroll_x, scroll_y)
        if DEBUG & DEBUG_MISC:
            print("MSC:img_zoom_wincenter = " \
                    "(%.3f,%.3f)"%(img_zoom_wincenter_x, img_zoom_wincenter_y))
            print("MSC:origin = (%.3f,%.3f)"%(origin_x, origin_y))
            print("MSC:Scroll to (%d,%d)"%(scroll_x, scroll_y))

    @debug_fxn
    def on_left_down(self, evt):
        """Mark image where user left-clicks

        Args:
            evt (wx.MouseEvent): todo.
        """
        # point coordinate returned seems:
        #   * be only absolute coordinates of where in window was clicked
        #   * not to depend on which img_dc we supply
        #   * not to depend on zoom or pan
        point = evt.GetLogicalPosition(self.img_dc)
        (img_x, img_y) = self.img_coord_from_win_coord(point.x, point.y)

        if DEBUG & DEBUG_MISC:
            print("MSC:left click at img", end="")
            print("(%.2f, %.2f)"%(img_x, img_y))

        self.draw_at_point(img_x, img_y)

        # continue processing click, for example shifting focus to app
        evt.Skip()

    @debug_fxn
    def on_right_down(self, evt):
        """Set image center where user right-clicks

        Args:
            evt (wx.MouseEvent): todo.
        """
        # point coordinate returned seems:
        #   * be only absolute coordinates of where in window was clicked
        #   * not to depend on which img_dc we supply
        #   * not to depend on zoom or pan
        point = evt.GetLogicalPosition(self.img_dc)
        (img_x, img_y) = self.img_coord_from_win_coord(point.x, point.y)

        if DEBUG & DEBUG_MISC:
            print("MSC:left click at img", end="")
            print("(%.2f, %.2f)"%(img_x, img_y))

        self.img_at_wincenter_x = img_x
        self.img_at_wincenter_y = img_y
        self.scroll_to_img_at_wincenter()

        # continue processing click, for example shifting focus to app
        evt.Skip()

    @debug_fxn
    def panimate(self, dest_x, dest_y, accel, max_speed):
        """Animate a pan from current scroll position to destination position

        Args:
            dest_x (int): destination x pan location in image coordinates
            dest_y (int): destination y pan location in image coordinates
            accel (float): how fast to accelerate at start and decelerate
                at end
            max_speed (float): maximum speed of pan
        """
            

    @debug_fxn
    def draw_at_point(self, pt_x, pt_y):
        # assumes img_dc_div2 not None implies no loaded file
        if self.img_dc_div2 is not None:
            point_x = int(pt_x)
            point_y = int(pt_y)

            if DEBUG & DEBUG_MISC:
                print("MSC: point", end="")
                print("(%d, %d)"%(point_x, point_y))

            self.points_record.append((point_x,point_y))

            # TEST: DELETEME: draw yellow pixel here just for sanity check,
            #   really draw crosses after the fact in PaintRect
            self.img_dc.DrawBitmap(
                    const.YELLOW_PIX_BMP,
                    point_x, point_y
                    )
            self.img_dc_div2.DrawBitmap(
                    const.YELLOW_PIX_BMP,
                    point_x/2, point_y/2
                    )
            self.img_dc_div4.DrawBitmap(
                    const.YELLOW_PIX_BMP,
                    point_x/4, point_y/4
                    )

            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

    @debug_fxn
    def on_scroll(self, evt):
        EventType = evt.GetEventType()
        Orientation = evt.GetOrientation()
        if DEBUG & DEBUG_MISC:
            print("MSC:")
            if Orientation == wx.HORIZONTAL:
                print("    wx.HORIZONTAL")
            elif Orientation == wx.VERTICAL:
                print("    wx.VERTICAL")
            else:
                print("    Orientation="+repr(Orientation))

            if EventType == wx.wxEVT_SCROLLWIN_TOP:
                print("    wx.wxEVT_SCROLLWIN_TOP")
            elif EventType == wx.wxEVT_SCROLLWIN_BOTTOM:
                print("    wx.wxEVT_SCROLLWIN_BOTTOM")
            elif EventType == wx.wxEVT_SCROLLWIN_LINEUP:
                print("    wx.wxEVT_SCROLLWIN_LINEUP")
            elif EventType == wx.wxEVT_SCROLLWIN_LINEDOWN:
                print("    wx.wxEVT_SCROLLWIN_LINEDOWN")
            elif EventType == wx.wxEVT_SCROLLWIN_PAGEUP:
                print("    wx.wxEVT_SCROLLWIN_PAGEUP")
            elif EventType == wx.wxEVT_SCROLLWIN_PAGEDOWN:
                print("    wx.wxEVT_SCROLLWIN_PAGEDOWN")
            elif EventType == wx.wxEVT_SCROLLWIN_THUMBTRACK:
                print("    wx.wxEVT_SCROLLWIN_THUMBTRACK")
            elif EventType == wx.wxEVT_SCROLLWIN_THUMBRELEASE:
                print("    wx.wxEVT_SCROLLWIN_THUMBRELEASE")
            else:
                print("    EventType="+repr(EventType))

        # NOTE: by setting position only on scroll (and not on zoom) we
        #   preserve position on zoom out/zoom back in even if the image gets
        #   temporarily centered during zoom out.  That way when we zoom back
        #   in, we will find the same position again unless we scroll.

        # set a position check for after this event is processed (after moved)
        #   useful in case event handled by default handler with evt.Skip()
        wx.CallAfter(self.get_img_wincenter)

        if Orientation == wx.HORIZONTAL and EventType == wx.wxEVT_SCROLLWIN_LINEUP:
            self.pan_left(2)
        elif Orientation == wx.HORIZONTAL and EventType == wx.wxEVT_SCROLLWIN_LINEDOWN:
            self.pan_right(2)
        elif Orientation == wx.VERTICAL and EventType == wx.wxEVT_SCROLLWIN_LINEUP:
            self.pan_up(2)
        elif Orientation == wx.VERTICAL and EventType == wx.wxEVT_SCROLLWIN_LINEDOWN:
            self.pan_down(2)
        else:
            # process with default handler(s)
            evt.Skip()

    @debug_fxn
    def blank_img(self):
        # Image object currently loaded
        #   None signals to methods not to pan, zoom, etc
        self.img = None
        # image path for current Image
        self.img_path = None
        # transparent placeholder img (2px x 2px of tranparent black)
        # will be bitmap corresponding to image
        img_bmp = wx.Bitmap.FromRGBA(2, 2, 0, 0, 0, 0)
        # store image data into a static DC
        self.img_dc = wx.MemoryDC()
        self.img_dc.SelectObject(img_bmp)
        # current position of image center
        #   start w/ 2px x 2px anchored with 1,1 at wincenter
        self.img_at_wincenter_x = 1
        self.img_at_wincenter_y = 1
        # size of image
        self.img_size_y = 2
        self.img_size_x = 2
        self.zoom = 1.0

        self.SetVirtualSize(2, 2)
        self.set_virt_size_with_min()

    @debug_fxn
    def set_virt_size_with_min(self):
        """Set size of unscrolled canvas for image_size, making virtual size
        same as image if image is zoomed larger than window, or as large as
        window if image is smaller than window in order to be able to center
        image in window.
        """
        # TODO: we can SetVirtualSize as a multiple of image in order to
        #   increase scrolling accuracy to sub-image-pixel resolution
        #   In that case we also need to scale image using scale_dc in 
        #   PaintRect
        #   Also need to adjust zoom settings
        (win_size_x, win_size_y) = self.GetClientSize()
        virt_size_x = max([self.img_size_x * self.zoom, win_size_x])
        virt_size_y = max([self.img_size_y * self.zoom, win_size_y])
        self.SetVirtualSize(virt_size_x, virt_size_y)

        # check and see if Client Size changed after setting VirtualSize
        #   e.g. for loss or addition of a Scrollbar
        (win_size_new_x, win_size_new_y) = self.GetClientSize()
        if (win_size_new_x != win_size_x) or (win_size_new_y != win_size_y):
            win_size_x = win_size_new_x
            win_size_y = win_size_new_y
            virt_size_x = max([self.img_size_x * self.zoom, win_size_x])
            virt_size_y = max([self.img_size_y * self.zoom, win_size_y])
            self.SetVirtualSize(virt_size_x, virt_size_y)

        # center image if Virtual Size is larger than image
        if win_size_x > self.img_size_x * self.zoom:
            self.img_coord_xlation_x = int(
                    (win_size_x - self.img_size_x * self.zoom) / 2
                    )
        else:
            self.img_coord_xlation_x = 0

        if win_size_y > self.img_size_y * self.zoom:
            self.img_coord_xlation_y = int(
                    (win_size_y - self.img_size_y * self.zoom) / 2
                    )
        else:
            self.img_coord_xlation_y = 0

        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom, divide by div_scale to get to img coordinates

    def on_size(self, evt):
        self.set_virt_size_with_min()

        # scroll so center of image at same point it used to be
        self.scroll_to_img_at_wincenter()

    # GetClientSize is size of window graphics not including scrollbars
    # GetSize is size of window including scrollbars
    @debug_fxn
    def OnPaintRegion(self, evt):
        """
        TODO:
            use BufferedPaintDC instead of PaintDC if flicker is a problem

        """
        if DEBUG & DEBUG_TIMING:
            start_onpaint = time.time()

        dc = wx.PaintDC(self)
        # for scrolled window
        self.DoPrepareDC(dc)

        # get the update rect list
        upd = wx.RegionIterator(self.GetUpdateRegion())

        while upd.HaveRects():
            rect = upd.GetRect()
            # Repaint this rectangle
            self.PaintRect(dc, rect)
            upd.Next()

        if DEBUG & DEBUG_TIMING:
            onpaint_eltime = time.time() - start_onpaint
            panel_size = self.GetSize()
            print(
                    "TIM:OnPaintRegion: %.3fs, zoom = %.3f, panel_size=(%d,%d)"%(
                        onpaint_eltime,
                        self.zoom,
                        panel_size.x, panel_size.y,
                        )
                    )

    @debug_fxn
    def PaintRect(self, dc, rect):
        """Given a rect needing a refresh in window PaintDC, Blit the image
        to fill that rect.

        Args:
            dc (wx.PaintDC): Device Context to Blit into
            rect (tuple): coordinates to refresh (window coordinates)
        """
        # break out rect details into variables
        (rect_pos_x, rect_pos_y, rect_size_x, rect_size_y) = rect.Get()

        # get rect coord origin translation based on scroll position
        (unscroll_pos_x, unscroll_pos_y) = self.CalcUnscrolledPosition(
                rect_pos_x, rect_pos_y
                )

        # see if we need to use a downscaled version of memdc
        if self.zoom > 0.5:
            img_dc_src = self.img_dc
            scale_dc = 1
        elif self.zoom > 0.25:
            img_dc_src = self.img_dc_div2
            scale_dc = 2
        else:
            img_dc_src = self.img_dc_div4
            scale_dc = 4

        # TODO: need exact slop factor verified
        #src_size_x = int(rect_size_x / scale_dc / self.zoom) + 2*int(1/self.zoom + 0.5)
        #src_size_y = int(rect_size_y / scale_dc / self.zoom) + 2*int(1/self.zoom + 0.5)
        src_size_x = int(rect_size_x / scale_dc / self.zoom) + 3
        src_size_y = int(rect_size_y / scale_dc / self.zoom) + 3
        # multiply back out to get slightly off-window but
        #   on src-pixel-boundary coords for dest
        # TODO: only do this for self.zoom > 1 ?
        dest_size_x = src_size_x * scale_dc * self.zoom
        dest_size_y = src_size_y * scale_dc * self.zoom

        # adjust image pos if smaller than window (center in window)
        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom, divide by div_scale to get to img coordinates
        src_pos_x = int(
                (unscroll_pos_x - self.img_coord_xlation_x) / self.zoom / scale_dc
                )
        src_pos_y = int(
                (unscroll_pos_y - self.img_coord_xlation_y) / self.zoom / scale_dc
                )
        # multiply back out to get slightly off-window but
        #   on src-pixel-boundary coords for dest
        # TODO: only do this for self.zoom > 1 ?
        dest_pos_x = src_pos_x * self.zoom * scale_dc + self.img_coord_xlation_x
        dest_pos_y = src_pos_y * self.zoom * scale_dc + self.img_coord_xlation_y

        # NOTE: Blit shows no performance advantage over StretchBlit
        # NOTE: StretchBlit uses ints for both src and dest pixel dimensions.
        #   This means to center and zoom accurately (sub-src-pixel) we need to
        #   refresh an area that INCLUDES the region needed, NOT ONLY that
        #   dest region.  This way we can zoom and position accurately, while
        #   employing the clipping mask behavior of PaintDC to make sure we
        #   only display in the area of the window

        # copy region from self.img_dc into dc with possible stretching
        dc.StretchBlit(
                dest_pos_x, dest_pos_y,
                dest_size_x, dest_size_y,
                img_dc_src,
                src_pos_x, src_pos_y,
                src_size_x, src_size_y,
                )

        self.draw_crosses(dc, src_pos_x, src_pos_y, src_size_x, src_size_y)

    @debug_fxn
    def draw_crosses(self, dc, src_pos_x, src_pos_y, src_size_x, src_size_y):
        pts_in_box = []
        for (x,y) in self.points_record:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pixel when zoomed
                # TODO: some sort of quantization error in zoom affects
                #   placement at different zoom values??
                x_win = (x + 0.5) * self.zoom + self.img_coord_xlation_x
                y_win = (y + 0.5) * self.zoom + self.img_coord_xlation_y
                if (x_win,y_win) not in pts_in_box:
                    pts_in_box.append((x_win, y_win))
                    dc.DrawBitmap(const.CROSS_11x11_BMP, x_win - 5 , y_win - 5)
        print(pts_in_box)

    @debug_fxn
    def img_coord_from_win_coord(self, win_x, win_y):
        # img_coord_xlation_{x,y} = 0 unless window is bigger than image
        #   in which case this is non-zero translation of left,top padding
        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom to get to img coordinates

        (img_unscroll_x, img_unscroll_y) = self.CalcUnscrolledPosition(win_x, win_y)

        img_x = (img_unscroll_x - self.img_coord_xlation_x) / self.zoom
        img_y = (img_unscroll_y - self.img_coord_xlation_y) / self.zoom

        # DEBUG DELETEME
        print("win: (%.2f,%.2f)"%(win_x,win_y))
        print("unscrolled: (%.2f,%.2f)"%(img_unscroll_x,img_unscroll_y))
        print("img: (%.2f,%.2f)"%(img_x,img_y))

        return (img_x, img_y)

    @debug_fxn
    def init_image_from_file(self, img_path):
        self.img_path = img_path

        # check for 1sc files and get image data to send to Image
        (imgfile_base, imgfile_ext) = os.path.splitext(img_path)
        if imgfile_ext == ".1sc":
            try:
                read1sc = biorad1sc_reader.Reader(img_path)
            except:
                # img_ok is false if 1sc is not valid 1sc file
                return False

            (img_x, img_y, img_data) = read1sc.get_img_data()

            # TODO: wx.Image is probably only 8-bits each color channel
            #   yet we have 16-bit images
            # wx.Image wants img_x * img_y * 3
            # TODO: shadow data with full 16-bit info
            img_data_rgb = np.zeros(img_data.size*3, dtype='uint8')
            img_data_rgb[0::3] = img_data//256
            img_data_rgb[1::3] = img_data//256
            img_data_rgb[2::3] = img_data//256
            self.img = wx.Image(img_x, img_y, bytes(img_data_rgb))
        else:
            self.img = wx.Image(img_path)

        img_ok = self.img.IsOk()
        if img_ok:
            self.img_size_y = self.img.GetHeight()
            self.img_size_x = self.img.GetWidth()

            if DEBUG & DEBUG_TIMING:
                staticdc_start = time.time()

            # store image data into a static DCs
            # full-size static DC
            img_bmp = wx.Bitmap(self.img)
            self.img_dc = wx.MemoryDC()
            self.img_dc.SelectObject(img_bmp)

            # half-size static DC
            img_bmp = wx.Bitmap(
                    self.img.Scale(self.img_size_x/2, self.img_size_y/2)
                    )
            self.img_dc_div2 = wx.MemoryDC()
            self.img_dc_div2.SelectObject(img_bmp)

            # quarter-size static DC
            img_bmp = wx.Bitmap(
                    self.img.Scale(self.img_size_x/4, self.img_size_y/4)
                    )
            self.img_dc_div4 = wx.MemoryDC()
            self.img_dc_div4.SelectObject(img_bmp)

            if DEBUG & DEBUG_TIMING:
                staticdc_eltime = time.time() - staticdc_start
                print("TIM:Create MemoryDCs: *%.3fs"%staticdc_eltime)

            # set zoom_idx to scaling that will fit image in window
            #   or 1.0 if max_zoom > 1.0
            win_size = self.GetSize()

            max_zoom = min(
                    [1.000001,
                        (win_size.x / self.img_size_x),
                        (win_size.y / self.img_size_y)
                        ]
                    )
            ok_zooms = [x for x in self.zoom_list if x < max_zoom]
            self.zoom_idx = self.zoom_list.index(max(ok_zooms))
            self.zoom = self.zoom_list[self.zoom_idx]

            self.set_virt_size_with_min()

            # start w/ image center at window center
            self.img_at_wincenter_x = self.img_size_x/2
            self.img_at_wincenter_y = self.img_size_y/2

            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

        return img_ok

    @debug_fxn
    def zoom_in(self, zoom_amt, do_refresh=True):
        """Zoom in the image in this window (increase zoom ratio).  There
        is a fixed list of zoom ratios, move down in the list

        Args:
            zoom_amt (int): How many positions to move down in the zoom ratio
                list
            do_refresh (bool, default=True): whether to force a refresh now
                after changing the zoom ratio

        Returns:
            self.zoom (float): resulting zoom ratio (1.00 is 1x zoom)
        """
        # return early if we're at max
        if not self.img or self.zoom_idx == len(self.zoom_list)-1:
            return

        self.zoom_idx += zoom_amt

        # enforce max zoom
        if self.zoom_idx > len(self.zoom_list)-1:
            self.zoom_idx = len(self.zoom_list)-1

        # record floating point zoom
        self.zoom = self.zoom_list[self.zoom_idx]

        # expand virtual window size
        self.set_virt_size_with_min()

        # scroll so center of image at same point it used to be
        self.scroll_to_img_at_wincenter()

        if do_refresh:
            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

        return self.zoom

    @debug_fxn
    def zoom_out(self, zoom_amt, do_refresh=True):
        """Zoom out the image in this window (reduce zoom ratio).  There
        is a fixed list of zoom ratios, move up in the list

        Args:
            zoom_amt (int): How many positions to move up in the zoom ratio
                list
            do_refresh (bool, default=True): whether to force a refresh now
                after changing the zoom ratio

        Returns:
            self.zoom (float): resulting zoom ratio (1.00 is 1x zoom)
        """
        # return early if no image or we're at max
        if not self.img or self.zoom_idx == 0:
            return

        self.zoom_idx -= zoom_amt

        # enforce min zoom
        if self.zoom_idx < 0:
            self.zoom_idx = 0

        # record floating point zoom
        self.zoom = self.zoom_list[self.zoom_idx]

        # contract virtual window size
        self.set_virt_size_with_min()

        # scroll so center of image at same point it used to be
        self.scroll_to_img_at_wincenter()

        if do_refresh:
            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

        return self.zoom

    @debug_fxn
    def pan_down(self, pan_amt):
        """Scroll the current viewport so we see an area below

        Args:
            pan_amt (float): amount to pan in pixels of the image

        Returns:
            None
        """
        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_y = self.GetScrollPos(wx.VERTICAL)
        (_, scroll_ppu_y) = self.GetScrollPixelsPerUnit()
        scroll_amt = max([round(pan_amt/scroll_ppu_y), 1])

        self.Scroll(wx.DefaultCoord, scroll_y + scroll_amt)
        # self.Scroll doesn't create an EVT_SCROLLWIN event, so we need to
        #   update wincenter position manually
        self.get_img_wincenter()

    @debug_fxn
    def pan_up(self, pan_amt):
        """Scroll the current viewport so we see an area above

        Args:
            pan_amt (float): amount to pan in pixels of the image

        Returns:
            None
        """
        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_y = self.GetScrollPos(wx.VERTICAL)
        (_, scroll_ppu_y) = self.GetScrollPixelsPerUnit()
        scroll_amt = max([round(pan_amt/scroll_ppu_y), 1])

        self.Scroll(wx.DefaultCoord, scroll_y - scroll_amt)
        # self.Scroll doesn't create an EVT_SCROLLWIN event, so we need to
        #   update wincenter position manually
        self.get_img_wincenter()

    @debug_fxn
    def pan_right(self, pan_amt):
        """Scroll the current viewport so we see an area to the right

        Args:
            pan_amt (float): amount to pan in pixels of the image

        Returns:
            None
        """
        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_x = self.GetScrollPos(wx.HORIZONTAL)
        (scroll_ppu_x, _) = self.GetScrollPixelsPerUnit()
        scroll_amt = max([round(pan_amt/scroll_ppu_x), 1])

        self.Scroll(scroll_x + scroll_amt, wx.DefaultCoord)
        # self.Scroll doesn't create an EVT_SCROLLWIN event, so we need to
        #   update wincenter position manually
        self.get_img_wincenter()

    @debug_fxn
    def pan_left(self, pan_amt):
        """Scroll the current viewport so we see an area to the left

        Args:
            pan_amt (float): amount to pan in pixels of the image

        Returns:
            None
        """
        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_x = self.GetScrollPos(wx.HORIZONTAL)
        (scroll_ppu_x, _) = self.GetScrollPixelsPerUnit()
        scroll_amt = max([round(pan_amt/scroll_ppu_x), 1])

        self.Scroll(scroll_x - scroll_amt, wx.DefaultCoord)
        # self.Scroll doesn't create an EVT_SCROLLWIN event, so we need to
        #   update wincenter position manually
        self.get_img_wincenter()


class DropTarget(wx.FileDropTarget):
    """DropTarget Facilitating dragging file into window to open
    """
    def __init__(self, window_target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_target = window_target

    def OnDropFiles(self, x, y, filenames):
        filename = filenames[0]
        if DEBUG & DEBUG_MISC:
            print("MSC:", end="")
            print("Drag and Drop filename:")
            print("    "+repr(filename))
        self.window_target.init_image_from_file(filename)

        # TODO: which one of these??
        #return wx.DragCopy
        return True


class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_ui()

    @debug_fxn
    def init_ui(self):
        # Add image handlers for wx (necessary?)
        #wx.Image.AddHandler(wx.PNGHandler)
        #wx.Image.AddHandler(wx.TIFFHandler)

        # menu bar stuff
        menubar = wx.MenuBar()
        # File
        file_menu = wx.Menu()
        fitem = file_menu.Append(wx.ID_EXIT,
                'Quit', 'Quit application\tCtrl+Q')
        oitem = file_menu.Append(wx.ID_OPEN,
                'Open Image...\tCtrl+O', 'Open image file')
        satem = file_menu.Append(wx.ID_SAVEAS,
                'Save Image Data As...', 'Save image file and associated data')
        menubar.Append(file_menu, '&File')
        # Help
        help_menu = wx.Menu()
        aboutitem = help_menu.Append(wx.ID_ABOUT, "&About Cellcounter")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        # toolbar stuff
        toolbar = self.CreateToolBar()
        if DEBUG & DEBUG_MISC:
            print( "MSC:ICON_DIR=%s"%(ICON_DIR ))
        obmp = os.path.join(ICON_DIR,'topen32.png')
        otool = toolbar.AddTool(wx.ID_OPEN, 'Open', wx.Bitmap(obmp))
        toolbar.Realize()

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
        self.img_panel = ImageScrolledCanvas(self)

        # make ImageScrolledCanvas Drag and Drop Target
        self.img_panel.SetDropTarget(DropTarget(self.img_panel))

        mybox.Add(self.img_panel, 1, wx.EXPAND)
        self.SetSizer(mybox)

        # setup event handlers for toolbar, menus
        self.Bind(wx.EVT_TOOL, self.on_open, otool)
        self.Bind(wx.EVT_MENU, self.on_quit, fitem)
        self.Bind(wx.EVT_MENU, self.on_open, oitem)
        self.Bind(wx.EVT_MENU, self.on_about, aboutitem)

        # finally render app
        self.SetSize((800, 600))
        self.SetTitle('Cell Counter')
        self.Centre()

        #self.img_panel.subpanel.Centre()

        self.Show(True)

        if DEBUG & DEBUG_MISC:
            print("MSC:", end="")
            print("self.img_panel size:")
            print("    "+repr(self.img_panel.GetClientSize()))

    @debug_fxn
    def on_quit(self, evt):
        self.Close()

    @debug_fxn
    def on_key_down(self, evt):
        KeyCode = evt.GetKeyCode()
        if DEBUG & DEBUG_KEYPRESS:
            print("KEY:Key Down:")
            print("    KeyCode: ", end="", flush=True)
            print(KeyCode)
            print("    RawKeyCode: ", end="", flush=True)
            print(evt.GetRawKeyCode())
            print("    Position: ", end="", flush=True)
            print(evt.GetPosition())

        if KeyCode == 91:
            # [ key
            #  KeyCode: 91
            #  RawKeyCode: 33
            zoom = self.img_panel.zoom_out(1)
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))
        if KeyCode == 93:
            # ] key
            #  KeyCode: 93
            #  RawKeyCode: 30
            zoom = self.img_panel.zoom_in(1)
            if zoom:
                self.statusbar.SetStatusText("Zoom: %.1f%%"%(zoom*100))

        # keys usually scroll, so down arrow makes image go up, etc.
        # "arrow keys move virtual viewport over image"
        # NOTE: if we wanted to automatically implement panning, we could
        #   just evt.Skip in the following if statements
        if KeyCode == 314:
            # left key
            self.img_panel.pan_left(20)
        if KeyCode == 315:
            # up key
            self.img_panel.pan_up(20)
        if KeyCode == 316:
            # right key
            self.img_panel.pan_right(20)
        if KeyCode == 317:
            # down key
            self.img_panel.pan_down(20)

        if KeyCode == 366:
            # PAGE UP
            # skip to process page up
            evt.Skip()
        if KeyCode == 367:
            # PAGE DOWN
            # skip to process page up
            evt.Skip()
        if KeyCode == 313:
            # HOME
            # skip to process HOME
            evt.Skip()
        if KeyCode == 312:
            # END
            # skip to process END
            evt.Skip()

        if KeyCode == 32:
            # Space Bar
            pass

    @debug_fxn
    def on_open(self, evt):
        #if self.contentNotSaved:
        #    if wx.MessageBox(
        #            "Current content has not been saved! Proceed?",
        #            "Please confirm",
        #             wx.ICON_QUESTION | wx.YES_NO, self) == wx.NO:
        #        return

        # else: proceed asking to the user the new file to open

        # create wildcard for Image files, and for *.1sc files (Bio-Rad)
        wildcard = wx.Image.GetImageExtWildcard()
        wildcard = "Image Files " + wildcard + "|Bio-Rad 1sc Files|*.1sc"
        open_file_dialog = wx.FileDialog(self,
                "Open image file",
                wildcard=wildcard,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_file_dialog.ShowModal() == wx.ID_CANCEL:
            # the user canceled
            return

        # get filepath and attempt to open image into bitmap
        img_path = open_file_dialog.GetPath()
        img_ok = self.img_panel.init_image_from_file(img_path)

        if img_ok:
            self.statusbar.SetStatusText("Image " + img_path + " loaded OK.")
        else:
            self.statusbar.SetStatusText(
                    "Image " + img_path + " loading ERROR."
                    )

    @debug_fxn
    def on_about(self, evt):
        info = wx.adv.AboutDialogInfo()
        info.SetName("Cellcounter")
        info.SetVersion("0.1.0")
        info.SetDescription("Counting cells in biological images.")
        info.SetCopyright("(C) 2017 Matthew A. Clapp")

        wx.adv.AboutBox(info)


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
            description="View images of cells, and allow for counting of them.")

    # specifying nargs= puts outputs of parser in list (even if nargs=1)

    # positional arguments
    parser.add_argument('srcfile', nargs='*',
            help="Source directory (recursively searched)."
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
    main_win = MainWindow(None)
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
