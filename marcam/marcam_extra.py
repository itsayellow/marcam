"""Classes necessary for marcam.py that are not MarcamApp or ImageWindow
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


import collections
import logging
import pathlib

import wx
import wx.html2

import const
import common


# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info)
debug_fxn_debug = common.debug_fxn_factory(LOGGER)


STDERR_STR = "STDERR: "


@debug_fxn
def file_unable_to_open_dialog(parent, img_path):
    """Common code whenever a file is not valid to be opened.

    Args:
        parent (wx.Window or None): parent window
        img_path (str): path to image file that was invalid
    """
    LOGGER.warning("Unable to open file: %s", img_path)
    wx.MessageDialog(parent,
            message="Unable to open file: %s"%img_path,
            caption="File Read Error",
            style=wx.OK | wx.ICON_EXCLAMATION
            ).ShowModal()


class StderrToLog:
    """Replace sys.stderr with this to route stderr messages to LOGGER
    """
    def __init__(self):
        self.buffer = ""

    def write(self, text):
        """Write test directly to LOGGER.error.  Masquerade as stderr.write()
        """
        # must not put STDERR_STR as literal string, because our custom
        #   MarcamFormatter doesn't format when looking for STDERR_STR
        LOGGER.error(STDERR_STR + text)
        return len(text)

    def writelines(self, lines):
        """Write lines of text directly to LOGGER.error.  Masquerade as
            stderr.writelines().
        """
        # must not put STDERR_STR as literal string, because our custom
        #   MarcamFormatter doesn't format when looking for STDERR_STR
        LOGGER.error(STDERR_STR + "StderrToLog.writelines()")
        self.write("".join(lines))

    def flush(self):
        """NOP.  Masquerade as stderr.flush().
        """
        # must not put STDERR_STR as literal string, because our custom
        #   MarcamFormatter doesn't format when looking for STDERR_STR
        LOGGER.error(STDERR_STR + "StderrToLog.flush()")


class FileHistory(wx.FileHistory):
    """Like wx.FileHistory, but changing how menu items are displayed
        so that they are either all relative to user's home diretory, or
        failing that, absolute paths.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.managed_menus = []
        self.base_id = super().GetBaseId()

    def _remove_file_from_menu(self, menu, i):
        # Delete specified item and all lower items
        # range + 1 because we've already removed the item in super()
        #   but not in our own menu
        for file_hist_i in range(i, super().GetCount() + 1):
            menu.Delete(self.base_id + file_hist_i)

        # Add back items with new IDs
        self._add_all_files_to_menu(menu, starting_file=i)

    def _remove_file_from_menus(self, i):
        for menu in self.managed_menus:
            self._remove_file_from_menu(menu, i)

    def _add_file_to_menu(self, menu):
        # Delete all history items
        # range - 1 because we've already added the item in super()
        #   but not in our own menu
        for file_hist_i in range(0, super().GetCount() - 1):
            menu.Delete(self.base_id + file_hist_i)

        # Add back items with new IDs
        self._add_all_files_to_menu(menu)

    def _add_file_to_menus(self):
        for menu in self.managed_menus:
            self._add_file_to_menu(menu)

    def _add_all_files_to_menu(self, menu, starting_file=0):
        # Add all items to end of menu
        for file_hist_i in range(starting_file, super().GetCount()):
            menu.Append(
                    self.base_id + file_hist_i,
                    self.FormatFilePathMenu(super().GetHistoryFile(file_hist_i))
                    )

    def _add_all_files_to_menus(self):
        for menu in self.managed_menus:
            self._add_all_files_to_menu(menu)

    def FormatFilePathMenu(self, file_path):
        """Given an input file_path string, output a formatted string to
            be displayed in a Recent Files menu item.

        Args:
            file_path (str): path to a file

        Output:
            str: file_path formatted as it should appear in Recent Files menu
        """
        file_path = pathlib.Path(file_path)
        try:
            # Attempt to find path relative to home directory
            file_path = file_path.relative_to(pathlib.Path.home())
        except ValueError:
            # keep absolute path if path not under home directory
            pass
        return str(file_path)

    def UseMenu(self, menu):
        """Add menu to list of managed menus
        """
        self.managed_menus.append(menu)

    def RemoveMenu(self, menu):
        """Remove menu from list of managed menus
        """
        self.managed_menus.remove(menu)

    def AddFilesToMenu(self, *args, **kwargs):
        """Add all recent files to menu in argument.  If no menu in argument
            then add files to all managed menus.

        Args:
            menu (wx.Menu): menu to add Recent Files to.
        """
        if args or kwargs.get('menu', False):
            self._add_all_files_to_menu(args[0])
        elif kwargs.get('menu', False):
            self._add_all_files_to_menu(kwargs['menu'])
        else:
            self._add_all_files_to_menus()

    def AddFileToHistory(self, filename):
        """Add filename to database of recent files, and to all managed menus.

        Args:
            filename (str): filename to add
        """
        super().AddFileToHistory(filename)
        self._add_file_to_menus()

    def RemoveFileFromHistory(self, i):
        """Remove filename from database of recent files, and all managed menus.

        Args:
            filename (str): filename to remove
        """
        super().RemoveFileFromHistory(i)
        self._remove_file_from_menus(i)


