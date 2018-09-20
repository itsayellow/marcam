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

import wx
import numpy as np

import const
import common
import image_scrolled_canvas

# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug)


# really a Scrolled Window
class ImageScrolledCanvasMarks(image_scrolled_canvas.ImageScrolledCanvas):
    """Window (in the wx sense) widget that displays an image, zooms in and
    out, and allows scrolling/panning in up/down and side/side if image is
    big enough.  If image is smaller than window it is auto-centered
    Also allow for setting, selecting, deleting, marks.
    """
    @debug_fxn
    def __init__(self, parent, *args, **kwargs):
        # get win_history and pass on to ImageScrolledCanvas
        # get marks_num_update_fxn and don't pass on to ImageScrolledCanvas
        cache_dir = kwargs.get('cache_dir', None)
        win_history = kwargs.get('win_history', None)
        marks_num_update_fxn = kwargs.pop('marks_num_update_fxn', None)
        assert cache_dir is not None
        assert win_history is not None
        assert marks_num_update_fxn is not None

        super().__init__(parent, *args, **kwargs)

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
        # Resume normal Event Processing after this method returns
        # Continue processing click, for example shifting focus to app.
        evt.Skip()

        # return early if no image
        if self.has_no_image():
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
                    # mark only added if not duplicate of previous point
                    self.history.new(
                            ['MARK', img_pt],
                            description="Add Mark"
                            )
                else:
                    # simulate the making of a mark while actually doing nothing
                    # this allows the user to undo what seems like the last mark
                    #   without making an actual duplicate mark in the same
                    #   location.
                    self.history.new(['NOP'], description="Add Mark")
        else:
            # we allow click outside of image in case we drag onto image

            # start following motion until on_left_up, in case this is a drag
            self.Bind(wx.EVT_MOTION, self.on_motion)

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

    @debug_fxn_debug
    def on_motion(self, evt):
        """EVT_MOTION handler: "mouse moving".  Used esp. to track dragging

        Args:
            evt (wx.MouseEvent): obj returned from mouse event
        """
        # Resume normal Event Processing after this method returns
        evt.Skip()

        # return early if no image or if in Mark Mode
        #   (Mark mode does everything in on_left_down, no drags)
        if self.has_no_image() or self.mark_mode:
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
        # Resume normal Event Processing after this method returns
        # Continue processing click, for example shifting focus to app.
        evt.Skip()

        # return early if no image or if in Mark Mode
        #   (Mark mode does everything in on_left_down, no drags)
        if self.has_no_image() or self.mark_mode:
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

        # stop following motion
        self.Unbind(wx.EVT_MOTION)

    @debug_fxn
    def move_mark(self, from_mark_pt, to_mark_pt, is_selected):
        """Move mark from one location to another

        Args:
            from_mark_pt (tuple): (x,y) original mark location
            to_mark_pt (tuple): (x,y) new mark location
            is_selected (bool): whether mark is currently selected
        """
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
        # Finally force a repaint of all invalidated areas
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
        marks_unselected = [x for x in self.marks if x not in self.marks_selected]
        for (x, y) in marks_unselected:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                cross_win = self.img2logical_coord(x + 0.5, y + 0.5)
                # NOTE: if you change the size of this bmp, also change
                #   the RefreshRect size const.CROSS_REFRESH_SQ_SIZE
                dc.DrawBitmap(
                        const.CROSS_UNSEL_BMP,
                        cross_win - const.CROSS_CENTER_COORDS
                        )

        for (x, y) in self.marks_selected:
            if (src_pos_x <= x <= src_pos_x + src_size_x and
                    src_pos_y <= y <= src_pos_y + src_size_y):
                # add half pixel so cross is in center of pix square when zoomed
                cross_win = self.img2logical_coord(x + 0.5, y + 0.5)
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
    def export_draw_to_memdc(self, mem_dc, width, height):
        # Blit (in this case copy) the actual screen on the memory DC
        # and thus the Bitmap
        mem_dc.Blit(0, 0,   # dest position
            width, height,  # src, dest size
            self.img_dc,    # From where do we copy?
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
        # set all mark-affecting parameters for output mem_dc
        self.zoom_val = 1
        self.img_coord_xlation.x = 0
        self.img_coord_xlation.y = 0

        self.draw_marks(
                mem_dc,
                (0 - sq_size/2), (0 - sq_size/2),
                (width + sq_size), (height + sq_size)
                )

        # restore self.zoom_val and self.img_coord_xlation_{x,y}
        self.zoom_val = self.zoom_list[self.zoom_idx]
        self.img_coord_xlation.x = img_coord_xlation_x_save
        self.img_coord_xlation.y = img_coord_xlation_y_save
