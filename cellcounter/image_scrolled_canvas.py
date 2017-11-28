#!/usr/bin/env python3

import time
import wx
import numpy as np
import const
from const import (
        DEBUG, DEBUG_FXN_ENTRY, DEBUG_KEYPRESS, DEBUG_TIMING, DEBUG_MISC
        )


def debugmsg(debug_bit, *args, **kwargs):
    if DEBUG & debug_bit:
        print(*args, **kwargs)


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


# really a Scrolled Window
class ImageScrolledCanvas(wx.ScrolledCanvas):
    """Window (in the wx sense) widget that displays an image, zooms in and
    out, and allows scrolling/panning in up/down and side/side if image is
    big enough.  If image is smaller than window it is auto-centered
    """
    @debug_fxn
    def __init__(self, parent, app_history, marks_num_update_fxn,
            id_=wx.ID_ANY, *args, **kwargs):
        super().__init__(parent, id_, *args, **kwargs)

        # init all properties to None (cause error if accessed before
        #   proper init)
        self.content_saved = True
        self.history = app_history
        self.img_at_wincenter_x = 0
        self.img_at_wincenter_y = 0
        self.img_coord_xlation_x = None
        self.img_coord_xlation_y = None
        self.img_dc = None
        self.img_dc_div2 = None
        self.img_dc_div4 = None
        self.img_size_x = 0
        self.img_size_y = 0
        self.is_dragging = False
        self.mark_mode = False
        self.mouse_left_down = None
        self.parent = parent    # TODO: do we need this?
        self.marks = []
        self.marks_num_update_fxn = marks_num_update_fxn
        self.marks_selected = []
        self.overlay = wx.Overlay() # for making rubber-band box during drag
        self.rubberband_draw_rect = None
        self.rubberband_refresh_rect = None
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

        # setup handlers
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_SCROLLWIN, self.on_scroll)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right_down)
        self.Bind(wx.EVT_MOTION, self.on_motion)

        # tell parent UI new total marks number (0)
        self.update_mark_total()

        # force a paint event with Refresh and Update
        # Refresh Invalidates the window
        self.Refresh()
        # Update immediately repaints invalidated areas
        #   without this, repainting will happen next iteration of event loop
        self.Update()

    @debug_fxn
    def set_no_image(self):
        self.content_saved = True
        self.history.reset()
        self.img_at_wincenter_x = 0
        self.img_at_wincenter_y = 0
        self.img_coord_xlation_x = None
        self.img_coord_xlation_y = None
        self.img_dc = None
        self.img_dc_div2 = None
        self.img_dc_div4 = None
        self.img_size_x = 0
        self.img_size_y = 0
        self.marks = []
        self.marks_selected = []

        # set zoom_idx to 1.00 scaling
        self.zoom_idx = self.zoom_list.index(1.0)
        self.zoom = self.zoom_list[self.zoom_idx]

        # make sure canvas is no larger than window
        self.set_virt_size_with_min()

        # tell parent UI new total marks number
        self.update_mark_total()

        # force a paint event with Refresh and Update
        # Refresh Invalidates the window
        self.Refresh()
        # Update immediately repaints invalidated areas
        #   without this, repainting will happen next iteration of event loop
        self.Update()

    @debug_fxn
    def needs_save(self):
        # poll self and children to determine if we need to save document
        return not self.content_saved

    @debug_fxn
    def save_notify(self):
        # tell self and children data was saved now
        self.content_saved = True

    @debug_fxn
    def get_img_wincenter(self):
        # find client size (visible image)
        (win_size_x, win_size_y) = self.GetClientSize()

        # translate client center to zoomed image center coords
        (self.img_at_wincenter_x, self.img_at_wincenter_y
                ) = self.win2img_coord(win_size_x/2, win_size_y/2)

        debugmsg(DEBUG_MISC,
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
        debugmsg(DEBUG_MISC,
            "MSC:img_zoom_wincenter = " + \
            "(%.3f,%.3f)\n"%(img_zoom_wincenter_x, img_zoom_wincenter_y) + \
            "MSC:origin = (%.3f,%.3f)\n"%(origin_x, origin_y) + \
            "MSC:Scroll to (%d,%d)"%(scroll_x, scroll_y)
            )

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

        debugmsg(DEBUG_MISC,
            "MSC:wincenter img limits (%.2f,%.2f) to (%.2f,%.2f)"%(
                img_x_min, img_y_min, img_x_max, img_y_max)
            )

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

        mods = evt.GetModifiers()

        # point coordinate returned seems:
        #   * be only absolute coordinates of where in window was clicked
        #       (unscrolled)
        #   * not to depend on which img_dc we supply
        #   * not to depend on zoom or pan
        # with self.img_dc, GetPosition == GetLogicalPosition (???)
        # NOTE: GetLogicalPosition doesn't seem to return anything different
        #       than GetPosition -- we are not getting unscrolled coords
        point = evt.GetPosition()
        point_unscroll = self.CalcUnscrolledPosition(point.x, point.y)
        (img_x, img_y) = self.win2img_coord(point.x, point.y)

        debugmsg(DEBUG_MISC,
            "MSC:left down at img (%.2f, %.2f)"%(img_x, img_y)
            )
        debugmsg(DEBUG_MISC,
            "MSC:evt.GetPosition = (%.2f, %.2f)"%(point.x, point.y)
            )

        if self.mark_mode:
            if (0 <= img_x <= self.img_size_x and
                    0 <= img_y <= self.img_size_y):
                img_pt = (int(img_x), int(img_y))
                mark_added = self.mark_point(img_pt)
                if mark_added:
                    self.history.new(['MARK',img_pt])
                else:
                    self.history.new(['NOP'])
        else:
            # we allow click outside of image in case we drag onto image

            # in case we need a drag capture mouse
            self.CaptureMouse()

            # selecting with no mark nearby deselects all
            # find the closest mark to click, as long as it is close
            #   enough to click
            # then color mark yellow and that one will be "selected"
            #   and can be deleted
            # Shift always adds select, CONTROL toggles select state
            is_appending = mods & wx.MOD_SHIFT
            is_toggling = mods & wx.MOD_CONTROL
            # record args so on on_left_up can select at point if this
            #   turns out to be a click and not a drag
            self.mouse_left_down = {
                    'point':point,
                    'point_unscroll':point_unscroll,
                    'img_x':img_x,
                    'img_y':img_y,
                    'is_appending':is_appending,
                    'is_toggling':is_toggling,
                    }
            #self.select_at_point(img_x, img_y, is_appending, is_toggling)

        # continue processing click, for example shifting focus to app
        evt.Skip()

    @debug_fxn
    def on_motion(self, evt):
        # return early if no image or if in Mark Mode
        #   (Mark mode does everything in on_left_down, no drags)
        if self.img_dc is None or self.mark_mode == True:
            wx.CallAfter(evt.Skip)
            return

        if evt.Dragging() and evt.LeftIsDown():
            evt_pos = evt.GetPosition()
            evt_pos_unscroll = self.CalcUnscrolledPosition(evt_pos.x, evt_pos.y)

            try:
                refresh_rect = wx.Rect(
                        topLeft=self.mouse_left_down['point'],
                        bottomRight=evt_pos
                        )
                draw_rect = wx.Rect(
                        topLeft=wx.Point(*self.mouse_left_down['point_unscroll']),
                        bottomRight=wx.Point(*evt_pos_unscroll)
                        )
            except TypeError as exc:
                # topLeft = NoneType. Attempting to double click image or something
                # DEBUG DELETEME
                #print("Drag but TypeError: returning")
                return
            except Exception as exc:
                raise exc

            # NOTE: Yosemite VM always says a click is a drag.  Does non-VM?
            # only set self.is_dragging flag if draw_rect is ever not (1,1)
            #   (1,1) means start point and end point the same (i.e. click)
            # Once set, only on_left_up can unset self.is_dragging
            if draw_rect.GetSize() != (1, 1):
                self.is_dragging = True
            else:
                pass
                # DEBUG DELETEME
                #print("Drag with (1,1) size")
            
            # make copy of rects, inflate by 1 pixel in each dir, union
            #   inflate by same width as rubberband rect Pen width
            refresh_rect.Inflate(1,1)

            last_draw_rect = self.rubberband_draw_rect
            self.rubberband_draw_rect = draw_rect
            last_refresh_rect = self.rubberband_refresh_rect
            self.rubberband_refresh_rect = refresh_rect

            # union of this and last refresh_rect
            if last_refresh_rect is not None:
                refresh_rect.Union(last_refresh_rect)

            self.RefreshRect(refresh_rect)
            self.Update()

    @debug_fxn
    def marks_in_box_img(self, box_corner1_img, box_corner2_img):
        (xmin, xmax) = sorted((box_corner1_img[0], box_corner2_img[0]))
        (ymin, ymax) = sorted((box_corner1_img[1], box_corner2_img[1]))

        marks_in_box = []
        for (x,y) in self.marks:
            if xmin <= x <= xmax and ymin <= y <= ymax:
                marks_in_box.append((x,y))

        return marks_in_box    

    @debug_fxn
    def on_left_up(self, evt):
        # return early if no image or if in Mark Mode
        #   (Mark mode does everything in on_left_down, no drags)
        if self.img_dc is None or self.mark_mode == True:
            wx.CallAfter(evt.Skip)
            return

        if self.is_dragging:
            # make copy of rubberband_rect and inflate by 1 pixel in each dir
            #   inflate by same width as rubberband rect Pen width
            refresh_rect = self.rubberband_refresh_rect
            self.RefreshRect(refresh_rect)
            self.Update()

            # finish drag by selecting everything in box
            box_corner1_win = self.mouse_left_down['point']
            box_corner2_win = evt.GetPosition()

            box_corner1_img = (
                    self.mouse_left_down['img_x'],
                    self.mouse_left_down['img_y']
                    )
            box_corner2_img = self.win2img_coord(box_corner2_win.x, box_corner2_win.y)

            marks_in_box = self.marks_in_box_img(box_corner1_img, box_corner2_img)

            # get key modifiers for this left_up event
            mods = evt.GetModifiers()
            is_appending = mods & wx.MOD_SHIFT

            if not is_appending:
                marks_unselected = [
                        x for x in self.marks_selected if x not in marks_in_box]
                marks_new_selected = [
                        x for x in marks_in_box if x not in self.marks_selected]
                self.marks_selected = marks_in_box
                for mark in marks_new_selected + marks_unselected:
                    self.refresh_mark_area(mark)
            else:
                for mark in marks_in_box:
                    if mark not in self.marks_selected:
                        self.marks_selected.append(mark)
                        self.refresh_mark_area(mark)
            self.Update()
        else:
            # finish click by selecting at point with args from on_left_down
            if (0 <= self.mouse_left_down['img_x'] <= self.img_size_x and
                    0 <= self.mouse_left_down['img_y'] <= self.img_size_y):
                self.select_at_point(
                        self.mouse_left_down['img_x'],
                        self.mouse_left_down['img_y'],
                        self.mouse_left_down['is_appending'],
                        self.mouse_left_down['is_toggling'],
                        )

        # reset all drag info
        self.mouse_left_down = None
        self.is_dragging = False
        self.rubberband_refresh_rect = None
        self.rubberband_draw_rect = None

        if self.HasCapture():
            self.ReleaseMouse()

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

        debugmsg(DEBUG_MISC,
                "MSC:right click at img (%.2f, %.2f)"%(img_x, img_y)
                )

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

        debugmsg(DEBUG_MISC,
            "MSC:panimate: start=(%.2f,%.2f) "%(img_x_start,img_y_start) + \
            "end=(%.2f, %.2f)"%(img_x_end, img_y_end)
            )

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
    def refresh_mark_area(self, mark_pt):
        # force a paint event with Refresh and Update
        #   to force paint_rect to paint new selected cross
        (pos_x, pos_y) = self.img2win_coord(mark_pt[0] + 0.5, mark_pt[1] + 0.5)
        # refresh square size should be >= than cross size
        sq_size = const.CROSS_REFRESH_SQ_SIZE
        self.RefreshRect(
                wx.Rect(
                    pos_x - sq_size/2, pos_y - sq_size/2,
                    sq_size, sq_size
                    )
                )

    @debug_fxn
    def mark_point(self, img_point, internal=False):
        """Mark image coordinates with cross in window

        Args:
            img_point (tuple): int (x, y) in image coordinates mark location

        Returns (bool): True if new mark added, False if same point already
            exists in mark list
        """
        debugmsg(DEBUG_MISC, "MSC: point (%d, %d)"%img_point)

        if img_point in self.marks:
            # mark already exists, doing nothing
            return False

        self.marks.append(img_point)
        # signal to parent that a new unsaved state has happened
        self.content_saved = False

        self.refresh_mark_area(img_point)

        if not internal:
            # tell parent UI new total marks number
            self.update_mark_total()
            self.Update()
        return True

    @debug_fxn
    def mark_point_list(self, point_list):
        for point in point_list:
            self.mark_point(point, internal=True)
        self.update_mark_total()
        self.Update()

    @debug_fxn
    def deselect_mark(self, desel_pt, internal=False):
        self.marks_selected.remove(desel_pt)
        self.refresh_mark_area(desel_pt)
        if not internal:
            self.Update()

    @debug_fxn
    def deselect_all_marks(self):
        marks_selected = self.marks_selected.copy()
        for mark_pt in marks_selected:
            self.deselect_mark(mark_pt, internal=True)
        self.marks_selected = []
        self.Update()

    @debug_fxn
    def delete_mark(self, mark_pt, internal=False):
        self.marks.remove(mark_pt)
        # deleted mark may or may not be selected
        try:
            self.marks_selected.remove(mark_pt)
        except ValueError:
            pass
        self.refresh_mark_area(mark_pt)
        # signal to parent that a new unsaved state has happened
        self.content_saved = False
        if not internal:
            # tell parent UI new total marks number
            self.update_mark_total()
            self.Update()

    @debug_fxn
    def delete_mark_point_list(self, point_list):
        for point in point_list:
            self.delete_mark(point, internal=True)
        # tell parent UI new total marks number
        self.update_mark_total()
        self.Update()

    @debug_fxn
    def delete_selected_marks(self):
        # make list copy
        # so deleting from self.marks_selected doesn't corrupt this operation
        # also so we have list later on for history
        marks_selected = self.marks_selected.copy()
        self.delete_mark_point_list(marks_selected)
        # return marks_deleted
        return marks_selected 

    @debug_fxn
    def update_mark_total(self):
        # tell parent UI new total marks number
        if self.marks_num_update_fxn is not None:
            self.marks_num_update_fxn(len(self.marks))

    @debug_fxn
    def select_at_point(self, click_img_x, click_img_y, is_appending, is_toggling=False):
        # how close can click to a mark to say we clicked on it
        prox_img = const.PROXIMITY_PX / self.zoom
        poss_points = []
        for (x,y) in self.marks:
            # check if pt is in a 2*prox_img x 2*prox_img box centered
            #   around click
            dist = np.sqrt(
                    (click_img_x - (x + 0.5))**2 + (click_img_y - (y + 0.5))**2
                    )
            if dist < prox_img:
                poss_points.append((x, y, dist))
        # if we're near at least one point, find the closest point to the click
        if poss_points:
            poss_points.sort(key=lambda pt: pt[2])
            sel_pt = poss_points[0][0:2]

            # click: select only this mark (deselect all others)
            # shift-click: add this mark select to prev selects
            # control-click: toggle this mark select
            if is_appending:
                # append mark to selected mark
                self.marks_selected.append(sel_pt)
            elif is_toggling:
                # toggle selection status of mark
                if sel_pt in self.marks_selected:
                    self.deselect_mark(sel_pt)
                else:
                    self.marks_selected.append(sel_pt)
            else:
                # deselect all currently selected marks,
                # select this mark
                self.deselect_all_marks()
                self.marks_selected = [sel_pt,]

            self.refresh_mark_area(sel_pt)
            self.Update()
        else:
            if not is_appending and not is_toggling:
                # not selecting any point deselects all points
                self.deselect_all_marks()

    @debug_fxn
    def select_all_marks(self):
        marks_unselected = [x for x in self.marks if x not in self.marks_selected]
        # copy all marks into marks_selected
        self.marks_selected = self.marks.copy()
        # set all unselected marks for refresh to allow color change
        for mark in marks_unselected:
            self.refresh_mark_area(mark)
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

    @debug_fxn
    def on_size(self, evt):
        self.set_virt_size_with_min()

        # scroll so center of image at same point it used to be
        self.scroll_to_img_at_wincenter()

    # GetClientSize is size of window graphics not including scrollbars
    # GetSize is size of window including scrollbars
    @debug_fxn
    def on_paint(self, evt):
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
            self.paint_rect(dc, rect)
            upd.Next()

        if DEBUG & DEBUG_TIMING:
            onpaint_eltime = time.time() - start_onpaint
            panel_size = self.GetSize()
            print(
                    "TIM:on_paint: %.3fs, zoom = %.3f, panel_size=(%d,%d)"%(
                        onpaint_eltime,
                        self.zoom,
                        panel_size.x, panel_size.y,
                        )
                    )

    @debug_fxn
    def paint_rect(self, dc, rect):
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
        debugmsg(DEBUG_MISC,
                "MSC:src_pos=(%.2f,%.2f)\t"%(src_pos_x,src_pos_y) + \
                "src_size=(%.2f,%.2f)\n"%(src_size_x,src_size_y) + \
                "    dest_pos=(%.2f,%.2f)\t"%(dest_pos_x,dest_pos_y) + \
                "dest_size=(%.2f,%.2f)\n"%(dest_size_x,dest_size_y) + \
                "    rect_pos=(%.2f,%.2f)\t"%(rect_pos_log_x,rect_pos_log_y) + \
                "rect_size=(%.2f,%.2f)"%(rect_size_x,rect_size_y)
                )

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
        # expand by const.CROSS_REFRESH_SQ_SIZE/2 in each dir to repaint
        #   portion of mark even if center of mark is not in region
        sq_size = const.CROSS_REFRESH_SQ_SIZE
        self.draw_crosses(
                dc,
                (src_pos_x - sq_size/2)*scale_dc, (src_pos_y - sq_size/2)*scale_dc,
                (src_size_x + sq_size)*scale_dc, (src_size_y + sq_size)*scale_dc)

        if self.is_dragging:
            self.draw_rubberband_box(dc)

    @debug_fxn
    def draw_rubberband_box(self, dc):
        # Set the pen, for the box's border
        # Mac Native selecting on background:
        #   white at 56.8% opacity (255, 255, 255, 145)
        dc.SetPen(
                wx.Pen(
                    colour=wx.Colour(0xff,0xff,0xff,145),
                     width=1,
                     style=wx.SOLID
                     )
                )
        # Create a brush (for the box's interior) with the same colour,
        # but 50% transparency.
        # Mac Native selecting on background:
        #   white at 14.5% opacity (255, 255, 255, 37)
        dc.SetBrush(
                wx.Brush(
                    colour=wx.Colour(0xff,0xff,0xff,37),
                    style=wx.BRUSHSTYLE_SOLID
                    )
                )
        dc.DrawRectangle(self.rubberband_draw_rect)

    @debug_fxn
    def draw_crosses(self, dc, src_pos_x, src_pos_y, src_size_x, src_size_y):
        pts_in_box = []
        marks_unselected = [x for x in self.marks if x not in self.marks_selected]
        for (x, y) in marks_unselected:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                (x_win, y_win) = self.img2logical_coord(x + 0.5, y + 0.5)
                if (x_win, y_win) not in pts_in_box:
                    # only draw bitmap if this is not a duplicate
                    pts_in_box.append((x_win, y_win))
                    # NOTE: if you change the size of this bmp, also change
                    #   the RefreshRect size const.CROSS_REFRESH_SQ_SIZE
                    dc.DrawBitmap(const.CROSS_11x11_RED_BMP, x_win - 6, y_win - 6)

        pts_in_box = []
        for (x, y) in self.marks_selected:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                (x_win, y_win) = self.img2logical_coord(x + 0.5, y + 0.5)
                if (x_win, y_win) not in pts_in_box:
                    # only draw bitmap if this is not a duplicate
                    pts_in_box.append((x_win, y_win))
                    # NOTE: if you change the size of this bmp, also change
                    #   the RefreshRect size const.CROSS_REFRESH_SQ_SIZE
                    dc.DrawBitmap(const.CROSS_11x11_YELLOW_BMP, x_win - 6, y_win - 6)

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
    def init_image(self, img):
        """Load and initialize image given its full path

        Args:
            img (wx.Image): wx Image to display in window
        """
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
            print("TIM:Create MemoryDCs: %.3fs"%staticdc_eltime)

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