class MarcamFormatter(logging.Formatter):
    """Our specific Formatter for logging
    """
    def __init__(self, *args, **kwargs):
        """Init mostly the same as parent, but with extra option add_terminator.

        Args:
            add_terminator (bool): if True, every line will have a \n added
                except for all stderr lines but the last one.
        """
        # If boolean add_terminator is present, save to object and remove
        #   from passed kwargs.
        self.add_terminator = kwargs.pop('add_terminator', False)
        super().__init__(*args, **kwargs)
        self.last_was_stderr = False

    def format(self, record):
        """Overload of default format fxn, make all lines after first indented
        of a log message

        If lines are from piped stderr, then format the first line, and do
        not format the following stderr lines.  Also do not add a terminator
        if requested by self.add_terminator for all lines except the last one.

        Args:
            record (Logger.LogRecord): log message

        Returns:
            out_string: processed log message
        """
        # Is this current log message starting with stderr string?
        # msg must start with literal STDERR_STR and not %s that resolves
        #   to STDERR_STR, otherwise processing format arguments gets very
        #   complex.
        now_stderr = record.msg.startswith(STDERR_STR)

        if now_stderr:
            # Remove STDERR_STR from beginning of message
            record.msg = record.msg[len(STDERR_STR):]

        if self.last_was_stderr and now_stderr:
            # print stderr lines with no format if prev. was stderr

            # get message of record with user args substituted
            out_string = record.getMessage()
        else:
            # normal message formatting
            out_string = super().format(record)
            # indent all lines after main format string
            out_string = out_string.replace("\n", "\n    ")

        if self.add_terminator and self.last_was_stderr and not now_stderr:
            # finish previous stderr with a CR before printing this string
            out_string = "\n" + out_string

        if self.add_terminator and not now_stderr:
            # finish this string with a CR before printing this string
            out_string = out_string + "\n"

        self.last_was_stderr = now_stderr

        return out_string


