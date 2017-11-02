#!/usr/bin/env python3
#
# GUI for displaying an image and counting cells

import sys
import time
import argparse
import os.path
import numpy as np
import biorad1sc_reader
from biorad1sc_reader import BioRadInvalidFileError, BioRadParsingError
import wx
import wx.adv
import wx.html
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


def ceil(num):
    if int(num) < num:
        return int(num) + 1
    else:
        return int(num)


def clip(num, num_min=None, num_max=None):
    if num_min is not None and num_max is not None:
        return min(max(num, num_min), num_max)
    elif num_min is not None:
        return max(num, num_min)
    elif num_max is not None:
        return min(num, num_max)
    else:
        return num


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
        self.img_at_wincenter_x = None
        self.img_at_wincenter_y = None
        self.img_coord_xlation_x = None
        self.img_coord_xlation_y = None
        self.img_dc = None
        self.img_dc_div2 = None
        self.img_dc_div4 = None
        self.img_path = None    # TODO: do we need this?
        self.img_size_x = None
        self.img_size_y = None
        self.mark_mode = False
        self.parent = None    # TODO: do we need this?
        self.points_record = []
        self.zoom = None
        self.zoom_idx = None
        self.zoom_list = None

        # prevent erasing of background before paint events
        #   we will be responsible for painting entire window, which we
        #   usually do anyway.
        # TODO: also style=wx.BUFFER_VIRTUAL_AREA for Windows flicker?
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

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
        # DELETEME OBSOLETE
        #self.blank_img()

        # setup handlers
        self.Bind(wx.EVT_PAINT, self.OnPaint)
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
                ) = self.win2img_coord(win_size_x/2, win_size_y/2)

        if DEBUG & DEBUG_MISC:
            print(
                    "MSC:self.img_at_wincenter=(%.3f,%.3f)"%(
                        self.img_at_wincenter_x,
                        self.img_at_wincenter_y
                        )
                    )

    @debug_fxn
    def scroll_to_img_at_wincenter(self):
        """
        Scroll window so center of window is at
        (self.img_at_wincenter_x, self.img_at_wincenter_y)
        """
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

    def wincenter_scroll_limits(self):
        """
        get min, max coordinates that can lie in center of window

        Returns:
            tuple: (img_x_min, img_y_min, img_x_max, img_y_max)
        """
        # GetClientSize returns physical window dimensions, not unscrolled
        (win_size_x, win_size_y) = self.GetClientSize()
        win_size_img_x = win_size_x / self.zoom
        win_size_img_y = win_size_y / self.zoom

        if win_size_img_x > self.img_size_x:
            img_x_min = self.img_size_x / 2
            img_x_max = self.img_size_x / 2
        else:
            img_x_min = win_size_x / 2 / self.zoom
            img_x_max = self.img_size_x - (win_size_x / 2 / self.zoom)

        if win_size_img_y > self.img_size_y:
            img_y_min = self.img_size_y / 2
            img_y_max = self.img_size_y / 2
        else:
            img_y_min = win_size_y / 2 / self.zoom
            img_y_max = self.img_size_y - (win_size_y / 2 / self.zoom)

        if DEBUG & DEBUG_MISC:
            print("MSC:wincenter img limits (%.2f,%.2f) to (%.2f,%.2f)"%(img_x_min, img_y_min, img_x_max, img_y_max))

        return (img_x_min, img_y_min, img_x_max, img_y_max)

    @debug_fxn
    def on_left_down(self, evt):
        """Handle mouse left-clicks

        Args:
            evt (wx.MouseEvent): todo.
        """
        # return early if no image
        if self.img_dc is None:
            wx.CallAfter(evt.Skip)
            return

        # point coordinate returned seems:
        #   * be only absolute coordinates of where in window was clicked
        #   * not to depend on which img_dc we supply
        #   * not to depend on zoom or pan
        point = evt.GetLogicalPosition(self.img_dc)
        (img_x, img_y) = self.win2img_coord(point.x, point.y)

        if DEBUG & DEBUG_MISC:
            print("MSC:left click at img", end="")
            print("(%.2f, %.2f)"%(img_x, img_y))

        if (0 <= img_x <= self.img_size_x and
                0 <= img_y <= self.img_size_y):
            if self.mark_mode:
                self.draw_at_point(img_x, img_y)
            else:
                # TODO: select mode selects nearby mark (possibly to delete)
                #   selecting with no mark nearby deselects
                #   find the closest cross to click, as long as it is close
                #       enough to click
                #   then color cross yellow and that one will be "selected"
                #   can be deleted
                #   clicking far from any crosses deselects all
                if DEBUG & DEBUG_MISC:
                    print("MSC:Not in Mark Mode")

        # continue processing click, for example shifting focus to app
        evt.Skip()

    @debug_fxn
    def on_right_down(self, evt):
        """Handle mouse right-clicks

        Args:
            evt (wx.MouseEvent): todo.
        """
        # return early if no image
        if self.img_dc is None:
            wx.CallAfter(evt.Skip)
            return

        # point coordinate returned seems:
        #   * be only absolute coordinates of where in window was clicked
        #   * not to depend on which img_dc we supply
        #   * not to depend on zoom or pan
        point = evt.GetLogicalPosition(self.img_dc)
        (img_x, img_y) = self.win2img_coord(point.x, point.y)

        if DEBUG & DEBUG_MISC:
            print("MSC:right click at img", end="")
            print("(%.2f, %.2f)"%(img_x, img_y))

        #self.img_at_wincenter_x = img_x
        #self.img_at_wincenter_y = img_y
        #self.scroll_to_img_at_wincenter()
        self.panimate(img_x, img_y, 1250)

        # continue processing click, for example shifting focus to app
        evt.Skip()

    @debug_fxn
    def panimate(self, img_x_end, img_y_end, max_speed):
        """Animate a pan from current scroll position to destination position

        Args:
            img_x_end (int): destination x pan location in img coordinates
            img_y_end (int): destination y pan location in img coordinates
            max_speed (float): maximum speed of pan in win pixels/sec
        """
        max_speed = clip(max_speed, 1, None)
        img_max_speed = max_speed / self.zoom

        (xmin, ymin, xmax, ymax) = self.wincenter_scroll_limits()

        # clip values for end coordinates to max zoom area
        img_x_end = clip(img_x_end, xmin, xmax)
        img_y_end = clip(img_y_end, ymin, ymax)

        img_x_start = self.img_at_wincenter_x
        img_y_start = self.img_at_wincenter_y

        # if we're not moving then just return
        if img_x_end == img_x_start and img_y_end == img_y_start:
            return

        if DEBUG & DEBUG_MISC:
            print("MSC:panimate: start=(%.2f,%.2f)"%(img_x_start,img_y_start), end="")
            print("end=(%.2f, %.2f)"%(img_x_end, img_y_end))

        img_dist = np.sqrt((img_x_end - img_x_start)**2 + (img_y_end - img_y_start)**2)

        steps = clip(
                img_dist / img_max_speed / (const.PANIMATE_STEP_MS * 1e-3),
                5, None
                )

        img_x_vals = list(np.linspace(img_x_start, img_x_end, steps))
        img_y_vals = list(np.linspace(img_y_start, img_y_end, steps))

        # accel / decel at 0.1*speed/sec
        #   replace first 2 points with 3 new ones
        #   [0.0, 0.5, 1.0, 1.5, ...]
        #   becomes
        #   [0.1, 0.3, 0.6, 1.0, 1.5 ...]
        # don't include orig point (it's where we are)
        img_x_prevals = [
                0.1*img_x_vals[2]+0.9*img_x_vals[0],
                0.3*img_x_vals[2]+0.7*img_x_vals[0],
                0.6*img_x_vals[2]+0.4*img_x_vals[0],
                ]
        img_x_postvals = [
                0.6*img_x_vals[-3]+0.4*img_x_vals[-1],
                0.3*img_x_vals[-3]+0.7*img_x_vals[-1],
                0.1*img_x_vals[-3]+0.9*img_x_vals[-1],
                img_x_vals[-1]
                ]
        img_x_vals = img_x_prevals + img_x_vals[2:-2] + img_x_postvals
        img_y_prevals = [
                0.1*img_y_vals[2]+0.9*img_y_vals[0],
                0.3*img_y_vals[2]+0.7*img_y_vals[0],
                0.6*img_y_vals[2]+0.4*img_y_vals[0],
                ]
        img_y_postvals = [
                0.6*img_y_vals[-3]+0.4*img_y_vals[-1],
                0.3*img_y_vals[-3]+0.7*img_y_vals[-1],
                0.1*img_y_vals[-3]+0.9*img_y_vals[-1],
                img_y_vals[-1]
                ]
        img_y_vals = img_y_prevals + img_y_vals[2:-2] + img_y_postvals

        wx.CallLater(
                const.PANIMATE_STEP_MS,
                self.panimate_step, img_x_vals, img_y_vals, time.time()
                )

    @debug_fxn
    def panimate_step(self, x_vals, y_vals, last_time):
        # check if time since last panimate step is multiple steps
        #   and skip ahead if so
        pop_num = int((time.time()-last_time)/(const.PANIMATE_STEP_MS*1e-3))
        # 1 <= pop_num <= len(x_vals)
        pop_num = clip(pop_num, 1, len(x_vals))
        for i in range(pop_num):
            self.img_at_wincenter_x = x_vals.pop(0)
            self.img_at_wincenter_y = y_vals.pop(0)
        self.scroll_to_img_at_wincenter()
        if x_vals:
            wx.CallLater(
                    const.PANIMATE_STEP_MS,
                    self.panimate_step, x_vals, y_vals, time.time()
                    )
        else:
            wx.CallAfter(self.get_img_wincenter)

    @debug_fxn
    def draw_at_point(self, pt_x, pt_y):
        point_x = int(pt_x)
        point_y = int(pt_y)

        if DEBUG & DEBUG_MISC:
            print("MSC: point", end="")
            print("(%d, %d)"%(point_x, point_y))

        self.points_record.append((point_x, point_y))

        # force a paint event with Refresh and Update
        #   to force PaintRect to paint new cross
        (pos_x, pos_y) = self.img2win_coord(point_x + 0.5, point_y + 0.5)
        # refresh square size should be >= than cross size
        sq_size = 16
        self.RefreshRect(
                wx.Rect(
                    pos_x - sq_size/2, pos_y - sq_size/2,
                    sq_size, sq_size
                    )
                )
        self.Update()

    @debug_fxn
    def on_scroll(self, evt):
        # return early if no image
        if self.img_dc is None:
            wx.CallAfter(evt.Skip)
            return

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
            self.pan_left(const.SCROLL_WHEEL_SPEED)
        elif Orientation == wx.HORIZONTAL and EventType == wx.wxEVT_SCROLLWIN_LINEDOWN:
            self.pan_right(const.SCROLL_WHEEL_SPEED)
        elif Orientation == wx.VERTICAL and EventType == wx.wxEVT_SCROLLWIN_LINEUP:
            self.pan_up(const.SCROLL_WHEEL_SPEED)
        elif Orientation == wx.VERTICAL and EventType == wx.wxEVT_SCROLLWIN_LINEDOWN:
            self.pan_down(const.SCROLL_WHEEL_SPEED)
        else:
            # process with default handler(s)
            evt.Skip()

    # DELETEME OBSOLETE
    #@debug_fxn
    #def blank_img(self):
    #    # Image object currently loaded
    #    #   None signals to methods not to pan, zoom, etc
    #    self.img = None
    #    # image path for current Image
    #    self.img_path = None
    #    # transparent placeholder img (2px x 2px of tranparent black)
    #    # will be bitmap corresponding to image
    #    img_bmp = wx.Bitmap.FromRGBA(2, 2, 0, 0, 0, 0)
    #    # store image data into a static DC
    #    self.img_dc = wx.MemoryDC()
    #    self.img_dc.SelectObject(img_bmp)
    #    # current position of image center
    #    #   start w/ 2px x 2px anchored with 1,1 at wincenter
    #    self.img_at_wincenter_x = 1
    #    self.img_at_wincenter_y = 1
    #    # size of image
    #    self.img_size_y = 2
    #    self.img_size_x = 2
    #    self.zoom = 1.0

    #    self.SetVirtualSize(2, 2)
    #    self.set_virt_size_with_min()

    @debug_fxn
    def set_virt_size_with_min(self):
        """Set size of unscrolled canvas for image_size, making virtual size
        same as image if image is zoomed larger than window, or as large as
        window if image is smaller than window in order to be able to center
        image in window.
        """
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
        # return early if no image
        if self.img_dc is None:
            return

        self.set_virt_size_with_min()

        # scroll so center of image at same point it used to be
        self.scroll_to_img_at_wincenter()

    # GetClientSize is size of window graphics not including scrollbars
    # GetSize is size of window including scrollbars
    @debug_fxn
    def OnPaint(self, evt):
        """EVT_PAINT event handler to update window area

        Args:
            evt (wx.PaintEvent): no useful information
        """
        if DEBUG & DEBUG_TIMING:
            start_onpaint = time.time()

        # TODO: flicker is a problem in Windows.
        #   * use BufferedPaintDC or AutoBufferedPaintDC instead of PaintDC
        #   * call wx.Window.SetBackgroundStyle with wx.BG_STYLE_PAINT
        #       (also style=wx.BUFFER_VIRTUAL_AREA ?)
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
                    "TIM:OnPaint: %.3fs, zoom = %.3f, panel_size=(%d,%d)"%(
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

        # if no image, fill area with background color
        if self.img_dc is None:
            dc.SetPen(wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT))
            dc.SetBrush(dc.GetBackground())
            dc.DrawRectangle(rect_pos_x, rect_pos_y, rect_size_x, rect_size_y)
            # DONE
            return

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

        # rect_pos_{x,y} is upper left corner
        # rect_lr_{x,y} is lower right corner
        rect_lr_x = rect_pos_x + rect_size_x
        rect_lr_y = rect_pos_y + rect_size_y
        (rect_pos_log_x, rect_pos_log_y) = self.CalcUnscrolledPosition(
                rect_pos_x, rect_pos_y)
        (rect_lr_log_x, rect_lr_log_y) = self.CalcUnscrolledPosition(
                rect_lr_x, rect_lr_y)

        # img coordinates of upper left corner
        (src_pos_x, src_pos_y) = self.logical2img_coord(
                rect_pos_log_x, rect_pos_log_y,
                scale_dc=scale_dc
                )
        # make int and enforce min. val of 0
        src_pos_x = clip(int(src_pos_x), 0, None)
        src_pos_y = clip(int(src_pos_y), 0, None)
        # img coordinates of lower right corner
        (src_lr_x, src_lr_y) = self.logical2img_coord(
                rect_lr_log_x, rect_lr_log_y,
                scale_dc=scale_dc
                )
        # make int (via ceil) and enforce max. val of img_dc_src size
        dc_size = img_dc_src.GetSize()
        src_lr_x = clip(ceil(src_lr_x), None, dc_size.x)
        src_lr_y = clip(ceil(src_lr_y), None, dc_size.y)

        # multiply pos back out to get slightly off-window but
        #   on src-pixel-boundary coords for dest
        # dest coordinates are all logical
        (dest_pos_x, dest_pos_y) = self.img2logical_coord(
                src_pos_x, src_pos_y, scale_dc=scale_dc
               )
        dest_pos_x = round(dest_pos_x)
        dest_pos_y = round(dest_pos_y)
        # multiply size back out to get slightly off-window but
        #   on src-pixel-boundary coords for dest
        (dest_lr_x, dest_lr_y) = self.img2logical_coord(
                src_lr_x, src_lr_y, scale_dc=scale_dc
                )
        dest_lr_x = round(dest_lr_x)
        dest_lr_y = round(dest_lr_y)

        # compute src size
        src_size_x = src_lr_x - src_pos_x
        src_size_y = src_lr_y - src_pos_y
        # compute dest size
        dest_size_x = dest_lr_x - dest_pos_x
        dest_size_y = dest_lr_y - dest_pos_y

        # paint bg rectangles around border if necessary
        left_gap = clip(dest_pos_x - rect_pos_log_x, 0, None)
        right_gap = clip(rect_lr_log_x - dest_lr_x, 0, None)
        top_gap = clip(dest_pos_y - rect_pos_log_y, 0, None)
        bottom_gap = clip(rect_lr_log_y - dest_lr_y, 0, None)

        dc.SetPen(wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT))
        # debug pen:
        #dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), width=1, style=wx.SOLID))
        dc.SetBrush(dc.GetBackground())
        rects_to_draw = []
        if top_gap > 0:
            rects_to_draw.append(
                    (rect_pos_log_x, rect_pos_log_y, rect_size_x, top_gap)
                    )
        if bottom_gap > 0:
            rects_to_draw.append(
                    (rect_pos_log_x, dest_lr_y, rect_size_x, bottom_gap)
                    )
        if left_gap > 0:
            rects_to_draw.append(
                    (rect_pos_log_x, dest_pos_y, left_gap, rect_size_y - top_gap - bottom_gap)
                    )
        if right_gap > 0:
            rects_to_draw.append(
                    (dest_lr_x, dest_pos_y, right_gap, rect_size_y - top_gap - bottom_gap)
                    )
        if rects_to_draw:
            dc.DrawRectangleList(rects_to_draw)

        # DEBUG DELETEME
        if DEBUG & DEBUG_MISC:
            print("MSC:")
            print("    src_pos=(%.2f,%.2f)"%(src_pos_x,src_pos_y))
            print("    src_size=(%.2f,%.2f)"%(src_size_x,src_size_y))
            print("    dest_pos=(%.2f,%.2f)"%(dest_pos_x,dest_pos_y))
            print("    dest_size=(%.2f,%.2f)"%(dest_size_x,dest_size_y))
            print("    rect_pos=(%.2f,%.2f)"%(rect_pos_log_x,rect_pos_log_y))
            print("    rect_size=(%.2f,%.2f)"%(rect_size_x,rect_size_y))

        # NOTE: Blit shows no performance advantage over StretchBlit (Mac)
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

        # draw crosses visible in this region
        # need to multiply by scale_dc to get back to div1 image coordinates
        self.draw_crosses(
                dc,
                src_pos_x*scale_dc, src_pos_y*scale_dc,
                src_size_x*scale_dc, src_size_y*scale_dc)

    @debug_fxn
    def draw_crosses(self, dc, src_pos_x, src_pos_y, src_size_x, src_size_y):
        pts_in_box = []
        for (x, y) in self.points_record:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                (x_win, y_win) = self.img2logical_coord(x + 0.5, y + 0.5)
                if (x_win, y_win) not in pts_in_box:
                    # only draw bitmap if this is not a duplicate
                    pts_in_box.append((x_win, y_win))
                    # NOTE: if you change the size of this bmp, also change
                    #   the RefreshRect size in self.draw_at_point()
                    dc.DrawBitmap(const.CROSS_11x11_RED_BMP, x_win - 6, y_win - 6)

    @debug_fxn
    def win2img_coord(self, win_x, win_y, scale_dc=1):
        """Given plain window coordinates, return image coordinates

        Args:
            win_x (float): window device coordinates
            win_y (float): window device coordinates

        Returns:
            tuple: (img_x (float), img_y (float)) position in src image
                coordinates
        """
        # img_coord_xlation_{x,y} = 0 unless window is bigger than image
        #   in which case this is non-zero translation of left,top padding
        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom to get to img coordinates

        (win_unscroll_x, win_unscroll_y) = self.CalcUnscrolledPosition(win_x, win_y)

        img_x = (win_unscroll_x - self.img_coord_xlation_x) / self.zoom / scale_dc
        img_y = (win_unscroll_y - self.img_coord_xlation_y) / self.zoom / scale_dc

        return (img_x, img_y)

    @debug_fxn
    def logical2img_coord(self, logical_x, logical_y, scale_dc=1):
        """Given logical unscrolled canvas coordinates, return image coordinates

        Args:
            win_x (float): logical canvas (unscrolled) coordinates
            win_y (float): logical canvas (unscrolled) coordinates

        Returns:
            tuple: (img_x (float), img_y (float)) position in src image
                coordinates
        """
        # img_coord_xlation_{x,y} = 0 unless window is bigger than image
        #   in which case this is non-zero translation of left,top padding
        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom to get to img coordinates

        img_x = (logical_x - self.img_coord_xlation_x) / self.zoom / scale_dc
        img_y = (logical_y - self.img_coord_xlation_y) / self.zoom / scale_dc

        return (img_x, img_y)

    @debug_fxn
    def img2logical_coord(self, img_x, img_y, scale_dc=1):
        """Given image coordinates, return logical unscrolled canvas coordinates

        Args:
            img_x (float): src image coordinates
            img_y (float): src image coordinates

        Returns:
            tuple: (logical_x (float), logical_y (float)) position in
                logical unscrolled canvas coordinates
        """
        win_unscroll_x = img_x * self.zoom * scale_dc + self.img_coord_xlation_x
        win_unscroll_y = img_y * self.zoom * scale_dc + self.img_coord_xlation_y
        return (win_unscroll_x, win_unscroll_y)

    @debug_fxn
    def img2win_coord(self, img_x, img_y, scale_dc=1):
        """Given image coordinates, return plain window coordinates

        Args:
            img_x (float): src image coordinates
            img_y (float): src image coordinates

        Returns:
            tuple: (win_x (float), win_y (float)) position in device
                window coordinates
        """
        win_logical_x = img_x * self.zoom * scale_dc + self.img_coord_xlation_x
        win_logical_y = img_y * self.zoom * scale_dc + self.img_coord_xlation_y
        (win_x, win_y) = self.CalcScrolledPosition(win_logical_x, win_logical_y)
        return (win_x, win_y)

    @debug_fxn
    def init_image_from_file(self, img_path):
        """Load and initialize image given its full path

        Args:
            img_path (str): full path to image to load into app
        """
        self.img_path = img_path

        # check for 1sc files and get image data to send to Image
        (_, imgfile_ext) = os.path.splitext(img_path)
        if imgfile_ext == ".1sc":
            try:
                read1sc = biorad1sc_reader.Reader(img_path)
            except (BioRadInvalidFileError, BioRadParsingError):
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
            img = wx.Image(img_x, img_y, bytes(img_data_rgb))
        else:
            img = wx.Image(img_path)

        img_ok = img.IsOk()
        if img_ok:
            self.img_size_y = img.GetHeight()
            self.img_size_x = img.GetWidth()

            if DEBUG & DEBUG_TIMING:
                staticdc_start = time.time()

            # store image data into a static DCs
            # full-size static DC
            img_bmp = wx.Bitmap(img)
            self.img_dc = wx.MemoryDC()
            self.img_dc.SelectObject(img_bmp)

            # half-size static DC
            img_bmp = wx.Bitmap(
                    img.Scale(self.img_size_x/2, self.img_size_y/2)
                    )
            self.img_dc_div2 = wx.MemoryDC()
            self.img_dc_div2.SelectObject(img_bmp)

            # quarter-size static DC
            img_bmp = wx.Bitmap(
                    img.Scale(self.img_size_x/4, self.img_size_y/4)
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
                    1.000001,
                    (win_size.x / self.img_size_x),
                    (win_size.y / self.img_size_y)
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
        # return early if no image or we're at max
        if self.img_dc is None or self.zoom_idx == len(self.zoom_list)-1:
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
        if self.img_dc is None or self.zoom_idx == 0:
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
        # return early if no image
        if self.img_dc is None:
            return

        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_y = self.GetScrollPos(wx.VERTICAL)
        (_, scroll_ppu_y) = self.GetScrollPixelsPerUnit()
        scroll_amt = clip(round(pan_amt/scroll_ppu_y), 1, None)

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
        # return early if no image
        if self.img_dc is None:
            return

        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_y = self.GetScrollPos(wx.VERTICAL)
        (_, scroll_ppu_y) = self.GetScrollPixelsPerUnit()
        scroll_amt = clip(round(pan_amt/scroll_ppu_y), 1, None)

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
        # return early if no image
        if self.img_dc is None:
            return

        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_x = self.GetScrollPos(wx.HORIZONTAL)
        (scroll_ppu_x, _) = self.GetScrollPixelsPerUnit()
        scroll_amt = clip(round(pan_amt/scroll_ppu_x), 1, None)

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
        # return early if no image
        if self.img_dc is None:
            return

        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_x = self.GetScrollPos(wx.HORIZONTAL)
        (scroll_ppu_x, _) = self.GetScrollPixelsPerUnit()
        scroll_amt = clip(round(pan_amt/scroll_ppu_x), 1, None)

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
    def __init__(self, srcfiles, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.marktool = None
        self.html = None
        self.init_ui()
        if srcfiles:
            # TODO: are we able to load more than one file?
            self.load_image_from_path(srcfiles[0])

    @debug_fxn
    def init_ui(self):
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
        helpitem = help_menu.Append(wx.ID_HELP, "&Cellcounter Help")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        # toolbar stuff
        toolbar = self.CreateToolBar()
        if DEBUG & DEBUG_MISC:
            print("MSC:ICON_DIR=%s"%(ICON_DIR))
        obmp = os.path.join(ICON_DIR, 'topen32.png')
        otool = toolbar.AddTool(wx.ID_OPEN, 'Open', wx.Bitmap(obmp))
        markbmp = os.path.join(ICON_DIR, 'marktool32.png')
        self.marktool = toolbar.AddCheckTool(
                wx.ID_ANY,
                'Point/Mark',
                wx.Bitmap(markbmp),
                )
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
        self.Bind(wx.EVT_TOOL, self.on_mark_toggle, self.marktool)
        self.Bind(wx.EVT_MENU, self.on_quit, fitem)
        self.Bind(wx.EVT_MENU, self.on_open, oitem)
        self.Bind(wx.EVT_MENU, self.on_about, aboutitem)
        self.Bind(wx.EVT_MENU, self.on_help, helpitem)

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
            self.img_panel.pan_left(const.SCROLL_KEY_SPEED)
        if KeyCode == 315:
            # up key
            self.img_panel.pan_up(const.SCROLL_KEY_SPEED)
        if KeyCode == 316:
            # right key
            self.img_panel.pan_right(const.SCROLL_KEY_SPEED)
        if KeyCode == 317:
            # down key
            self.img_panel.pan_down(const.SCROLL_KEY_SPEED)

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
    def on_mark_toggle(self, evt):
        self.img_panel.mark_mode = self.marktool.IsToggled()

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
        self.load_image_from_path(img_path)

    @debug_fxn
    def load_image_from_path(self, img_path):
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
        info.SetVersion(const.VERSION_STR)
        info.SetDescription("Counting cells in biological images.")
        info.SetCopyright("(C) 2017 Matthew A. Clapp")

        wx.adv.AboutBox(info)

    @debug_fxn
    def on_help(self, evt):
        """Open a brief help window (html)
        """
        self.html = HelpFrame(self, id=wx.ID_ANY)
        self.html.Show(True)


class HelpFrame(wx.Frame):
    """
    """
    def __init__(self, *args, **kwargs):
        """Constructor"""
        super().__init__(*args, **kwargs)
        # TODO: consider using wx.html2.WebView if we want to make Help look
        #   nicer than crummy html4 (e.g. being able to use CSS)
        self.html = wx.html.HtmlWindow(self)
        self.html.SetRelatedFrame(self, "%s")
        self.html.LoadPage(os.path.join(ICON_DIR, 'cellcounter_help.html'))
        self.SetSize((400, 600))


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
    parser.add_argument('srcfiles', nargs='*',
            help="Source files to open on startup."
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
    main_win = MainWindow(args.srcfiles, None)
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
