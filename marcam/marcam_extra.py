#!/usr/bin/env python3

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

# GUI for displaying an image and counting cells

# TODO: Mac OS X specific things to possibly try:
#   wx.TopLevelWindow.OSXSetModified()

import argparse
from datetime import datetime
import json
import logging
import os
import os.path # TODO: consider pathlib
import platform
import re
import sys
import threading
import time

import wx
import wx.adv
import wx.html2
import wx.lib.dialogs
import wx.lib.newevent

import image_proc
from image_scrolled_canvas import ImageScrolledCanvasMarks
import const
import common
import mcmfile
if const.PLATFORM == 'win':
    import winpipe


# DEBUG defaults to False.  Is set to True if debug switch found
DEBUG = False

# which modules are we logging
LOGGED_MODULES = [
        __name__, 'common', 'image_proc', 'image_scrolled_canvas', 'longtask',
        'mcmfile', 'winpipe'
        ]

# global logger obj for this file
LOGGER = logging.getLogger(__name__)

LOGGER.info("MSC:ICON_DIR=%s", const.ICON_DIR)

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)


@debug_fxn
def get_text_width_px(window, text_str):
    screen_dc = wx.ScreenDC()
    screen_dc.SetFont(window.GetFont())
    (text_width_px, _) = screen_dc.GetTextExtent(text_str)
    del screen_dc

    return text_width_px


class MarcamFormatter(logging.Formatter):
    def format(self, record):
        """Overload of default format fxn, make all lines after first indented
        of a log message

        Args:
            record (Logger.LogRecord): log message

        Returns:
            out_string: processed log message
        """
        out_string = super().format(record)
        # indent all lines after main format string
        out_string = out_string.replace("\n", "\n    ")
        return out_string