class EditHistory():
    """Keeps track of Edit History, undo, redo, whether save is needed

    TODO: when we initialize or reset, we need to know if we've ever been saved
    """
    def __init__(self):
        self.undo_menu_item = None
        self.redo_menu_item = None
        self.save_menu_item = None
        self.history_nodes = None
        self.history_node_i = None
        self.history_edges = None

        # (node0) - edge0 - (node1) - edge1 - (node2) - edge2 - (node3)
        # edgeN connects nodeN and nodeN+1

        self.reset()

    @debug_fxn
    def reset(self):
        """Reset Edit History so it has no entries and ptr is reset
        """
        # one node for each state of file
        self.history_nodes = [{'save_flag':False}]
        self.history_node_i = 0
        # one edge connects two nodes, an action that transforms previous
        #   node to next node
        self.history_edges = []

        # update Save, Redo, Undo menu items
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
        # truncate nodes so current node is last item
        self.history_nodes = self.history_nodes[:self.history_node_i + 1]
        # truncate edges (always len(history_nodes)-1 length)
        self.history_edges = self.history_edges[:self.history_node_i]

        self.history_nodes.append(
                {
                    'save_flag':False
                    }
                )
        self.history_edges.append(
                {
                    'edit_action':item,
                    'description':description,
                    }
                )
        self.history_node_i = len(self.history_nodes) - 1

        # update Save, Redo, Undo menu items
        self._update_menu_items()

    @debug_fxn
    def save_notify(self):
        """Set save flag for current history action only, erase flag for all
        other actions in history

        save flag indicates that at this point in history, the file can be
        considered "saved" and we don't have to query user on close of file
        """
        # set all edit history save flags to False
        for i in range(len(self.history_nodes)):
            self.history_nodes[i]['save_flag'] = False

        # set current edit history node save flag to True
        self.history_nodes[self.history_node_i]['save_flag'] = True

        # update Save, Redo, Undo menu items
        self._update_menu_items()

    @debug_fxn
    def is_saved(self):
        """At this point in history, has user most recently saved document?

        Returns:
            bool: True if this point in history is saved
        """
        return self.history_nodes[self.history_node_i]['save_flag']

    @debug_fxn
    def undo(self):
        """Return action to undo, and move history pointer to prev. action
        in history

        Returns:
            list: action, first item is str of action, remainig items
                are action info.  Returns None if nothing left to redo
        """
        if self._can_undo():
            undo_action = self.history_edges[self.history_node_i - 1]['edit_action']
            self.history_node_i -= 1
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
            redo_action = self.history_edges[self.history_node_i]['edit_action']
            self.history_node_i += 1
        else:
            redo_action = None

        self._update_menu_items()
        return redo_action

    @debug_fxn
    def get_actions_since_save(self):
        """Return a formatted list of actions in EditHistory since last save

        Returns:
            (list, bool): (list of strings representing actions happened since
                last save, True if file was never saved)
        """
        # initial value
        never_saved = False

        if self.is_saved():
            # no edit history or no actions since save
            return (None, never_saved)

        try:
            save_loc = [x['save_flag'] for x in self.history_nodes].index(True)
        except ValueError:
            # never saved, set to initial node
            never_saved = True
            save_loc = 0

        if save_loc < self.history_node_i:
            edits_since_save = self.history_edges[save_loc:self.history_node_i]
            edits_since_save = [x for x in edits_since_save if x['edit_action'][0] != 'NOP']
            edits_since_save = [x['description'] for x in edits_since_save]
        else:
            # save_loc > self.history_node_i:
            edits_since_save = self.history_edges[self.history_node_i:save_loc]
            edits_since_save = [x for x in edits_since_save if x['edit_action'][0] != 'NOP']
            edits_since_save = ["Undo " + x['description'] for x in edits_since_save]
            edits_since_save.reverse()

        # aggregate repeated sequential edits in one description
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

        return (edits_since_save_new, never_saved)

    @debug_fxn
    def _can_undo(self):
        """Is there an action to undo back in history?

        Returns:
            bool: True if can undo
        """
        return self.history_node_i > 0

    @debug_fxn
    def _can_redo(self):
        """Is there an action to redo next in history?

        Returns:
            bool: True if can redo
        """
        return self.history_node_i < (len(self.history_nodes) - 1)

    @debug_fxn
    def _update_menu_items(self):
        """Update the Enabled/Disabled quality of Undo, Redo Menu items
        """
        if self.save_menu_item is not None:
            self.save_menu_item.Enable(not self.is_saved())

        if self.undo_menu_item is not None:
            self.undo_menu_item.Enable(self._can_undo())
            if self._can_undo():
                key_accel = self.undo_menu_item.GetItemLabel().split('\t')[1]
                undo_descrip = self.history_edges[self.history_node_i - 1]['description']
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
                undo_descrip = self.history_edges[self.history_node_i]['description']
                self.redo_menu_item.SetItemLabel(
                        "Redo " + undo_descrip + "\t" + key_accel
                        )
            else:
                key_accel = self.redo_menu_item.GetItemLabel().split('\t')[1]
                self.redo_menu_item.SetItemLabel(
                        "Redo\t" + key_accel
                        )

    @debug_fxn
    def register_save_menu_item(self, save_menu_item):
        """Give this class instance the Save menu item instance so it can
        Enable and Disable menu item on its own

        Save is disabled if currently we are in a saved state.

        Args:
            undo_menu_item (wx.MenuItem): menu item instance for Undo
        """
        self.save_menu_item = save_menu_item
        self._update_menu_items()

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
        for filename in filenames:
            # Open new frame or put image in existing blank frame
            self.window_target.parent.open_image(filename)
            # log it
            LOGGER.info("MSC:Drag and Drop filename:\n    %s", repr(filename))

        # True to accept data, False to veto
        # Just return True all the time, we'll sort it out internally.
        return True


