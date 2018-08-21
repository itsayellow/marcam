"""Image viewing/manipulation workhorse widget.
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

import logging
import threading
import time

import wx
import numpy as np

import const
import common
from common import floor, ceil, clip
import image_proc

# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug, common.DEBUG_FXN_STATE)


(myImageProcDoneEvent, EVT_IMG_PROC_DONE) = wx.lib.newevent.NewEvent()


@debug_fxn
def find_nearest_rational(input_num, possible_nums, possible_denoms):
    """Find nearest rational number to input_num
    """
    nums_denoms = []
    for denom in possible_denoms:
        test_nums = np.array(possible_nums)/denom
        errors = np.abs(test_nums - np.array([input_num]*len(possible_nums)))
        num = possible_nums[np.argmin(errors)]
        nums_denoms.append((num, denom))

    test_nums = np.array([x[0]/x[1] for x in nums_denoms])
    errors = np.abs(test_nums - np.array([input_num]*len(possible_denoms)))
    i = np.argmin(errors)
    (num, denom) = nums_denoms[i]
    zoom = test_nums[i]
    error = errors[i]

    # cast numpy.uint16 to plain ints
    return (zoom, int(num), int(denom), error)

@debug_fxn
def find_low_rational(input_num, possible_nums, possible_denoms, error_tol):
    """Find rational number close to input_num with lowest (num, denom) within
    error tolerance.
    """
    # make sure numerators and denominators are in ascending order
    possible_nums = np.array(possible_nums, dtype='uint16')
    possible_denoms = np.array(possible_denoms, dtype='uint16')
    possible_nums.sort()
    possible_denoms.sort()

    test_nums = np.tile(possible_nums, len(possible_denoms))
    test_denoms = np.tile(possible_denoms, (len(possible_nums), 1)).flatten('F')
    error_ratios = np.abs(test_nums/test_denoms - input_num)/input_num

    # first ok index is lowest numerator, denominator
    ok_index = np.min(np.where(error_ratios < error_tol))
    num = test_nums[ok_index]
    denom = test_denoms[ok_index]
    zoom = num/denom
    error = error_ratios[ok_index]

    # cast numpy.uint16 to plain ints
    return (zoom, int(num), int(denom), error)


@debug_fxn
def create_rational_zooms(mag_step, total_mag_steps, error_tol):
    """Create list of zoom ratios representable by rational numbers

    In the future once we settle on coefficients we like, this can
    be hard-coded instead of a function.

    Args:
        mag_step (float): Ratio of adjacent zoom ratios
        total_mag_steps (int): Total magnification steps from min to max
            (centered on 1.0).  Should be an odd number.
        error_tol (float): maximum multiplicative error that rational zoom
            can be off from ideal_zoom

    Returns:
        tuple: (zoom_list (list of floats), zoom_frac_list (list of tuples))
    """
    # mag_step puts a hard limit on error_tol, to ensure monotonicity of zoom
    if (mag_step - 1) < error_tol:
        raise Exception("Internal Error in create_rational_zooms: Please " \
                "make sure that eror_tol < (mag_step - 1)")

    if mag_step == 1.1 and total_mag_steps == 69 and error_tol == 0.011:
        # as long as coefficients are typical, use precomputed values
        zoom_frac_list = [
                (3, 76), (4, 92), (3, 64), (4, 76), (3, 52), (1, 16), (5, 72),
                (4, 52), (1, 12), (7, 76), (9, 88), (4, 36), (18, 148), (6, 44),
                (3, 20), (11, 68), (5, 28), (4, 20), (7, 32), (18, 76), (9, 34),
                (7, 24), (7, 22), (7, 20), (7, 18), (6, 14), (12, 26), (14, 27),
                (9, 16), (5, 8), (11, 16), (3, 4), (5, 6), (9, 10), (1, 1),
                (10, 9), (6, 5), (4, 3), (16, 11), (8, 5), (16, 9), (27, 14),
                (13, 6), (7, 3), (13, 5), (17, 6), (19, 6), (24, 7), (19, 5),
                (21, 5), (23, 5), (5, 1), (11, 2), (37, 6), (20, 3), (22, 3),
                (41, 5), (9, 1), (39, 4), (43, 4), (12, 1), (13, 1), (29, 2),
                (16, 1), (35, 2), (19, 1), (21, 1), (23, 1), (51, 2)
                ]
        zoom_list = [x[0]/x[1] for x in zoom_frac_list]
        return (zoom_list, zoom_frac_list)
    else:
        # let us know we are not as fast as we could be
        print("WARNING: NOT USING PRECOMPUTED ZOOM RATIOS.")
        LOGGER.warning("NOT USING PRECOMPUTED ZOOM RATIOS.")

    # hard code this, rely on error_tol for tweaking
    max_num_denom = 64

    # num: pixels in dest (window)
    # denom: pixels in src (image)
    # if 0.25 < zoom_ideal < 0.5:
    #   denom must be divisible by 2
    # if        zoom_ideal < 0.25:
    #   denom must be divisible by 4
    mag_len_half = int(total_mag_steps/2)

    # possible magnification list
    zoom_list_ideal = [
            mag_step**x
            for x in range(-mag_len_half, mag_len_half+1)
            ]
    # set this to 1.0 by hand to make sure no floating-point shenanigans
    #   might make it not exactly 1.0
    zoom_list_ideal[mag_len_half] = 1.0

    #errors = []
    zoom_list = []
    zoom_frac_list = []
    possible_nums = range(1, max_num_denom, 1)
    for zoom_ideal in zoom_list_ideal:
        # constraints due to scale_dc
        if zoom_ideal > 0.5:
            # normal denominators
            possible_denoms = range(1, max_num_denom + 1, 1)
        elif zoom_ideal > 0.25:
            # denominators must be divis. by 2 because img_dc_div2
            possible_denoms = range(2, 2*max_num_denom + 1, 2)
        else:
            # denominators must be divis. by 4 because img_dc_div4
            possible_denoms = range(4, 4*max_num_denom + 1, 4)

        (zoom, num, denom, error) = find_low_rational(
                zoom_ideal,
                possible_nums,
                possible_denoms,
                error_tol
                )
        #errors.append(error)
        zoom_list.append(zoom)
        zoom_frac_list.append((num, denom))

    #perc_errors = np.array(errors)*100
    #print(zoom_frac_list)
    #print("zoom max. perc error: %.2f%%"%np.max(perc_errors))

    # DEBUG DELETEME
    print("mag_step = ")
    print(mag_step)
    print("total_mag_steps = ")
    print(total_mag_steps)
    print("error_tol = ")
    print(error_tol)
    print("zoom_list = ")
    print(zoom_list)
    print("zoom_frac_list = ")
    print(zoom_frac_list)

    return (zoom_list, zoom_frac_list)


class RealPoint(wx.RealPoint):
    """A version of wx.RealPoint that allows multiplication by float
    """
    def __mul__(self, other):
        return RealPoint(self.x * other, self.y * other)
    def __repr__(self):
        return "RealPoint(" + repr(self.x) + ", " + repr(self.y) + ")"


# really a Scrolled Window
class ImageScrolledCanvas(wx.ScrolledCanvas):
    """Window (in the wx sense) widget that displays an image, zooms in and
    out, and allows scrolling/panning in up/down and side/side if image is
    big enough.  If image is smaller than window it is auto-centered
    """
    @debug_fxn
    def __init__(self, parent, win_history, id_=wx.ID_ANY, *args, **kwargs):
        super().__init__(parent, id_, *args, **kwargs)

        # init all properties to None (cause error if accessed before
        #   proper init)
        self.history = win_history
        self.img_at_wincenter = RealPoint(0, 0)
        self.img_coord_xlation = None
        self.img = None
        self.img_idx = None
        self.img_dc = None
        self.img_dc_div2 = None
        self.img_dc_div4 = None
        self.img_size_x = 0
        self.img_size_y = 0
        self.is_dragging = False
        self.mouse_left_down = None
        self.parent = parent # for drop target opening of files
        self.overlay = wx.Overlay() # for making rubber-band box during drag
        self.rubberband_draw_rect = None
        self.rubberband_refresh_rect = None
        self.zoom_frac_list = None
        self.zoom_idx = None
        self.zoom_list = None
        self.zoom_val = None
        self.paint_times = None

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

        # create zoom ratios of rational numbers (fractions)
        (self.zoom_list, self.zoom_frac_list) = create_rational_zooms(
                const.MAG_STEP,
                const.TOTAL_MAG_STEPS,
                const.ZOOM_MAX_ERROR_TOL
                )
        # set zoom_idx to 1.00 scaling
        self.zoom_idx = int(const.TOTAL_MAG_STEPS/2)
        self.zoom_val = self.zoom_list[self.zoom_idx]

        # setup handlers
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_SCROLLWIN, self.on_scroll)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right_down)
        self.Bind(wx.EVT_MOTION, self.on_motion)

        # force a paint event with Refresh and Update
        # Refresh Invalidates the window
        self.Refresh()
        # Update immediately repaints invalidated areas
        #   without this, repainting will happen next iteration of event loop
        self.Update()

    @debug_fxn
    def SetVirtualSizeNoSizeEvt(self, *args, **kwargs):
        """No-Size-Event version of wx.Window.SetVirtualSize

        Same as wx.WindowSetVirtualSize, except we disable Size Events
        So we don't keep cyclically enter set_virt_size_with_min
        """
        # NOTE: Apparently changing the VirtualSize of the window in
        #           set_virt_size_with_min() triggers
        #           EVT_SIZE, triggering on_size, triggering
        #           set_virt_size_with_min().
        #       To prevent such cyclical entering of that function, every
        #           time we change the Virtual Size, we disable event
        #           EVT_SIZE.

        # wrap SetVirtualSize in wx.EventBlocker to block size events
        block_size_event = wx.EventBlocker(self, type=wx.wxEVT_SIZE)
        self.SetVirtualSize(*args, **kwargs)
        del block_size_event


    @debug_fxn
    def set_no_image(self, refresh_update=True):
        """Reset image display area and state, remove image

        Args:
            refresh_update (bool): default True.  Whether to Refresh() and
                Update() window area
        """
        self.history.reset()
        self.img_at_wincenter = RealPoint(0, 0)
        self.img_coord_xlation = None
        self.img = None
        self.img_idx = None
        self.img_dc = None
        self.img_dc_div2 = None
        self.img_dc_div4 = None
        self.img_size_x = 0
        self.img_size_y = 0

        # set zoom_idx to 1.00 scaling
        self.zoom_idx = self.zoom_list.index(1.0)
        self.zoom_val = self.zoom_list[self.zoom_idx]

        # make sure canvas is no larger than window
        self.set_virt_size_with_min()

        # if we are using this in an inherited class method via super, option to
        #   refresh and update only in inherited method (not here)
        if refresh_update:
            # force a paint event with Refresh and Update
            # Refresh Invalidates the window
            self.Refresh()
            # Update immediately repaints invalidated areas
            #   without this, repainting will happen next iteration of event loop
            self.Update()

    @debug_fxn_debug
    def has_no_image(self):
        return self.img_dc is None

    @debug_fxn
    def get_img_wincenter(self):
        """Set this scroll position as internally-saved scroll location

        Affects:
            self.img_at_wincenter
        """
        # GetClientSize is size of window graphics not including scrollbars
        # GetSize is size of window including scrollbars

        # use GetSize not GetClientSize, so presence or absence of scrollbars
        #   doesn't affect image location in window
        (win_size_x, win_size_y) = self.GetSize()

        # translate client center to zoomed image center coords
        (img_at_wincenter_x, img_at_wincenter_y
                ) = self.win2img_coord(wx.Point(win_size_x/2, win_size_y/2))
        self.img_at_wincenter = RealPoint(img_at_wincenter_x, img_at_wincenter_y)

        LOGGER.info(
                "MSC:self.img_at_wincenter=(%.3f,%.3f)",
                self.img_at_wincenter.x,
                self.img_at_wincenter.y
                )

    @debug_fxn
    def get_scroll_zoom_state(self):
        """Fetch current state of image position / zoom

        Returns:
            list: scroll_zoom_state - (scroll_coords, zoom_index)
        """
        return (
                self.img_at_wincenter,
                self.zoom_idx
                )

    @debug_fxn
    def set_scroll_zoom_state(self, scroll_zoom_state):
        """Set current state of image position / zoom

        Args:
            scroll_zoom_state (tuple): (scroll_coords, zoom_idx)
        """
        self.img_at_wincenter = scroll_zoom_state[0]
        # zoom() will scroll to self.img_at_wincenter_{x,y} after zoom
        self.zoom(scroll_zoom_state[1] - self.zoom_idx)

    @debug_fxn
    def scroll_to_img_at_wincenter(self):
        """Scroll window so center of window is at intern. saved scroll location
        self.img_at_wincenter
        """
        # use GetSize not GetClientSize, so presence or absence of scrollbars
        #   doesn't affect image location in window
        (win_size_x, win_size_y) = self.GetSize()
        (scroll_ppu_x, scroll_ppu_y) = self.GetScrollPixelsPerUnit()

        img_zoom_wincenter = self.img_at_wincenter * self.zoom_val
        origin = img_zoom_wincenter - RealPoint(win_size_x/2, win_size_y/2)

        scroll_x = round(origin.x/scroll_ppu_x)
        scroll_y = round(origin.y/scroll_ppu_y)
        self.Scroll(scroll_x, scroll_y)
        LOGGER.debug(
                "MSC:img_zoom_wincenter = (%.3f,%.3f)\nMSC:origin = " \
                        "(%.3f,%.3f)\nMSC:Scroll to (%d,%d)",
                img_zoom_wincenter.x, img_zoom_wincenter.y,
                origin.x, origin.y,
                scroll_x, scroll_y
                )

    def wincenter_scroll_limits(self):
        """
        get min, max coordinates that can lie in center of window

        Returns:
            tuple: (img_x_min, img_y_min, img_x_max, img_y_max)
        """
        # GetClientSize returns physical window dimensions, not unscrolled
        (win_size_x, win_size_y) = self.GetClientSize()
        win_size_img_x = win_size_x / self.zoom_val
        win_size_img_y = win_size_y / self.zoom_val

        if win_size_img_x > self.img_size_x:
            img_x_min = self.img_size_x / 2
            img_x_max = self.img_size_x / 2
        else:
            img_x_min = win_size_x / 2 / self.zoom_val
            img_x_max = self.img_size_x - (win_size_x / 2 / self.zoom_val)

        if win_size_img_y > self.img_size_y:
            img_y_min = self.img_size_y / 2
            img_y_max = self.img_size_y / 2
        else:
            img_y_min = win_size_y / 2 / self.zoom_val
            img_y_max = self.img_size_y - (win_size_y / 2 / self.zoom_val)

        LOGGER.info(
                "MSC:wincenter img limits (%.2f,%.2f) to (%.2f,%.2f)",
                img_x_min, img_y_min, img_x_max, img_y_max
                )

        return (img_x_min, img_y_min, img_x_max, img_y_max)

    @debug_fxn
    def on_left_down(self, evt):
        """EVT_LEFT_DOWN handler: mouse left-clicks

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image
        if self.has_no_image():
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
        point_unscroll = self.CalcUnscrolledPosition(point)
        (img_x, img_y) = self.win2img_coord(point)

        LOGGER.info(
                "MSC:left down at img (%.2f, %.2f)"%(img_x, img_y) + "\n" + \
                " "*4 + "MSC:evt.GetPosition = (%.2f, %.2f)"%(point.x, point.y)
                )

        # we allow click outside of image in case we drag onto image

        # in case we need a drag capture mouse
        self.CaptureMouse()

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

        # continue processing click, for example shifting focus to app
        evt.Skip()

    # don't debug on_motion normally, too much log msgs
    #@debug_fxn
    def on_motion(self, evt):
        """EVT_MOTION handler: "mouse moving".  Used esp. to track dragging

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image
        if self.has_no_image():
            wx.CallAfter(evt.Skip)
            return

        if evt.Dragging() and evt.LeftIsDown():
            evt_pos = evt.GetPosition()
            evt_pos_unscroll = self.CalcUnscrolledPosition(evt_pos)

            try:
                refresh_rect = wx.Rect(
                        topLeft=self.mouse_left_down['point'],
                        bottomRight=evt_pos
                        )
                draw_rect = wx.Rect(
                        topLeft=self.mouse_left_down['point_unscroll'],
                        bottomRight=evt_pos_unscroll
                        )
            except TypeError as exc:
                # topLeft = NoneType. Attempting to double click image or something
                # DEBUG DELETEME
                #LOGGER.warning("Drag but TypeError: returning")
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
                return

            # make copy of rects, inflate by 1 pixel in each dir, union
            #   inflate by same width as rubberband rect Pen width
            refresh_rect.Inflate(1, 1)

            self.rubberband_draw_rect = draw_rect
            last_refresh_rect = self.rubberband_refresh_rect
            self.rubberband_refresh_rect = refresh_rect

            # union of this and last refresh_rect
            if last_refresh_rect is not None:
                refresh_rect.Union(last_refresh_rect)

            self.RefreshRect(refresh_rect)
            self.Update()

    @debug_fxn
    def on_left_up(self, evt):
        """EVT_LEFT_UP handler: "mouse button up".  Used esp. to stop dragging

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image
        if self.has_no_image():
            wx.CallAfter(evt.Skip)
            return

        if self.is_dragging:
            # use last rubberband_refresh_rect
            refresh_rect = self.rubberband_refresh_rect
            self.RefreshRect(refresh_rect)
            # reset all drag info so update doesn't add back drag rectangle
            self.is_dragging = False
            self.rubberband_refresh_rect = None
            self.rubberband_draw_rect = None

            # finish drag by selecting everything in box
            # In this function the following code does nothing, so commented out
            #box_corner2_win = evt.GetPosition()
            #box_corner1_img = (
            #        self.mouse_left_down['img_x'],
            #        self.mouse_left_down['img_y']
            #        )
            #box_corner2_img = self.win2img_coord(box_corner2_win.x, box_corner2_win.y)

            self.Update()
        else:
            # finish click
            pass

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
        """EVT_RIGHT_DOWN handler: mouse right-clicks

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image
        if self.has_no_image():
            wx.CallAfter(evt.Skip)
            return

        # point coordinate returned seems:
        #   * be only absolute coordinates of where in window was clicked
        #   * not to depend on which img_dc we supply
        #   * not to depend on zoom or pan
        point = evt.GetLogicalPosition(self.img_dc)
        (img_x, img_y) = self.win2img_coord(point)

        LOGGER.info(
                "MSC:right click at img (%.2f, %.2f)",
                img_x, img_y
                )

        #self.img_at_wincenter = RealPoint(img_x, img_y)
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
        img_max_speed = max_speed / self.zoom_val

        (xmin, ymin, xmax, ymax) = self.wincenter_scroll_limits()

        # clip values for end coordinates to max zoom area
        img_x_end = clip(img_x_end, xmin, xmax)
        img_y_end = clip(img_y_end, ymin, ymax)

        img_x_start = self.img_at_wincenter.x
        img_y_start = self.img_at_wincenter.y

        # if we're not moving then just return
        if img_x_end == img_x_start and img_y_end == img_y_start:
            return

        LOGGER.info(
                "MSC:panimate: start=(%.2f,%.2f) "%(img_x_start, img_y_start) + \
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
        """One step of a panimate pan animation

        Args:
            x_vals (list): future x_vals in pan-animation
            y_vals (list): future y_vals in pan-animation
            last_time (time.time()): last time panimate_step was executed
        """
        # check if time since last panimate step is multiple steps
        #   and skip ahead if so
        pop_num = int((time.time()-last_time)/(const.PANIMATE_STEP_MS*1e-3))
        # 1 <= pop_num <= len(x_vals)
        pop_num = clip(pop_num, 1, len(x_vals))
        for _ in range(pop_num):
            self.img_at_wincenter = RealPoint(x_vals.pop(0), y_vals.pop(0))
        self.scroll_to_img_at_wincenter()
        if x_vals:
            wx.CallLater(
                    const.PANIMATE_STEP_MS,
                    self.panimate_step, x_vals, y_vals, time.time()
                    )
        else:
            wx.CallAfter(self.get_img_wincenter)

    @debug_fxn
    def on_scroll(self, evt):
        """EVT_SCROLLWIN handler: scrolling events

        Args:
            evt (wx.ScrollWinEvent): obj returned from scrolled window event
        """
        # return early if no image
        if self.has_no_image():
            wx.CallAfter(evt.Skip)
            return

        event_type = evt.GetEventType()
        orientation = evt.GetOrientation()
        if LOGGER.isEnabledFor(logging.DEBUG):
            log_string = "MSC:"
            if orientation == wx.HORIZONTAL:
                log_string += " wx.HORIZONTAL"
            elif orientation == wx.VERTICAL:
                log_string += " wx.VERTICAL"
            else:
                log_string += " orientation="+repr(orientation)

            if event_type == wx.wxEVT_SCROLLWIN_TOP:
                log_string += " wx.wxEVT_SCROLLWIN_TOP"
            elif event_type == wx.wxEVT_SCROLLWIN_BOTTOM:
                log_string += " wx.wxEVT_SCROLLWIN_BOTTOM"
            elif event_type == wx.wxEVT_SCROLLWIN_LINEUP:
                log_string += " wx.wxEVT_SCROLLWIN_LINEUP"
            elif event_type == wx.wxEVT_SCROLLWIN_LINEDOWN:
                log_string += " wx.wxEVT_SCROLLWIN_LINEDOWN"
            elif event_type == wx.wxEVT_SCROLLWIN_PAGEUP:
                log_string += " wx.wxEVT_SCROLLWIN_PAGEUP"
            elif event_type == wx.wxEVT_SCROLLWIN_PAGEDOWN:
                log_string += " wx.wxEVT_SCROLLWIN_PAGEDOWN"
            elif event_type == wx.wxEVT_SCROLLWIN_THUMBTRACK:
                log_string += " wx.wxEVT_SCROLLWIN_THUMBTRACK"
            elif event_type == wx.wxEVT_SCROLLWIN_THUMBRELEASE:
                log_string += " wx.wxEVT_SCROLLWIN_THUMBRELEASE"
            else:
                log_string += " event_type="+repr(event_type)
            LOGGER.info(log_string)

        # NOTE: by setting position only on scroll (and not on zoom) we
        #   preserve position on zoom out/zoom back in even if the image gets
        #   temporarily centered during zoom out.  That way when we zoom back
        #   in, we will find the same position again unless we scroll.

        # set a position check for after this event is processed (after moved)
        #   useful in case event handled by default handler with evt.Skip()
        wx.CallAfter(self.get_img_wincenter)

        if orientation == wx.HORIZONTAL and event_type == wx.wxEVT_SCROLLWIN_LINEUP:
            self.pan_right(-const.SCROLL_WHEEL_SPEED)
        elif orientation == wx.HORIZONTAL and event_type == wx.wxEVT_SCROLLWIN_LINEDOWN:
            self.pan_right(const.SCROLL_WHEEL_SPEED)
        elif orientation == wx.VERTICAL and event_type == wx.wxEVT_SCROLLWIN_LINEUP:
            self.pan_down(-const.SCROLL_WHEEL_SPEED)
        elif orientation == wx.VERTICAL and event_type == wx.wxEVT_SCROLLWIN_LINEDOWN:
            self.pan_down(const.SCROLL_WHEEL_SPEED)
        else:
            # process with default handler(s)
            evt.Skip()

    @debug_fxn
    def _debug_paint_client_area(self):
        # DEBUG: Make whole background red for debug (allows us to see
        #   what parts are not getting subsequently repainted)
        (size_x, size_y) = self.GetSize()
        self.SetVirtualSizeNoSizeEvt(size_x, size_y)
        client_dc = wx.ClientDC(self)
        client_dc.SetPen(
                wx.Pen(colour=wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT)
                )
        client_dc.SetBrush(
                wx.Brush(
                    colour=wx.Colour(0, 255, 0),
                    style=wx.BRUSHSTYLE_SOLID
                    )
                )
        client_dc.DrawRectangle(0, 0, size_x, size_y)

    @debug_fxn
    def _erase_lowerright_corner(self, skip_virt_size=False):
        # Can't get ScreenDC to draw to screen, so to erase the
        #   lower right corner between scrollbars, resize virtual area
        #   to window size and draw to ClientDC
        # Color lower right corner of client area background color, to erase it

        # TODO: at init time find width of scrollbar and make that the
        #   edge size of this square.  Can find width of scrollbar by
        #   enlarging virtual area huge, then measure difference in
        #   self.GetSize() and self.GetClientSize()
        edge_width = 20

        (size_x, size_y) = self.GetSize()
        if not skip_virt_size:
            # if we currently have scrollbars, we need to resize virtual size
            #   to size of window so we can draw into lower right corner
            self.SetVirtualSizeNoSizeEvt(size_x, size_y)

        # init Client DC
        client_dc = wx.ClientDC(self)
        # invisible pen
        client_dc.SetPen(
                wx.Pen(colour=wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT)
                )
        # background-colored brush for area
        client_dc.SetBrush(
                wx.Brush(
                    colour=self.GetBackgroundColour(),
                    style=wx.BRUSHSTYLE_SOLID
                    )
                )
        # draw square in lower-right corner with edge size edge_width
        client_dc.DrawRectangle(
                size_x-edge_width, size_y-edge_width,
                edge_width, edge_width
                )

    @debug_fxn
    def set_virt_size_and_pos(self):
        # Freeze before changing virtual size and moving image
        #   so we don't see window jittering with updates
        self.Freeze()

        # expand virtual window size
        self.set_virt_size_with_min()

        # scroll so center of image at same point it used to be
        if self.GetSize() != self.GetClientSize():
            # only scroll if we have at least one scrollbar
            self.scroll_to_img_at_wincenter()

        # Now Thaw after changing virtual size and moving image
        self.Thaw()

    @debug_fxn
    def set_virt_size_with_min(self):
        """Set size of unscrolled canvas for image_size, making virtual size
        same as image if image is zoomed larger than window, or as large as
        window if image is smaller than window in order to be able to center
        image in window.

        Uses instance variables:
            self.img_size_x
            self.img_size_y
            self.zoom_val

        Affects instance variables:
            self.img_coord_xlation
        """

        # Paint entire client area red to debug possible repaint problems.
        #   (Can see red if we're not repainting over something.)
        #pylint: disable=using-constant-test
        if False:
            self._debug_paint_client_area()
        #pylint: enable=using-constant-test

        # Don't allow the window to update anything while we do a ton of
        #   playing around with the Virtual Size and scrolling to move to
        #   center.
        self.Freeze()
        LOGGER.debug("Freeze()")

        # NICE: self.GetSize() always returns maximum size of client area
        #           as it would be sized without scrollbars.
        # NICE: self.GetRect() always returns maximum size of client area
        #           as it would be sized without scrollbars.
        #       Seems to always have position at (0,0), but width, height are
        #           good.
        # USELESS: self.GetMaxClientSize() always = (-1,-1)
        # USELESS: self.GetMaxSize() always = (-1,-1)

        # Max size of client (without scrollbars)
        win_size = self.GetSize()
        # original Client Size before changing virt size
        orig_client_size = self.GetClientSize()
        # Boolean whether originally we have no scrollbars
        orig_has_no_scrollbars = win_size == orig_client_size
        # NOTE: do not depend on self.HasScrollbar, because it can be updated
        #   immediately on resize even when orig_client_size == win_size
        #   showing no scrollbar width
        orig_x_scrolled = win_size.GetWidth() != orig_client_size.GetWidth()
        orig_y_scrolled = win_size.GetHeight() != orig_client_size.GetHeight()

        # compute necessary virtual size, either win_size or bigger if needed
        #virt_size = wx.Size(
        #        max(self.img_size_x * self.zoom_val, win_size.GetWidth()),
        #        max(self.img_size_y * self.zoom_val, win_size.GetHeight())
        #        )

        # TODO: if one of these is True, the other might be incorrect
        #       (need to compare not to win_size, but win_size - scroll width)
        x_scrolled = self.img_size_x * self.zoom_val > win_size.GetWidth()
        y_scrolled = self.img_size_y * self.zoom_val > win_size.GetHeight()
        #only_one_scrolled = x_scrolled != y_scrolled
        both_or_none_scrolled = x_scrolled == y_scrolled

        if both_or_none_scrolled:
            virt_size = wx.Size(
                    max(self.img_size_x * self.zoom_val, win_size.GetWidth()),
                    max(self.img_size_y * self.zoom_val, win_size.GetHeight())
                    )
            # erase corner only needs to set virt size before erasing client
            #   area if we currently have scrollbars
            skip_virt_size = orig_has_no_scrollbars
        else:
            # only one of x_scrolled, y_scrolled is true (xor)

            # compute necessary virtual size, either client_size or bigger if needed
            virt_size = wx.Size(
                    max(self.img_size_x * self.zoom_val, orig_client_size.GetWidth()),
                    max(self.img_size_y * self.zoom_val, orig_client_size.GetHeight())
                    )
            # No need to recompute virt size:
            #   if orig_x_scrolled to x_scrolled only
            #       (then y client size stays the same)
            #   or if orig_y_scrolled to y_scrolled only
            #       (then x client size stays the same)
            #   and we use client_size for max in virt_size above
            if (x_scrolled and not orig_x_scrolled) or (y_scrolled and not orig_y_scrolled):
                # set new virtual size
                self.SetVirtualSizeNoSizeEvt(virt_size)
                # re-compute virtual size with new client size,
                #   because one scrollbar will affect Client Size of one dimension
                new_client_size = self.GetClientSize()
                virt_size = wx.Size(
                        max(self.img_size_x * self.zoom_val, new_client_size.GetWidth()),
                        max(self.img_size_y * self.zoom_val, new_client_size.GetHeight())
                        )
            # We have at least one scroll bar now, so erase corner needs to
            #   set virt size before erasing client area
            skip_virt_size = False

        # erase the corner between scroll bars
        #   NOTE: only need to do this on mac, and if window has
        #       self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        if const.PLATFORM == 'mac':
            # strictly speaking, this should be x_scrolled and y_scrolled,
            #   but to predict if the following SetVirtualSize will make both
            #   scrollbars, we'd need to know scrollbar width
            if x_scrolled or y_scrolled:
                # only need to erase if corner is inaccessible to client
                self._erase_lowerright_corner(skip_virt_size=skip_virt_size)
        # set new virtual size
        self.SetVirtualSizeNoSizeEvt(virt_size)

        # center image if Virtual Size is larger than image

        # center in window, not client area, so presence/absence of scrollbar
        #   doesn't affect placement
        if win_size.GetWidth() > self.img_size_x * self.zoom_val:
            img_coord_xlation_x = int(
                    (win_size.GetWidth() - self.img_size_x * self.zoom_val) / 2
                    )
        else:
            img_coord_xlation_x = 0

        if win_size.GetHeight() > self.img_size_y * self.zoom_val:
            img_coord_xlation_y = int(
                    (win_size.GetHeight() - self.img_size_y * self.zoom_val) / 2
                    )
        else:
            img_coord_xlation_y = 0
        self.img_coord_xlation = wx.Point(img_coord_xlation_x, img_coord_xlation_y)

        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom, divide by div_scale to get to img coordinates

        # Finally, allow drawing of window again
        self.Thaw()
        LOGGER.debug("Thaw()")

    @debug_fxn
    def on_size(self, _evt):
        """EVT_SIZE handler: resizing window

        Args:
            _evt (wx.ScrollWinEvent): obj returned from scrolled window event
        """
        # set new virtual window size and scroll position based on new window
        #   size
        self.set_virt_size_and_pos()

        # TODO: on Windows we need a Refresh/Update cycle as well,
        #   should we skip on Mac (and possibly unix?)
        # force a paint event with Refresh
        self.Refresh()
        #self.Update() # Update not necessary on Windows

    # GetClientSize is size of window graphics not including scrollbars
    # GetSize is size of window including scrollbars
    @debug_fxn
    def on_paint(self, _evt):
        """EVT_PAINT handler: update window area

        Args:
            _evt (wx.PaintEvent): no useful information
        """
        if LOGGER.isEnabledFor(logging.DEBUG):
            start_onpaint = time.time()

        # use BufferedPaintDC or AutoBufferedPaintDC instead of PaintDC
        #   to try and avoid flicker in systems without double-buffered DC.
        #   (also style=wx.BUFFER_VIRTUAL_AREA ?)
        # TODO: still helpful? on which platforms?
        # TODO: currently (7/27/2018) using AutoBufferedPaintDC makes
        #   our drag rubberband box fail.
        #   Possibly related to wx.GraphicsContext ??
        #paint_dc = wx.AutoBufferedPaintDC(self)

        # Since AutoBufferedPaintDC isn't working for us, do it manually
        if const.PLATFORM == 'mac':
            paint_dc = wx.PaintDC(self)
        else:
            paint_dc = wx.BufferedPaintDC(self)

        # for scrolled window
        self.DoPrepareDC(paint_dc)

        # get the update rect list
        upd = wx.RegionIterator(self.GetUpdateRegion())

        while upd.HaveRects():
            rect = upd.GetRect()
            # Repaint this rectangle
            self.paint_rect(paint_dc, rect)
            upd.Next()

        if LOGGER.isEnabledFor(logging.DEBUG):
            onpaint_eltime = time.time() - start_onpaint
            panel_size = self.GetSize()
            LOGGER.info(
                    "TIM:on_paint: %.3fs, zoom = %.3f, panel_size=(%d,%d)",
                    onpaint_eltime,
                    self.zoom_val,
                    panel_size.x, panel_size.y,
                    )
            if self.paint_times is not None:
                zoom_str = "%.3f"%self.zoom_val
                self.paint_times.setdefault(zoom_str, []).append(onpaint_eltime)


    @debug_fxn
    def _get_margin_rects(self, rect_pos_log, rect_size, dest_pos, dest_size):
        """Given a EVT_PAINT rectangle, if image is smaller than rect return
        background rectangles to paint.

        Args:
            rect_pos_log (wx.Point): position of EVT_PAINT rectangle
            rect_size (wx.Size): size of EVT_PAINT rectangle
            dest_pos (wx.Point): position of image in window
            dest_size (wx.Size): size of image in window
        """
        # useful local variables (lower-right corner coords)
        rect_lr_log = rect_pos_log + rect_size
        dest_lr = dest_pos + dest_size

        # paint bg rectangles around border if necessary
        left_gap = clip(dest_pos.x - rect_pos_log.x, 0, None)
        right_gap = clip(rect_lr_log.x - dest_lr.x, 0, None)
        top_gap = clip(dest_pos.y - rect_pos_log.y, 0, None)
        bottom_gap = clip(rect_lr_log.y - dest_lr.y, 0, None)

        rects_to_draw = []
        if top_gap > 0:
            rects_to_draw.append(
                    (rect_pos_log.x, rect_pos_log.y, rect_size.x, top_gap)
                    )
        if bottom_gap > 0:
            rects_to_draw.append(
                    (rect_pos_log.x, dest_lr.y, rect_size.x, bottom_gap)
                    )
        # for left_gap, right_gap y-size, import to use dest_size.y,
        #   NOT rect_size.y - top_gap - bottom_gap
        # dest_size is padded to account for the fact that dest_pos is
        #   made slightly smaller to make sure it is on a pixel boundary
        # if you don't use dest_size.y here, rect_size.y value will be not
        #   quite large enough to account for the slightly
        #   too small dest_pos.y
        # The above can happen if the image is taller than the window
        #   but not wider than the window.
        # Also, dest_size.y is exactly the height of the image if we have
        #   top_gap and bottom_gap
        if left_gap > 0:
            rects_to_draw.append(
                    (rect_pos_log.x, dest_pos.y, left_gap, dest_size.y)
                    )
        if right_gap > 0:
            rects_to_draw.append(
                    (dest_lr.x, dest_pos.y, right_gap, dest_size.y)
                    )
        return rects_to_draw

    @debug_fxn
    def _rect_to_srcdest(self, rect_point_logical, scale_dc, use_floor=True):
        # INPUT: rect_pos_log, scale_dc, self

        #zoom = dest_win_size/src_img_size
        (z_numer, z_denom) = self.zoom_frac_list[self.zoom_idx]

        # quantize destination positions AFTER subtracting self.img_coord_xlation
        #   then add self.img_coord_xlation back
        (x, y) = rect_point_logical.GetIM()
        # get untranslated x,y
        x = x - self.img_coord_xlation.x
        y = y - self.img_coord_xlation.y
        # quantize x,y, rounding down or up
        if use_floor:
            x = floor(x / z_numer) * z_numer
            y = floor(y / z_numer) * z_numer
        else:
            x = ceil(x / z_numer) * z_numer
            y = ceil(y / z_numer) * z_numer
        assert int(x) == x
        assert int(y) == y
        rect_pos_quant_destcoord = wx.Point(x, y)

        # img coordinates of upper left corner
        blit_src_pos_x = rect_pos_quant_destcoord.x * z_denom / z_numer / scale_dc
        blit_src_pos_y = rect_pos_quant_destcoord.y * z_denom / z_numer / scale_dc
        assert int(blit_src_pos_x) == blit_src_pos_x
        assert int(blit_src_pos_y) == blit_src_pos_y

        # make int and enforce min. val of 0, max val of (img_size + quant)
        blit_src_pos_x = clip(
                round(blit_src_pos_x),
                0, ceil(self.img_size_x / z_denom) * z_denom / scale_dc
                )
        blit_src_pos_y = clip(
                round(blit_src_pos_y),
                0, ceil(self.img_size_y / z_denom) * z_denom / scale_dc
                )
        assert int(blit_src_pos_x) == blit_src_pos_x
        assert int(blit_src_pos_y) == blit_src_pos_y
        blit_src_pos = wx.Point(blit_src_pos_x, blit_src_pos_y)

        # multiply pos back out to get slightly off-window but
        #   on src-pixel-boundary coords for dest
        # dest coordinates are all logical
        blit_dest_pos_x = blit_src_pos_x * z_numer * scale_dc / z_denom + self.img_coord_xlation.x
        blit_dest_pos_y = blit_src_pos_y * z_numer * scale_dc / z_denom + self.img_coord_xlation.y
        assert int(blit_dest_pos_x) == blit_dest_pos_x
        assert int(blit_dest_pos_y) == blit_dest_pos_y
        blit_dest_pos = wx.Point(round(blit_dest_pos_x), round(blit_dest_pos_y))
        #blit_dest_pos = self.img2logical_coord(
        #        blit_src_pos_x, blit_src_pos_y, scale_dc=scale_dc
        #       )

        return (blit_dest_pos, blit_src_pos)

    @debug_fxn
    def _get_rect_coords(self, rect):
        """Get all useful coordinates for a paint event given EVT_PAINT rect

        Args:
            rect (wx.Rect): rectangle being refreshed for EVT_PAINT event

        Returns:
            tuple: contains the following in order:
                stretch_blit_args (tuple): All args to be sent to wx.StretchBlit
                    blit_dest_pos.x (int): x pos of img region in dest window
                    blit_dest_pos.y (int): y pos of img region in dest window
                    blit_dest_size.x (int): x size of region in dest window
                    blit_dest_size.y (int): y size of region in dest window
                    img_dc_src (wx.MemoryDC): which scaled DC we use for src img
                    blit_src_pos.x (int): x pos of region in img src
                    blit_src_pos.y (int): y pos of region in img src
                    blit_src_size.x (int): x size of region in img src
                    blit_src_size.y (int): y size of region in img src
                rect_pos_log (wx.Point): logical paint rect position
                rect_size (wx.Size): paint rect size
                blit_src_pos (wx.Point): pos of region in img src
                blit_src_size (wx.Size): size of region in img src
                scale_dc (int): which scale we are using src img
                actual_dest_pos (wx.Point): exact pos of image in logical
                    coordinates with no quantization
                actual_dest_size (wx.Size): exact size of image in logical
                    coordinates with no quantization
        """
        # break out rect details into variables
        rect_pos = rect.GetPosition()
        rect_size = rect.GetSize()

        # see if we need to use a downscaled version of memdc
        if self.zoom_val > 0.5:
            img_dc_src = self.img_dc
            scale_dc = 1
        elif self.zoom_val > 0.25:
            img_dc_src = self.img_dc_div2
            scale_dc = 2
        else:
            img_dc_src = self.img_dc_div4
            scale_dc = 4

        # rect_pos_{x,y} is upper left corner
        # rect_lr_{x,y} is lower right corner
        rect_lr = rect_pos + rect_size

        rect_pos_log = self.CalcUnscrolledPosition(rect_pos)
        rect_lr_log = self.CalcUnscrolledPosition(rect_lr)

        # from logical upper-left rect point, compute upper-left
        #   in both src and dest blit coordinates
        (blit_dest_pos, blit_src_pos) = self._rect_to_srcdest(
                rect_pos_log, scale_dc, use_floor=True
                )

        # from logical lower-right rect point, compute upper-left
        #   in both src and dest blit coordinates
        (dest_lr_pos, src_lr_pos) = self._rect_to_srcdest(
                rect_lr_log, scale_dc, use_floor=False
                )

        # compute blit src size (zoom patch quantized)
        blit_src_size = wx.Size(
                src_lr_pos.x - blit_src_pos.x,
                src_lr_pos.y - blit_src_pos.y
                )
        # compute blit dest size (zoom patch quantized)
        blit_dest_size = wx.Size(
                dest_lr_pos.x - blit_dest_pos.x,
                dest_lr_pos.y - blit_dest_pos.y
                )
        # compute actual dest size by taking upper-left and lower-right
        #   positions of refresh rect and clipping them to img dest position
        actual_dest_pos = wx.Point(
                clip(
                    rect_pos_log.x,
                    self.img_coord_xlation.x,
                    self.img_coord_xlation.x + self.img_size_x * self.zoom_val
                    ),
                clip(
                    rect_pos_log.y,
                    self.img_coord_xlation.y,
                    self.img_coord_xlation.y + self.img_size_y * self.zoom_val
                    )
                )
        actual_dest_lr = wx.Point(
                clip(
                    rect_lr_log.x,
                    self.img_coord_xlation.x,
                    self.img_coord_xlation.x + self.img_size_x * self.zoom_val
                    ),
                clip(
                    rect_lr_log.y,
                    self.img_coord_xlation.y,
                    self.img_coord_xlation.y + self.img_size_y * self.zoom_val
                    )
                )
        actual_dest_size = actual_dest_lr - actual_dest_pos

        # Bundle all of the StretchBlit arguments into one tuple so that it can
        #   be just passed with an asterisk * expansion directly to StretchBlit
        stretch_blit_args = (
                blit_dest_pos.x, blit_dest_pos.y,
                blit_dest_size.x, blit_dest_size.y,
                img_dc_src,
                blit_src_pos.x, blit_src_pos.y,
                blit_src_size.x, blit_src_size.y,
                )
        return (
                stretch_blit_args,
                rect_pos_log, rect_size,
                blit_src_pos, blit_src_size,
                scale_dc,
                actual_dest_pos, actual_dest_size
                )

    @debug_fxn
    def paint_rect(self, paintdc, rect):
        """Given a rect needing a refresh in window PaintDC, Blit the image
        to fill that rect.

        Args:
            paintdc (wx.PaintDC): Device Context to Blit into
            rect (tuple): coordinates to refresh (window coordinates)
        """
        # if no image, fill area with background color
        if self.has_no_image():
            paintdc.SetPen(wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT))
            paintdc.SetBrush(paintdc.GetBackground())
            paintdc.DrawRectangle(rect)
            # DONE
            return

        # get coords and choose scaled version of img_dc
        (
                stretch_blit_args,
                rect_pos_log, rect_size,
                _, _,
                _,
                actual_dest_pos, actual_dest_size
                ) = self._get_rect_coords(rect)

        # NOTE: Blit shows no performance advantage over StretchBlit (Mac)
        # NOTE: StretchBlit uses ints for both src and dest pixel dimensions.
        #   This means to center and zoom accurately (sub-src-pixel) we need to
        #   refresh an area that INCLUDES the region needed, NOT ONLY that
        #   dest region.  This way we can zoom and position accurately, while
        #   employing the clipping mask behavior of PaintDC to make sure we
        #   only display in the area of the window
        # copy region from self.img_dc into paintdc with possible stretching
        # TODO: clipping max to only blit to image area?
        paintdc.StretchBlit(*stretch_blit_args)

        # paint margins bg color if image is smaller than window
        rects_to_draw = self._get_margin_rects(
                rect_pos_log, rect_size,
                actual_dest_pos, actual_dest_size,
                )
        if rects_to_draw:
            paintdc.SetPen(wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT))
            # debug pen:
            #paintdc.SetPen(wx.Pen(wx.Colour(255, 0, 0), width=1, style=wx.SOLID))
            paintdc.SetBrush(paintdc.GetBackground())
            paintdc.DrawRectangleList(rects_to_draw)

        if self.is_dragging:
            self.draw_rubberband_box(paintdc)

    @debug_fxn
    def draw_rubberband_box(self, dc):
        """Draw rubberband box onto given DC to indicate dragging

        Args:
            dc (wx.DC): typically wx.PaintDC, DC on which to draw drag rect
        """
        # NOTE: GraphicsContext currently (7/27/2018) doesn't seem to work with
        #   AutoBufferedPaintDC
        graphics_dc = wx.GraphicsContext.Create(dc)

        if graphics_dc:
            if const.PLATFORM == 'win':
                # Windows 10 drag color
                #   \HKEY_CURRENT_USER\Control Panel\Colors\HotTrackingColor
                #   0 102 204
                pen_color = wx.Colour(0, 102, 204, 145)
                brush_color = wx.Colour(0, 102, 204, 37)
            elif const.PLATFORM == 'mac':
                # Mac Native pen selecting on background:
                #   white at 56.8% opacity (255, 255, 255, 145)
                # Mac Native brush selecting on background:
                #   white at 14.5% opacity (255, 255, 255, 37)
                pen_color = wx.Colour(0xff, 0xff, 0xff, 145)
                brush_color = wx.Colour(0xff, 0xff, 0xff, 37)
            else:
                pen_color = wx.Colour(0xff, 0xff, 0xff, 145)
                brush_color = wx.Colour(0xff, 0xff, 0xff, 37)

            # Set the pen, for the box's border
            graphics_dc.SetPen(
                    wx.Pen(colour=pen_color, width=1, style=wx.SOLID)
                    )
            # Create a brush (for the box's interior)
            graphics_dc.SetBrush(
                    wx.Brush(colour=brush_color, style=wx.BRUSHSTYLE_SOLID)
                    )
            # for some reason GraphicsContext.DrawRectangle will not accept
            #   wx.Rect as argument, so break out separate dimensions
            graphics_dc.DrawRectangle(
                    self.rubberband_draw_rect.x,
                    self.rubberband_draw_rect.y,
                    self.rubberband_draw_rect.width,
                    self.rubberband_draw_rect.height,
                    )

    @debug_fxn
    def win2img_coord(self, win_coord, scale_dc=1):
        """Given plain window coordinates, return image coordinates

        Args:
            win_coord (wx.Point): point in device (window) coordinates

        Returns:
            tuple: (img_x (float), img_y (float)) position in src image
                coordinates
        """
        # img_coord_xlation_{x,y} = 0 unless window is bigger than image
        #   in which case this is non-zero translation of left,top padding
        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom to get to img coordinates

        win_unscroll = self.CalcUnscrolledPosition(win_coord)

        img_x = (win_unscroll.x - self.img_coord_xlation.x) / self.zoom_val / scale_dc
        img_y = (win_unscroll.y - self.img_coord_xlation.y) / self.zoom_val / scale_dc

        return (img_x, img_y)

    @debug_fxn
    def logical2img_coord(self, logical_coord, scale_dc=1):
        """Given logical unscrolled canvas coordinates, return image coordinates

        Args:
            logical_coord (wx.Point): logical canvas (unscrolled) coordinates

        Returns:
            tuple: (img_x (float), img_y (float)) position in src image
                coordinates
        """
        (z_numer, z_denom) = self.zoom_frac_list[self.zoom_idx]

        # img_coord_xlation_{x,y} = 0 unless window is bigger than image
        #   in which case this is non-zero translation of left,top padding
        # self.img_coord_xlation_{x,y} is in window coordinates
        #   divide by zoom to get to img coordinates
        # TODO: remove these someday when we are confident
        assert isinstance(self.img_coord_xlation.x, int)
        assert isinstance(self.img_coord_xlation.y, int)
        assert isinstance(z_numer, int)
        assert isinstance(z_denom, int)
        assert isinstance(scale_dc, int)
        #img_x = (logical_coord.x - self.img_coord_xlation.x) / self.zoom_val / scale_dc
        #img_y = (logical_coord.y - self.img_coord_xlation.y) / self.zoom_val / scale_dc
        # TODO: use integer division when we are confident answer is always int
        img_x = (logical_coord.x - self.img_coord_xlation.x) * z_denom / z_numer / scale_dc
        img_y = (logical_coord.y - self.img_coord_xlation.y) * z_denom / z_numer / scale_dc
        # TODO: remove these someday when we are confident
        assert img_x == int(img_x)
        assert img_y == int(img_y)

        return (int(img_x), int(img_y))

    # this happens too many times, don't print to logs normally
    #@debug_fxn
    def img2logical_coord(self, img_x, img_y, scale_dc=1):
        """Given image coordinates, return logical unscrolled canvas coordinates

        Args:
            img_x (float): src image coordinates
            img_y (float): src image coordinates

        Returns:
            wx.Point: position in logical unscrolled canvas coordinates
        """
        win_unscroll_x = img_x * self.zoom_val * scale_dc + self.img_coord_xlation.x
        win_unscroll_y = img_y * self.zoom_val * scale_dc + self.img_coord_xlation.y

        return wx.Point(round(win_unscroll_x), round(win_unscroll_y))

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
        win_logical_x = img_x * self.zoom_val * scale_dc + self.img_coord_xlation.x
        win_logical_y = img_y * self.zoom_val * scale_dc + self.img_coord_xlation.y
        (win_x, win_y) = self.CalcScrolledPosition(win_logical_x, win_logical_y)
        return (win_x, win_y)

    @debug_fxn
    def get_current_img(self):
        return self.img[self.img_idx]

    @debug_fxn
    def new_img(self, img):
        self.img = [img]
        self.img_idx = 0

    @debug_fxn
    def set_img_idx(self, idx_set):
        self.img_idx = idx_set

    @debug_fxn
    def init_image(self, do_zoom_fit=True):
        """Load and initialize image

        Args:
            img (wx.Image): wx Image to display in window
        """
        if LOGGER.isEnabledFor(logging.DEBUG):
            staticdc_start = time.time()

        # before calling init_image, must call new_img, or set_img_idx
        #   so this is correct
        img = self.img[self.img_idx]

        self.img_size_y = img.GetHeight()
        self.img_size_x = img.GetWidth()

        # create wx.Bitmaps from wx.Image
        white_bg = img.HasAlpha()
        if white_bg:
            LOGGER.info("Image has an alpha channel")

        self.img_dc = image_proc.image2memorydc(
                img,
                white_bg=white_bg
                )
        self.img_dc_div2 = image_proc.image2memorydc(
                img.Scale(self.img_size_x/2, self.img_size_y/2),
                white_bg=white_bg
                )
        self.img_dc_div4 = image_proc.image2memorydc(
                img.Scale(self.img_size_x/4, self.img_size_y/4),
                white_bg=white_bg
                )

        if LOGGER.isEnabledFor(logging.DEBUG):
            staticdc_eltime = time.time() - staticdc_start
            LOGGER.info("TIM:Create MemoryDCs: %.3fs", staticdc_eltime)

        if do_zoom_fit:
            # set zoom_idx to scaling that will fit image in window
            #   (with 1.0x zoom maximum)
            self.zoom_fit(max_zoom=1.0, do_refresh=False)

        # force a paint event with Refresh and Update
        self.Refresh()
        self.Update()

    @debug_fxn
    def zoom_fit(self, max_zoom=None, do_refresh=True):
        # return early if no image
        if self.has_no_image():
            return None

        if max_zoom is None:
            # no max zoom, so set max_zoom to 10x biggest zoom possible
            max_zoom = self.zoom_list[-1]*10
        else:
            # max_zoom needs to be slightly bigger than desired final max zoom
            max_zoom += 0.000001

        # set zoom_idx to scaling that will fit image in window
        win_size = self.GetSize()
        max_fit_zoom = min(
                max_zoom,
                (win_size.x / self.img_size_x),
                (win_size.y / self.img_size_y)
                )
        ok_zooms = [x for x in self.zoom_list if x < max_fit_zoom]
        self.zoom_idx = self.zoom_list.index(max(ok_zooms))

        # record floating point zoom
        self.zoom_val = self.zoom_list[self.zoom_idx]

        # expand virtual window size
        self.set_virt_size_with_min()

        # set image center at window center
        self.img_at_wincenter = RealPoint(self.img_size_x/2, self.img_size_y/2)

        if do_refresh:
            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

        return self.zoom_val

    @debug_fxn
    def zoom_point(self, zoom_amt, win_coords=None, do_refresh=True):
        """Zoom in the image in this window (increase zoom ratio).  There
        is a fixed list of zoom ratios, move down in the list

        Args:
            zoom_amt (int): How many positions to move up or down in the
                zoom ratio list
            win_coords (wx.Point): point to center zoom around
            do_refresh (bool, default=True): whether to force a refresh now
                after changing the zoom ratio

        Returns:
            self.zoom_val (float): resulting zoom ratio (1.00 is 1x zoom)
        """
        # return early if no image or we can't zoom any more
        if self.has_no_image():
            return None
        if zoom_amt > 0 and self.zoom_idx == len(self.zoom_list)-1:
            return self.zoom_val
        if zoom_amt < 0 and self.zoom_idx == 0:
            return self.zoom_val

        # make sure self.img_at_wincenter_{x,y} is up to date
        self.get_img_wincenter()

        # translate mouse location from window coords to img coords
        #point_unscroll = self.CalcUnscrolledPosition(point.x, point.y)
        (img_x, img_y) = self.win2img_coord(win_coords)
        zoom_orig = self.zoom_val
        delta_x_orig = img_x - self.img_at_wincenter.x
        delta_y_orig = img_y - self.img_at_wincenter.y

        self.zoom_idx += zoom_amt

        # enforce max zoom
        if self.zoom_idx > len(self.zoom_list)-1:
            self.zoom_idx = len(self.zoom_list)-1
        # enforce min zoom
        if self.zoom_idx < 0:
            self.zoom_idx = 0

        # record floating point zoom
        self.zoom_val = self.zoom_list[self.zoom_idx]

        # set img centerpoint coords so img coords and win coords from mouse
        #   point are still the same
        delta_x_new = delta_x_orig * zoom_orig / self.zoom_val
        delta_y_new = delta_y_orig * zoom_orig / self.zoom_val
        self.img_at_wincenter = RealPoint(img_x - delta_x_new, img_y - delta_y_new)

        # set new virtual window size and scroll position based on new zoom and
        #   new position
        self.set_virt_size_and_pos()

        if do_refresh:
            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

        return self.zoom_val

    @debug_fxn
    def zoom(self, zoom_amt, do_refresh=True):
        """Zoom in the image in this window (increase zoom ratio).  There
        is a fixed list of zoom ratios, move down in the list

        Args:
            zoom_amt (int): How many positions to move up or down in the
                zoom ratio list
            do_refresh (bool, default=True): whether to force a refresh now
                after changing the zoom ratio

        Returns:
            self.zoom_val (float): resulting zoom ratio (1.00 is 1x zoom) or
                None, if no image
        """
        # return early if no image or we can't zoom any more
        if self.has_no_image():
            return None
        if zoom_amt > 0 and self.zoom_idx == len(self.zoom_list)-1:
            return self.zoom_val
        if zoom_amt < 0 and self.zoom_idx == 0:
            return self.zoom_val

        self.zoom_idx += zoom_amt

        # enforce max zoom
        if self.zoom_idx > len(self.zoom_list)-1:
            self.zoom_idx = len(self.zoom_list)-1
        # enforce min zoom
        if self.zoom_idx < 0:
            self.zoom_idx = 0

        # record floating point zoom
        self.zoom_val = self.zoom_list[self.zoom_idx]

        # set new virtual window size and scroll position based on new zoom
        self.set_virt_size_and_pos()

        if do_refresh:
            # force a paint event with Refresh and Update
            self.Refresh()
            self.Update()

        return self.zoom_val

    @debug_fxn
    def pan_down(self, pan_amt):
        """Scroll the current viewport so we see an area below

        Args:
            pan_amt (float): amount to pan in pixels of the image

        Returns:
            None
        """
        # return early if no image
        if self.has_no_image():
            return

        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_y = self.GetScrollPos(wx.VERTICAL)
        (_, scroll_ppu_y) = self.GetScrollPixelsPerUnit()
        if pan_amt > 0:
            scroll_amt = clip(round(pan_amt/scroll_ppu_y), 1, None)
        elif pan_amt < 0:
            scroll_amt = clip(round(pan_amt/scroll_ppu_y), None, -1)

        self.Scroll(wx.DefaultCoord, scroll_y + scroll_amt)
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
        if self.has_no_image():
            return

        # NOTE: we don't use SetScrollPos here because that requires a
        #   separate refresh.  It also doesn't? seem to make EVT_SCROLLWIN
        #   events either

        scroll_x = self.GetScrollPos(wx.HORIZONTAL)
        (scroll_ppu_x, _) = self.GetScrollPixelsPerUnit()
        if pan_amt > 0:
            scroll_amt = clip(round(pan_amt/scroll_ppu_x), 1, None)
        elif pan_amt < 0:
            scroll_amt = clip(round(pan_amt/scroll_ppu_x), None, -1)

        self.Scroll(scroll_x + scroll_amt, wx.DefaultCoord)
        # self.Scroll doesn't create an EVT_SCROLLWIN event, so we need to
        #   update wincenter position manually
        self.get_img_wincenter()

    @debug_fxn
    def export_to_image(self):
        dc_source = self.img_dc

        # based largely on code posted to wxpython-users by Andrea Gavana 2006-11-08
        size = dc_source.GetSize()

        # Create a Bitmap that will later on hold the screenshot image
        # Note that the Bitmap must have a size big enough to hold the screenshot
        # -1 means using the current default colour depth
        bmp = wx.Bitmap(size.width, size.height)

        # Create a memory DC that will be used for actually taking the screenshot
        #   use bmp as SelectObject
        # Tell the memory DC to use our Bitmap
        # all drawing action on the memory DC will go to the Bitmap now
        memDC = wx.MemoryDC(bmp)

        # Blit (in this case copy) the actual screen on the memory DC
        # and thus the Bitmap
        memDC.Blit(0, 0,    # dest position
            size.width, size.height, # src, dest size
            dc_source,      # From where do we copy?
            0, 0            # src position
            )

        # Select the Bitmap out of the memory DC by selecting a new
        # uninitialized Bitmap
        memDC.SelectObject(wx.NullBitmap)

        img = bmp.ConvertToImage()
        #img.SaveFile('saved.png', wx.BITMAP_TYPE_PNG)
        return img

    @debug_fxn
    def image_invert(self):
        # return early if no image
        if self.has_no_image():
            return

        # get current image
        wx_image_orig = self.img[self.img_idx]
        # create new image
        wx_image_new = image_proc.image_invert(wx_image_orig)
        # delete all items after current one in list
        self.img = self.img[:self.img_idx+1]
        # add new img to end of list
        self.img.append(wx_image_new)
        # update img pointer
        self.img_idx += 1
        # save previous image idx, and new image idx
        self.history.new(
                ['IMAGE_XFORM', self.img_idx - 1, self.img_idx],
                description="Invert Image"
                )
        self.init_image(do_zoom_fit=False)

    @debug_fxn
    def thread_image_remap_colormap(self, cmap):
        # create new image (3.7s for 4276x2676 image)
        self.wx_image_new = image_proc.image_remap_colormap(self.wx_image_orig, cmap=cmap)
        wx.PostEvent(self, myImageProcDoneEvent())

    @debug_fxn
    def finish_image_remap_colormap(self, evt):
        # Set Value to 100 (max) to auto-hide
        self.image_remap_dialog.Update(100)
        # On Windows especially, must Destroy progress dialog for application
        #   to continue
        self.image_remap_dialog.Destroy()
        start_time = time.time()
        # delete all items after current one in list
        self.img = self.img[:self.img_idx+1]
        # add new img to end of list
        self.img.append(self.wx_image_new)
        # update img pointer
        self.img_idx += 1
        # save previous image idx, and new image idx
        self.history.new(
                ['IMAGE_XFORM', self.img_idx - 1, self.img_idx],
                description="Image False Color"
                )
        print("3 before init image: %.1fms"%((time.time()-start_time)*1000))
        start_time = time.time()
        # put new image in window (188ms for 4276x2676)
        self.init_image(do_zoom_fit=False)
        print("4 init image: %.1fms"%((time.time()-start_time)*1000))
       
    def pulse_image_remap_dialog(self):
        if self.image_remap_dialog.GetValue() < 100:
            self.image_remap_dialog.Pulse()
            wx.CallLater(100, self.pulse_image_remap_dialog)
        else:
            pass
            #print("image_remap_dialog done (max value)")

    @debug_fxn
    def image_remap_colormap(self, cmap='viridis'):
        # return early if no image
        if self.has_no_image():
            return

        # DEBUG DELETEME
        start_time = time.time()
        # get current image
        self.wx_image_orig = self.img[self.img_idx]
        print("1 get current image: %.1fms"%((time.time()-start_time)*1000))

        imageproc_thread = threading.Thread(
                target=self.thread_image_remap_colormap,
                args=(cmap,),
                daemon=True,
                )
        imageproc_thread.start()
        self.Bind(EVT_IMG_PROC_DONE, self.finish_image_remap_colormap)
        self.image_remap_dialog = wx.ProgressDialog(
                "Processing Image.",
                "Applying False Color to image.",
                parent=self
                )
        wx.CallAfter(self.pulse_image_remap_dialog)
        
        #start_time = time.time()
        # create new image (3.7s for 4276x2676 image)
        #wx_image_new = image_proc.image_remap_colormap(wx_image_orig, cmap=cmap)
        #print("2 image_proc.remap: %.1fms"%((time.time()-start_time)*1000))
        #start_time = time.time()
        ## delete all items after current one in list
        #self.img = self.img[:self.img_idx+1]
        ## add new img to end of list
        #self.img.append(wx_image_new)
        ## update img pointer
        #self.img_idx += 1
        ## save previous image idx, and new image idx
        #self.history.new(
        #        ['IMAGE_XFORM', self.img_idx - 1, self.img_idx],
        #        description="Image False Color"
        #        )
        #print("3 before init image: %.1fms"%((time.time()-start_time)*1000))
        #start_time = time.time()
        ## put new image in window (188ms for 4276x2676)
        #self.init_image(do_zoom_fit=False)
        #print("4 init image: %.1fms"%((time.time()-start_time)*1000))

    @debug_fxn
    def image_autocontrast(self, cutoff=0):
        # return early if no image
        if self.has_no_image():
            return

        # get current image
        wx_image_orig = self.img[self.img_idx]
        # create new image
        wx_image_new = image_proc.image_autocontrast(wx_image_orig, cutoff=cutoff)
        # delete all items after current one in list
        self.img = self.img[:self.img_idx+1]
        # add new img to end of list
        self.img.append(wx_image_new)
        # update img pointer
        self.img_idx += 1
        # save previous image idx, and new image idx
        self.history.new(
                ['IMAGE_XFORM', self.img_idx - 1, self.img_idx],
                description="Image Auto-Contrast"
                )
        self.init_image(do_zoom_fit=False)

    @debug_fxn
    def get_image_info(self):
        # return early if no image
        if self.has_no_image():
            return None

        return image_proc.get_image_info(self.img_dc)


# really a Scrolled Window
class ImageScrolledCanvasMarks(ImageScrolledCanvas):
    """Window (in the wx sense) widget that displays an image, zooms in and
    out, and allows scrolling/panning in up/down and side/side if image is
    big enough.  If image is smaller than window it is auto-centered
    Also allow for setting, selecting, deleting, marks.
    """
    @debug_fxn
    def __init__(self, parent, win_history, marks_num_update_fxn,
            id_=wx.ID_ANY, *args, **kwargs):
        super().__init__(parent, win_history, id_, *args, **kwargs)

        # init all properties to None (cause error if accessed before
        #   proper init)
        self.mark_mode = False
        self.marks = []
        self.marks_num_update_fxn = marks_num_update_fxn
        self.marks_selected = []
        self.mark_dragging = None
        self.mark_dragging_is_sel = None

        # tell parent UI new total marks number (0)
        self._update_mark_total()

        # force a paint event with Refresh and Update
        # Refresh Invalidates the window
        self.Refresh()
        # Update immediately repaints invalidated areas
        #   without this, repainting will happen next iteration of event loop
        self.Update()

    @debug_fxn
    def set_no_image(self):
        """Reset image display area and state, remove image

        Args:
            refresh_update (bool): default True.  Whether to Refresh() and
                Update() window area
        """
        # execute all non-mark no-image init
        super().set_no_image(refresh_update=False)

        self.marks = []
        self.marks_selected = []

        # tell parent UI new total marks number
        self._update_mark_total()

        # force a paint event with Refresh and Update
        # Refresh Invalidates the window
        self.Refresh()
        # Update immediately repaints invalidated areas
        #   without this, repainting will happen next iteration of event loop
        self.Update()

    @debug_fxn
    def on_left_down(self, evt):
        """EVT_LEFT_DOWN handler: mouse left-clicks

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image
        if self.has_no_image():
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
        point_unscroll = self.CalcUnscrolledPosition(point)
        (img_x, img_y) = self.win2img_coord(point)

        LOGGER.info(
                "MSC:left down at img (%.2f, %.2f)"%(img_x, img_y) + "\n" + \
                " "*4 + "MSC:evt.GetPosition = (%.2f, %.2f)"%(point.x, point.y)
                )

        if self.mark_mode:
            if (0 <= img_x <= self.img_size_x and
                    0 <= img_y <= self.img_size_y):
                img_pt = (int(img_x), int(img_y))
                mark_added = self.mark_point(img_pt)
                if mark_added:
                    self.history.new(
                            ['MARK', img_pt],
                            description="Add Mark"
                            )
                else:
                    # TODO: IS THIS WRONG?  Should we delete this?
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

            # get mark location if this is click/drag on a mark
            sel_pt = self._mark_that_is_near_click(img_x, img_y)
            mark_pt_is_sel = sel_pt in self.marks_selected

            # record args so on on_left_up can select at point if this
            #   turns out to be a click and not a drag
            self.mouse_left_down = {
                    'point':point,
                    'point_unscroll':point_unscroll,
                    'img_x':img_x,
                    'img_y':img_y,
                    'is_appending':is_appending,
                    'is_toggling':is_toggling,
                    'mark_pt':sel_pt,
                    'mark_pt_is_sel':mark_pt_is_sel
                    }

        # continue processing click, for example shifting focus to app
        evt.Skip()

    # don't debug on_motion normally, too much log msgs
    #@debug_fxn
    def on_motion(self, evt):
        """EVT_MOTION handler: "mouse moving".  Used esp. to track dragging

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image or if in Mark Mode
        #   (Mark mode does everything in on_left_down, no drags)
        if self.has_no_image() or self.mark_mode:
            wx.CallAfter(evt.Skip)
            return

        if evt.Dragging() and evt.LeftIsDown():
            evt_pos = evt.GetPosition()
            evt_pos_unscroll = self.CalcUnscrolledPosition(evt_pos)

            if self.mouse_left_down['mark_pt'] is not None:
                # we are dragging a mark
                drag_rect = wx.Rect(
                        topLeft=self.mouse_left_down['point_unscroll'],
                        bottomRight=evt_pos_unscroll
                        )
                # NOTE: Yosemite VM always says a click is a drag.  Does non-VM?
                # only set self.is_dragging flag if draw_rect is ever not (1,1)
                #   (1,1) means start point and end point the same (i.e. click)
                # Once set, only on_left_up can unset self.is_dragging
                if drag_rect.GetSize() != (1, 1):
                    self.is_dragging = True
                else:
                    return
                # delete orig loc of dragged mark from normal list of marks
                #   at start of drag
                if self.mouse_left_down['mark_pt'] in self.marks:
                    self.delete_mark(self.mouse_left_down['mark_pt'], internal=True)
                    # update selection flag now that we know we're in drag
                    self.mark_dragging_is_sel = self.mouse_left_down['mark_pt_is_sel']
                    # set old mark location to mark_dragging
                    self.mark_dragging = self.mouse_left_down['mark_pt']
                # refresh old mark location
                self.refresh_mark_area(self.mark_dragging)
                # update dragged mark location
                (img_x, img_y) = self.win2img_coord(evt_pos)
                self.mark_dragging = (int(img_x), int(img_y))
                # refresh new mark location
                self.refresh_mark_area(self.mark_dragging)
            else:
                try:
                    # in case we have scrolled while dragging, recalculate
                    #   window position from original unscrolled position
                    point_devcoord = self.CalcScrolledPosition(
                            self.mouse_left_down['point_unscroll']
                            )
                    refresh_rect = wx.Rect(
                            topLeft=point_devcoord,
                            bottomRight=evt_pos
                            )
                    draw_rect = wx.Rect(
                            topLeft=self.mouse_left_down['point_unscroll'],
                            bottomRight=evt_pos_unscroll
                            )
                except TypeError as exc:
                    # topLeft = NoneType. Attempting to double click image or something
                    # DEBUG DELETEME
                    #LOGGER.warning("Drag but TypeError: returning")
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
                    return

                # make copy of rects, inflate by 1 pixel in each dir, union
                #   inflate by same width as rubberband rect Pen width
                refresh_rect.Inflate(1, 1)

                self.rubberband_draw_rect = draw_rect
                last_refresh_rect = self.rubberband_refresh_rect
                # get a COPY of refresh_rect, so self.rubberband_refresh_rect
                #   isn't still pointing to refresh_rect object, and
                #   isn't affected with Union below
                self.rubberband_refresh_rect = wx.Rect(refresh_rect.GetIM())

                # union of this and last refresh_rect
                if last_refresh_rect is not None:
                    refresh_rect.Union(last_refresh_rect)

                self.RefreshRect(refresh_rect)

            # update window for all rects needing refresh
            self.Update()

    @debug_fxn
    def marks_in_box_img(self, box_corner1_img, box_corner2_img):
        """Return list of coordinates of marks within denoted box (img coords)

        Args:
            box_corner1_img (tuple): one corner of region in img coords
            box_corner2_img (tuple): opposite corner of region in img coords

        Returns:
            list: list of (x,y) tuples of all marks within box region
                (img coordinates)
        """
        (xmin, xmax) = sorted((box_corner1_img[0], box_corner2_img[0]))
        (ymin, ymax) = sorted((box_corner1_img[1], box_corner2_img[1]))

        marks_in_box = []
        for (x, y) in self.marks:
            if xmin <= x <= xmax and ymin <= y <= ymax:
                marks_in_box.append((x, y))

        return marks_in_box

    @debug_fxn
    def on_left_up(self, evt):
        """EVT_LEFT_UP handler: "mouse button up".  Used esp. to stop dragging

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # return early if no image or if in Mark Mode
        #   (Mark mode does everything in on_left_down, no drags)
        if self.has_no_image() or self.mark_mode:
            wx.CallAfter(evt.Skip)
            return

        evt_pos = evt.GetPosition()
        if self.is_dragging:
            if self.rubberband_refresh_rect is not None:
                # use last rubberband_refresh_rect to refresh all marks
                #   in selection box, and selection box area (to erase
                #   rubber band box after resetting rubber_band vars)
                refresh_rect = self.rubberband_refresh_rect
                self.RefreshRect(refresh_rect)

                # finish drag by selecting everything in box
                box_corner1_img = (
                        self.mouse_left_down['img_x'],
                        self.mouse_left_down['img_y']
                        )
                box_corner2_img = self.win2img_coord(evt_pos)

                marks_in_box = self.marks_in_box_img(box_corner1_img, box_corner2_img)

                # get key modifiers for this left_up event
                mods = evt.GetModifiers()
                is_appending = mods & wx.MOD_SHIFT

                if not is_appending:
                    marks_unselected = [
                            x for x in self.marks_selected if x not in marks_in_box]
                    #marks_new_selected = [
                    #        x for x in marks_in_box if x not in self.marks_selected]
                    self.marks_selected = marks_in_box
                    # marks_new_selected already in refresh_rect box, so
                    #   no need to refresh them individually.
                    #   Just refresh mark areas outside of the rubber band box
                    for mark in marks_unselected:
                        self.refresh_mark_area(mark)
                else:
                    for mark in marks_in_box:
                        if mark not in self.marks_selected:
                            self.marks_selected.append(mark)
                            # marks_selected already in refresh_rect box, so
                            #   no need to refresh them individually.

                # reset all drag info before updating refresh rects
                self.mouse_left_down = None
                self.is_dragging = False
                self.rubberband_refresh_rect = None
                self.rubberband_draw_rect = None
                # Finally update all refresh rects
                self.Update()
            else:
                # get mouse location of left_up
                (img_x, img_y) = self.win2img_coord(evt_pos)
                mark_new_loc = (int(img_x), int(img_y))
                # Move a mark
                self.move_mark(
                        self.mouse_left_down['mark_pt'],
                        mark_new_loc,
                        self.mark_dragging_is_sel
                        )
                # MOVE_MARK from_coord to_coord
                self.history.new(
                        ['MOVE_MARK', self.mouse_left_down['mark_pt'], mark_new_loc],
                        description="Move Mark"
                        )

        else:
            # finish click by selecting at point with args from on_left_down
            # NOTE: if this was a double click, then mouse_left_down is None
            if self.mouse_left_down is not None:
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

        self.mark_dragging = None
        self.mark_dragging_is_sel = None

        if self.HasCapture():
            self.ReleaseMouse()

        # continue processing click, for example shifting focus to app
        evt.Skip()

    @debug_fxn
    def move_mark(self, from_mark_pt, to_mark_pt, is_selected):
        # delete orig position of dragged mark from normal list of marks
        #   if still present
        if from_mark_pt in self.marks:
            self.delete_mark(from_mark_pt, internal=True)
        # refresh old mark location
        self.refresh_mark_area(from_mark_pt)

        # finish moving mark by placing it in mark list
        self.mark_point(to_mark_pt, internal=True)
        # if dragged mark was selected, add to marks_selected too
        if is_selected:
            self.marks_selected.append(to_mark_pt)
        # TODO necessary?
        self.Update()

    @debug_fxn
    def refresh_mark_area(self, mark_pt):
        """Given img coords of a mark point, force a paint event with Refresh
        to paint mark region

        Args:
            mark_pt (tuple): mark point in image coordinates
        """
        (pos_x, pos_y) = self.img2win_coord(mark_pt[0] + 0.5, mark_pt[1] + 0.5)
        # refresh square size should be >= than mark size
        sq_size = const.CROSS_REFRESH_SQ_SIZE
        self.RefreshRect(
                wx.Rect(
                    pos_x - sq_size/2, pos_y - sq_size/2,
                    sq_size, sq_size
                    )
                )

    @debug_fxn
    def mark_point(self, img_point, internal=False, dup_ok=False):
        """Mark image coordinates with cross in window

        Args:
            img_point (tuple): int (x, y) in image coordinates mark location

        Returns (bool): True if new mark added, False if same point already
            exists in mark list
        """
        LOGGER.info("MSC: point (%d, %d)", img_point[0], img_point[1])

        if not dup_ok and img_point in self.marks:
            # mark already exists, doing nothing
            return False

        self.marks.append(img_point)

        self.refresh_mark_area(img_point)

        if not internal:
            # tell parent UI new total marks number
            self._update_mark_total()
            self.Update()
        return True

    @debug_fxn
    def mark_point_list(self, point_list):
        """Add list of points to marks

        Args:
            point_list (list): list of (x,y) tuples in image coordinates
        """
        for point in point_list:
            self.mark_point(point, internal=True)
        self._update_mark_total()
        self.Update()

    @debug_fxn
    def deselect_mark(self, desel_pt, internal=False):
        """Deselect one mark

        Args:
            desel_pt (tuple): (x,y) image coordinates of mark to deselect
            internal (bool): Default False.  If true, do NOT Update window
        """
        self.marks_selected.remove(desel_pt)
        self.refresh_mark_area(desel_pt)
        if not internal:
            self.Update()

    @debug_fxn
    def deselect_all_marks(self):
        """Deselect all marks
        """
        marks_selected = self.marks_selected.copy()
        for mark_pt in marks_selected:
            self.deselect_mark(mark_pt, internal=True)
        self.marks_selected = []
        self.Update()

    @debug_fxn
    def delete_mark(self, mark_pt, internal=False):
        """Delete one mark

        Args:
            mark_pt (tuple): (x,y) image coordinates of mark to delete
            internal (bool): Default False.  If true, do NOT Update window
        """
        self.marks.remove(mark_pt)
        # deleted mark may or may not be selected
        try:
            self.marks_selected.remove(mark_pt)
        except ValueError:
            pass
        self.refresh_mark_area(mark_pt)
        if not internal:
            # tell parent UI new total marks number
            self._update_mark_total()
            self.Update()

    @debug_fxn
    def delete_mark_point_list(self, point_list):
        """Delete list of marks

        Args:
            point_list (list): list of (x,y) mark img coords to delete
        """
        for point in point_list:
            self.delete_mark(point, internal=True)
        # tell parent UI new total marks number
        self._update_mark_total()
        self.Update()

    @debug_fxn
    def delete_selected_marks(self):
        """Delete all marks currently selected

        Returns:
            list: list of (x,y) image coordinates of marks just deleted
        """
        # make list copy
        # so deleting from self.marks_selected doesn't corrupt this operation
        # also so we have list later on for history
        marks_selected = self.marks_selected.copy()
        self.delete_mark_point_list(marks_selected)
        # return marks_deleted
        return marks_selected

    @debug_fxn
    def _update_mark_total(self):
        """tell parent UI new total marks number via previously registered fxn
        """
        if self.marks_num_update_fxn is not None:
            self.marks_num_update_fxn(len(self.marks))

    @debug_fxn
    def _mark_that_is_near_click(self, click_img_x, click_img_y):
        # default if no point is close enough
        sel_pt = None

        # how close can click to a mark to say we clicked on it
        prox_img = const.PROXIMITY_PX / self.zoom_val
        poss_points = []
        for (x, y) in self.marks:
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

        return sel_pt

    @debug_fxn
    def select_at_point(self, click_img_x, click_img_y, is_appending, is_toggling=False):
        """Given mouse click point coords, select mark (if any) that was clicked

        Args:
            click_img_x (float): x location of click in img coords
            click_img_y (float): y location of click in img coords
            is_appending (bool): True if we are appending selection, False if
                this mark becomes only selection
            is_toggling (bool): Default False. True to toggle selection status
                of this mark
        """
        # if we clicked on/near a mark, which mark?
        sel_pt = self._mark_that_is_near_click(click_img_x, click_img_y)

        if sel_pt is not None:
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
        """Select All marks
        """
        marks_unselected = [x for x in self.marks if x not in self.marks_selected]
        # copy all marks into marks_selected
        self.marks_selected = self.marks.copy()
        # set all unselected marks for refresh to allow color change
        for mark in marks_unselected:
            self.refresh_mark_area(mark)
        self.Update()

    @debug_fxn
    def paint_rect(self, paintdc, rect):
        """Given a rect needing a refresh in window PaintDC, Blit the image
        to fill that rect.

        Args:
            paintdc (wx.PaintDC): Device Context to Blit into
            rect (tuple): coordinates to refresh (window coordinates)
        """
        if self.has_no_image():
            paintdc.SetPen(wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT))
            paintdc.SetBrush(paintdc.GetBackground())
            paintdc.DrawRectangle(rect)
            # DONE
            return

        # get coords and choose scaled version of img_dc
        (
                stretch_blit_args,
                rect_pos_log, rect_size,
                blit_src_pos, blit_src_size,
                scale_dc,
                actual_dest_pos, actual_dest_size
                ) = self._get_rect_coords(rect)

        # NOTE: Blit shows no performance advantage over StretchBlit (Mac)
        # NOTE: StretchBlit uses ints for both src and dest pixel dimensions.
        #   This means to center and zoom accurately (sub-src-pixel) we need to
        #   refresh an area that INCLUDES the region needed, NOT ONLY that
        #   dest region.  This way we can zoom and position accurately, while
        #   employing the clipping mask behavior of PaintDC to make sure we
        #   only display in the area of the window
        # copy region from self.img_dc into paintdc with possible stretching
        paintdc.StretchBlit(*stretch_blit_args)

        rects_to_draw = self._get_margin_rects(
                rect_pos_log, rect_size,
                actual_dest_pos, actual_dest_size,
                )
        if rects_to_draw:
            paintdc.SetPen(wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.TRANSPARENT))
            # debug pen:
            #paintdc.SetPen(wx.Pen(wx.Colour(255, 0, 0), width=1, style=wx.SOLID))
            paintdc.SetBrush(paintdc.GetBackground())
            paintdc.DrawRectangleList(rects_to_draw)

        # draw marks visible in this region
        # need to multiply by scale_dc to get back to div1 image coordinates
        # expand by const.CROSS_REFRESH_SQ_SIZE/2 in each dir to repaint
        #   portion of mark even if center of mark is not in region
        sq_size = const.CROSS_REFRESH_SQ_SIZE
        self.draw_marks(
                paintdc,
                (blit_src_pos.x - sq_size/2)*scale_dc, (blit_src_pos.y - sq_size/2)*scale_dc,
                (blit_src_size.x + sq_size)*scale_dc, (blit_src_size.y + sq_size)*scale_dc)

        # draw rubber-band box AFTER marks, so it is drawn on top of them
        if self.rubberband_draw_rect is not None:
            self.draw_rubberband_box(paintdc)

    @debug_fxn
    def draw_marks(self, dc, src_pos_x, src_pos_y, src_size_x, src_size_y):
        """Given a region of a DC, Draw all marks within that region

        Args:
            dc (wx.MemoryDC): DC to draw into
            src_pos_x (float): x position in img coords of region
            src_pos_y (float): y position in img coords of region
            src_size_x (float): x size in img coords of region
            src_size_y (float): y size in img coords of region
        """
        pts_in_box = []
        marks_unselected = [x for x in self.marks if x not in self.marks_selected]
        for (x, y) in marks_unselected:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                cross_win = self.img2logical_coord(x + 0.5, y + 0.5)
                if cross_win not in pts_in_box:
                    # only draw bitmap if this is not a duplicate
                    # TODO: is this unnecessary and obsolete?
                    pts_in_box.append(cross_win)
                    # NOTE: if you change the size of this bmp, also change
                    #   the RefreshRect size const.CROSS_REFRESH_SQ_SIZE
                    dc.DrawBitmap(
                            const.CROSS_UNSEL_BMP,
                            cross_win - const.CROSS_CENTER_COORDS
                            )

        pts_in_box = []
        for (x, y) in self.marks_selected:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                cross_win = self.img2logical_coord(x + 0.5, y + 0.5)
                if cross_win not in pts_in_box:
                    # only draw bitmap if this is not a duplicate
                    # TODO: is this unnecessary and obsolete?
                    pts_in_box.append(cross_win)
                    # NOTE: if you change the size of this bmp, also change
                    #   the RefreshRect size const.CROSS_REFRESH_SQ_SIZE
                    dc.DrawBitmap(
                            const.CROSS_SEL_BMP,
                            cross_win - const.CROSS_CENTER_COORDS
                            )

        if self.mark_dragging is not None:
            (x, y) = self.mark_dragging
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                cross_win = self.img2logical_coord(x + 0.5, y + 0.5)
                if self.mark_dragging_is_sel:
                    dc.DrawBitmap(
                            const.CROSS_SEL_BMP,
                            cross_win - const.CROSS_CENTER_COORDS
                            )
                else:
                    dc.DrawBitmap(
                            const.CROSS_UNSEL_BMP,
                            cross_win - const.CROSS_CENTER_COORDS
                            )

    @debug_fxn
    def export_to_image(self):
        dc_source = self.img_dc

        # based largely on code posted to wxpython-users by Andrea Gavana 2006-11-08
        size = dc_source.GetSize()

        # Create a Bitmap that will later on hold the screenshot image
        # Note that the Bitmap must have a size big enough to hold the screenshot
        # -1 means using the current default colour depth
        bmp = wx.Bitmap(size.width, size.height)

        # Create a memory DC that will be used for actually taking the screenshot
        #   use bmp as SelectObject
        # Tell the memory DC to use our Bitmap
        # all drawing action on the memory DC will go to the Bitmap now
        memDC = wx.MemoryDC(bmp)

        # Blit (in this case copy) the actual screen on the memory DC
        # and thus the Bitmap
        memDC.Blit(0, 0,    # dest position
            size.width, size.height, # src, dest size
            dc_source,      # From where do we copy?
            0, 0            # src position
            )

        # draw marks visible in this region
        # need to multiply by scale_dc to get back to div1 image coordinates
        # expand by const.CROSS_REFRESH_SQ_SIZE/2 in each dir to repaint
        #   portion of mark even if center of mark is not in region
        sq_size = const.CROSS_REFRESH_SQ_SIZE

        # save current self.img_coord_xlation_{x,y}
        img_coord_xlation_x_save = self.img_coord_xlation.x
        img_coord_xlation_y_save = self.img_coord_xlation.y
        # set all mark-affecting parameters for output memDC
        self.zoom_val = 1
        self.img_coord_xlation.x = 0
        self.img_coord_xlation.y = 0

        self.draw_marks(
                memDC,
                (0 - sq_size/2), (0 - sq_size/2),
                (size.width + sq_size), (size.height + sq_size))

        # restore self.zoom_val and self.img_coord_xlation_{x,y}
        self.zoom_val = self.zoom_list[self.zoom_idx]
        self.img_coord_xlation.x = img_coord_xlation_x_save
        self.img_coord_xlation.y = img_coord_xlation_y_save

        # Select the Bitmap out of the memory DC by selecting a new
        # uninitialized Bitmap
        memDC.SelectObject(wx.NullBitmap)

        img = bmp.ConvertToImage()
        #img.SaveFile('saved.png', wx.BITMAP_TYPE_PNG)
        return img