class EditHistory():
    """Keeps track of Edit History, undo, redo, whether save is needed
    """
    def __init__(self):
        self.undo_menu_item = None
        self.redo_menu_item = None
        self.history = []
        self.history_ptr = -1
        self._update_menu_items()

    @debug_fxn
    def reset(self):
        """Reset Edit History so it has no entries and ptr is reset
        """
        self.history = []
        self.history_ptr = -1
        self._update_menu_items()

    @debug_fxn
    def new(self, item, description=""):
        """Make a new Edit History item

        Args:
            item (list): list with first item being action string, and
                following items information concerning that action
            description (str): Short text description of the action,
                for putting after "Undo" or "Redo" in menu items.
                e.g. "Undo Add Marks", "Undo Invert Image"
        """
        # truncate list so current item is last item (makes empty list
        #   if self.history_ptr == -1)
        self.history = self.history[:self.history_ptr + 1]
        self.history.append(
                {
                    'edit_action':item,
                    'description':description,
                    'save_flag':False
                    }
                )
        self.history_ptr = len(self.history) - 1
        self._update_menu_items()

    @debug_fxn
    def save_notify(self):
        """Set save flag for current history action only, erase flag for all
        other actions in history

        save flag indicates that at this point in history, the file can be
        considered "saved" and we don't have to query user on close of file
        """
        # set all edit history save flags to False
        for i in range(len(self.history)):
            self.history[i]['save_flag'] = False

        # set current edit history action save flags to True
        if self.history_ptr > -1:
            self.history[self.history_ptr]['save_flag'] = True

    @debug_fxn
    def is_saved(self):
        """At this point in history, has user most recently saved document?

        Returns:
            bool: True if this point in history is saved
        """
        if self.history_ptr == -1:
            # no edit history, so no save needed
            return True

        return self.history[self.history_ptr]['save_flag']

    @debug_fxn
    def undo(self):
        """Return action to undo, and move history pointer to prev. action
        in history

        Returns:
            list: action, first item is str of action, remainig items
                are action info.  Returns None if nothing left to redo
        """
        if self._can_undo():
            undo_action = self.history[self.history_ptr]['edit_action']
            self.history_ptr -= 1
        else:
            undo_action = None

        self._update_menu_items()
        return undo_action

    @debug_fxn
    def redo(self):
        """Return action to redo, and move history pointer to next action
        in history

        Returns:
            list: action, first item is str of action, remainig items
                are action info.  Returns None if nothing left to undo
        """
        if self._can_redo():
            self.history_ptr += 1
            redo_action = self.history[self.history_ptr]['edit_action']
        else:
            redo_action = None

        self._update_menu_items()
        return redo_action

    @debug_fxn
    def get_actions_since_save(self):
        if self.is_saved():
            # no edit history or no actions since save
            return None

        try:
            save_loc = [x['save_flag'] for x in self.history].index(True)
        except ValueError:
            # never saved
            save_loc = -1

        if save_loc < self.history_ptr:
            edits_since_save = self.history[save_loc+1:self.history_ptr+1]
            edits_since_save = [x['description'] for x in edits_since_save]
        else:
            # save_loc > self.history_ptr:
            edits_since_save = self.history[self.history_ptr+1:save_loc+1]
            edits_since_save = ["Undo " + x['description'] for x in edits_since_save]
            edits_since_save.reverse()

        item_count = 1
        edits_since_save_new = []
        for (i, this_edit) in enumerate(edits_since_save):
            if i+1 < len(edits_since_save) and edits_since_save[i+1] == this_edit:
                item_count += 1
            else:
                edits_since_save_new.append(
                        this_edit + (" [x%d]"%item_count if item_count > 1 else "")
                        )
                item_count = 1

        return edits_since_save_new

    @debug_fxn
    def _can_undo(self):
        """Is there an action to undo back in history?

        Returns:
            bool: True if can undo
        """
        return (len(self.history) > 0) and (self.history_ptr >= 0)

    @debug_fxn
    def _can_redo(self):
        """Is there an action to redo next in history?

        Returns:
            bool: True if can redo
        """
        return (len(self.history) > 0) and (self.history_ptr < len(self.history) - 1)

    @debug_fxn
    def _update_menu_items(self):
        """Update the Enabled/Disabled quality of Undo, Redo Menu items
        """
        if self.undo_menu_item is not None:
            self.undo_menu_item.Enable(self._can_undo())
            if self._can_undo():
                key_accel = self.undo_menu_item.GetItemLabel().split('\t')[1]
                undo_descrip = self.history[self.history_ptr]['description']
                self.undo_menu_item.SetItemLabel(
                        "Undo " + undo_descrip + "\t" + key_accel
                        )
            else:
                key_accel = self.undo_menu_item.GetItemLabel().split('\t')[1]
                self.undo_menu_item.SetItemLabel(
                        "Undo\t" + key_accel
                        )

        if self.redo_menu_item is not None:
            self.redo_menu_item.Enable(self._can_redo())
            if self._can_redo():
                key_accel = self.redo_menu_item.GetItemLabel().split('\t')[1]
                undo_descrip = self.history[self.history_ptr + 1]['description']
                self.redo_menu_item.SetItemLabel(
                        "Redo " + undo_descrip + "\t" + key_accel
                        )
            else:
                key_accel = self.redo_menu_item.GetItemLabel().split('\t')[1]
                self.redo_menu_item.SetItemLabel(
                        "Redo\t" + key_accel
                        )

    @debug_fxn
    def register_undo_menu_item(self, undo_menu_item):
        """Give this class instance the Undo menu item instance so it can
        Enable and Disable menu item on its own

        Args:
            undo_menu_item (wx.MenuItem): menu item instance for Undo
        """
        self.undo_menu_item = undo_menu_item
        self._update_menu_items()

    @debug_fxn
    def register_redo_menu_item(self, redo_menu_item):
        """Give this class instance the Redo menu item instance so it can
        Enable and Disable menu item on its own

        Args:
            redo_menu_item (wx.MenuItem): menu item instance for Redo
        """
        self.redo_menu_item = redo_menu_item
        self._update_menu_items()


class FileDropTarget(wx.FileDropTarget):
    """FileDropTarget Facilitating dragging file into window to open
    """
    def __init__(self, window_target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_target = window_target

    @debug_fxn
    def OnDropFiles(self, _x, _y, filenames):
        """Dropped File Handler

        Args:
            _x (int): x coordinate of mouse
            _y (int): y coordinate of mouse
            filenames (list): A list of filepaths
        """
        filename = filenames[0]
        LOGGER.info("MSC:Drag and Drop filename:\n    %s", repr(filename))

        # ---------
        # OPTION 1: Open new frame or put image in existing blank frame
        img_ok = self.window_target.parent.open_image(filename)
        # ---------
        ## OPTION 2: Replace existing image in same frame
        ## Close any existing image
        #self.window_target.parent.close_image(keep_win_open=True)
        ## Open Drag-and-Dropped image file
        #img_ok = self.window_target.parent.open_image_this_frame(filename)
        # ---------

        # True to accept data, False to veto
        return img_ok


class ImageAutoContrastDialog(wx.Dialog):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, title="Image Auto-Contrast", **kwargs)

        starting_val = 0

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Slider Value Display
        # Find text width of "999", large enough to show 0 through 20
        text_width_px = get_text_width_px(self, "999")
        sizer_h = wx.BoxSizer(wx.HORIZONTAL)
        static_text = wx.StaticText(self, wx.ID_ANY, "Auto-Contrast Level:")
        sizer_h.Add(static_text, flag=wx.ALIGN_CENTER, proportion=0)
        self.value_display = wx.TextCtrl(
                self,
                id=wx.ID_ANY,
                value="%d"%starting_val,
                size=wx.Size(text_width_px, -1),
                style=wx.TE_READONLY
                #style=wx.TE_READONLY | wx.TE_CENTRE
                )
        sizer_h.Add(
                self.value_display,
                proportion=0,
                flag=wx.ALIGN_CENTER
                #flag=wx.ALIGN_CENTER | wx.TOP,
                #border=10
                )
        sizer.AddSpacer(10)
        sizer.Add(
                sizer_h,
                proportion=0,
                #flag=wx.ALIGN_CENTER | wx.TOP,
                flag=wx.ALIGN_LEFT | wx.TOP | wx.LEFT | wx.RIGHT,
                border=10
                )

        # Slider Control
        self.slider = wx.Slider(
                self,
                id=wx.ID_ANY,
                value=starting_val,
                minValue=0, maxValue=20,
                size=(250, -1),
                #style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS | wx.SL_MIN_MAX_LABELS
                style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS
                )
        self.slider.SetTickFreq(1)
        sizer.Add(
                self.slider,
                proportion=0,
                #flag=wx.LEFT | wx.RIGHT,
                flag=wx.ALL,
                border=10
                )

        # OK, Cancel Buttons
        btnsizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(
                btnsizer,
                proportion=0,
                flag=wx.BOTTOM | wx.ALIGN_RIGHT,
                border=5
                )

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Bind(wx.EVT_SLIDER, self.on_evt_slider)

    def on_evt_slider(self, evt):
        slider_val = self.slider.GetValue()
        self.value_display.SetLabel("%d"%slider_val)