class ImageAutoContrastDialog(wx.Dialog):
    """Dialog to ask user for level of Auto-Contrast (0 through 20) desired.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, title="Image Auto-Contrast", **kwargs)

        starting_val = 0

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Slider Value Display
        # Find text width of "999", large enough to show 0 through 20
        text_width_px = common.get_text_width_px(self, "999")
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

    def on_evt_slider(self, _evt):
        """When Slider is changed, change label showing value.

        Args:
            _evt (wx.): TODO
        """
        slider_val = self.slider.GetValue()
        self.value_display.SetLabel("%d"%slider_val)


class ImageFalseColorDialog(wx.Dialog):
    """Dialog to ask user which colormap for False Color desired.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, title="Image False Color", **kwargs)

        self.cmap_choices = ['Viridis', 'Plasma', 'Magma', 'Inferno']

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(10)
        # Choice widget selects one of many string options
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

    def get_colormap(self):
        """Return lower-case canonical colormap string that was selected.
        """
        return self.cmap_choices[self.colormap_choice.GetSelection()].lower()


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
        self.html.LoadURL((const.ICON_DIR / help_filename).as_uri())

        self.SetTitle("Marcam Help")
        self.SetSize((500, 600))


class FrameList():
    """Manager for all top-level Frames in Marcam App.
    """
    @debug_fxn
    def __init__(self):
        # index dict by ID, as we use this most often
        self.frame_dict = collections.OrderedDict()
        self.is_handling_window_menu = False

    @debug_fxn
    def active_frame(self):
        """Return the frame in FrameList that is currently active.

        Returns:
            (None or wx.Frame): None if no frame is active, or the wx.Frame
                that is currently active.
        """
        # If we never find an active frame, return None.
        #   Can happen if Modal Dialog is present on current frame.
        return_frame = None

        # Search all frames for an active one.
        for frame_id in self.frame_dict:
            if self.frame_dict[frame_id]['frame'].IsActive():
                return_frame = self.frame_dict[frame_id]['frame']
                break
        return return_frame

    @debug_fxn
    def frame_with_file(self, img_file):
        """Return the frame in FrameList that has img_file inside it.

        Args:
            img_file (pathlib.Path): full path to img_file to check Frame for.

        Returns:
            (None or wx.Frame): None if no frame contains file, or the wx.Frame
                that is currently contains the file.
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
            for (i, menuitem_frame_id) in enumerate(self.frame_dict.keys()):
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
        self.update_window_menu()

    @debug_fxn
    def register_window_menu(self, frame_inst, window_menu):
        """Add another Frame's Window menu to the menus this class manages.

        Args:
            frame_inst: Frame object containing the menu.
            window_menu: Menu object that is the "Window" menu of Frame.
        """
        # init to empty dict if not already
        self.frame_dict.setdefault(frame_inst.GetId(), {})
        self.frame_dict[frame_inst.GetId()]['menu'] = window_menu
        self.frame_dict[frame_inst.GetId()]['menu_origcount'] = window_menu.GetMenuItemCount()
        self.is_handling_window_menu = True

    @debug_fxn
    def get_list_copy(self):
        """Get a copy of the list of frame object instances.
        """
        return [self.frame_dict[id]['frame'] for id in self.frame_dict]