class ImageFalseColorDialog(wx.Dialog):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, title="Image False Color", **kwargs)

        self.cmap_choices = ['Viridis', 'Plasma', 'Magma', 'Inferno']

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(10)
        # Choice widget selects one of many string options
        text_width_px = get_text_width_px(self, "999")
        sizer_h = wx.BoxSizer(wx.HORIZONTAL)
        static_text = wx.StaticText(self, wx.ID_ANY, "Use colormap:")
        sizer_h.AddSpacer(20)
        sizer_h.Add(static_text, flag=wx.ALIGN_CENTER, proportion=0)
        self.colormap_choice = wx.Choice(
                self,
                id=wx.ID_ANY,
                choices=self.cmap_choices,
                )
        sizer_h.Add(
                self.colormap_choice,
                proportion=0,
                flag=wx.ALIGN_CENTER
                #flag=wx.ALIGN_CENTER | wx.TOP,
                #border=10
                )
        sizer_h.AddSpacer(20)
        sizer.Add(
                sizer_h,
                proportion=0,
                #flag=wx.ALIGN_CENTER | wx.TOP,
                flag=wx.ALIGN_LEFT | wx.ALL,
                border=10
                )

        # OK, Cancel Buttons
        btnsizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(
                btnsizer,
                proportion=0,
                flag=wx.BOTTOM | wx.ALIGN_RIGHT,
                border=5
                )

        self.SetSizer(sizer)
        sizer.Fit(self)
        #self.Bind(wx.EVT_SLIDER, self.on_evt_slider)

    def get_colormap(self):
        return self.cmap_choices[self.colormap_choice.GetSelection()].lower()

    #def on_evt_slider(self, evt):
    #    slider_val = self.slider.GetValue()
    #    self.value_display.SetLabel("%d"%slider_val)


class HelpFrame(wx.Frame):
    """Separate window to contain HTML help viewer
    """
    def __init__(self, *args, **kwargs):
        """Constructor"""
        super().__init__(*args, **kwargs)

        if const.PLATFORM == 'mac':
            help_filename = 'marcam_help_mac.html'
        else:
            help_filename = 'marcam_help.html'

        # use wx.html2 to allow better rendering (and CSS in future)
        self.html = wx.html2.WebView.New(self)
        self.html.LoadURL(
                'file://' + os.path.join(const.ICON_DIR, help_filename)
                )

        self.SetTitle("Marcam Help")
        self.SetSize((500, 600))


class FrameList():
    @debug_fxn
    def __init__(self):
        # index dict by ID, as we use this most often
        self.frame_dict = {}
        self.win_menu_list = []
        self.is_handling_window_menu = False

    @debug_fxn
    def active_frame(self):
        """Return the frame in FrameList that is currently active.
        """
        for frame_id in self.frame_dict:
            if self.frame_dict[frame_id]['frame'].IsActive():
                return_frame = self.frame_dict[frame_id]['frame']
                break
        return return_frame

    @debug_fxn
    def frame_with_file(self, img_file):
        """Return the frame in FrameList that has img_file inside it.
        """
        return_frame = None
        for frame_id in self.frame_dict:
            if (
                    self.frame_dict[frame_id]['frame'].img_path == img_file or
                    (
                        isinstance(self.frame_dict[frame_id]['frame'].img_path, list) and
                        self.frame_dict[frame_id]['frame'].img_path[0] == img_file
                        )
                    ):
                return_frame = self.frame_dict[frame_id]['frame']
                break
        return return_frame

    @debug_fxn
    def has_zero(self):
        """FrameList contains zero frames (empty).
        """
        return not self.frame_dict

    @debug_fxn
    def has_one(self):
        """FrameList contains only one frame.
        """
        return len(self.frame_dict) == 1

    @debug_fxn
    def all_have_image(self):
        """All FrameList frames contain images (has_image()==True)
        """
        # We assume the only possibility of a frame not having an image is if
        #   it is the only one.  Thus it is "safe" to just check [0].
        # self.frame_dict.values is a dictionary view object, we must convert
        #   it to list before indexing
        return len(self.frame_dict) > 0 and list(self.frame_dict.values())[0]['frame'].has_image()

    @debug_fxn
    def has_multiple(self):
        """FrameList has multiple frames.
        """
        return len(self.frame_dict) > 1

    @debug_fxn
    def frame_from_id(self, frame_id):
        """Return the frame specified by frame ID.
        """
        return self.frame_dict[frame_id]['frame']

    @debug_fxn
    def only_frame(self):
        """Return the only frame in the list
        """
        assert len(self.frame_dict) == 1
        # self.frame_dict.values is a dictionary view object, we must convert
        #   it to list before indexing
        return list(self.frame_dict.values())[0]['frame']

    @debug_fxn
    def append(self, frame_to_append):
        """Add the specified frame to the FrameList
        """
        # init to empty dict if not already
        self.frame_dict.setdefault(frame_to_append.GetId(), {})
        self.frame_dict[frame_to_append.GetId()]['frame'] = frame_to_append
        # if wxpython ever automatically manages the Window menu on Mac, the
        #   following will be unnecessary
        self.win_menu_list.append(frame_to_append.GetId())
        self.update_window_menu()

    @debug_fxn
    def update_window_menu(self):
        """Update the frame list part of the Window Menu on Mac

        if wxpython ever automatically manages the Window menu on Mac, the
        following will be unnecessary

        """
        if not self.is_handling_window_menu:
            return

        for frame_id in self.frame_dict:
            # we update each frame's Window menu list of windows
            this_frame = self.frame_dict[frame_id]['frame']
            win_menu = self.frame_dict[frame_id]['menu']
            win_menu_origcount = self.frame_dict[frame_id]['menu_origcount']
            for (i, menuitem_frame_id) in enumerate(self.win_menu_list):
                menuitem_frame = self.frame_dict[menuitem_frame_id]['frame']
                menuitem_frame_title = menuitem_frame.GetTitle()
                if win_menu_origcount + i < win_menu.GetMenuItemCount():
                    win_menu_item = win_menu.FindItemByPosition(i + win_menu_origcount)
                    if win_menu_item.GetItemLabel() == menuitem_frame_title:
                        # Current menu item is correct, set this_menuitem
                        this_menuitem = win_menu_item
                    else:
                        # Current menu item is not correct, replace it
                        win_menu.Remove(win_menu_item)
                        this_menuitem = win_menu.InsertCheckItem(
                                i + win_menu_origcount,
                                wx.ID_ANY,
                                menuitem_frame_title
                                )
                else:
                    # We don't have a menu item yet, so append one
                    this_menuitem = win_menu.AppendCheckItem(
                            wx.ID_ANY,
                            menuitem_frame_title
                            )
                if menuitem_frame_title == this_frame.GetTitle():
                    # For the Window menu item that is for our own window,
                    #   check it to show that's where we are
                    this_menuitem.Check(True)

                # Bind this menuitem to the appropriate frame's activation
                #   function
                this_frame.Bind(
                        wx.EVT_MENU,
                        menuitem_frame.on_window_menu_activate,
                        this_menuitem
                        )

    #@debug_fxn
    #def remove(self, frame_to_remove):
    #    self.frame_dict.pop(frame_to_remove.GetId())

    @debug_fxn
    def remove_id(self, frame_id_to_remove):
        """Remove the frame specified by frame ID from the FrameList
        """
        self.frame_dict.pop(frame_id_to_remove)

    @debug_fxn
    def register_window_menu(self, frame_inst, window_menu):
        # init to empty dict if not already
        self.frame_dict.setdefault(frame_inst.GetId(), {})
        self.frame_dict[frame_inst.GetId()]['menu'] = window_menu
        self.frame_dict[frame_inst.GetId()]['menu_origcount'] = window_menu.GetMenuItemCount()
        self.is_handling_window_menu = True

    @debug_fxn
    def get_list_copy(self):
        # TODO: hopefully we won't need this forever, stopgap
        return [self.frame_dict[id]['frame'] for id in self.frame_dict]
