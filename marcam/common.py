"""Common functions used by multiple modules
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

import builtins # for MarcamRepr
import logging
import reprlib
import threading

import wx


# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


# Stores global depth for debug_fxn's in all modules
#   (e.g. debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE))
DEBUG_FXN_STATE = {}

class MarcamRepr(reprlib.Repr):
    def __init__(self):
        super().__init__()
        # Defaults of reprlib.Repr
        #self.maxlevel = 6      self.maxtuple = 6       self.maxlist = 6
        #self.maxarray = 5      self.maxdict = 4        self.maxset = 6
        #self.maxfrozenset = 6  self.maxdeque = 6       self.maxstring = 30
        #self.maxlong = 40      self.maxother = 30
        self.maxtuple = 12
        self.maxlist = 12
        self.maxdict = 12
        self.maxstring = 80
        self.maxother = 80
        self.maxbytes = 80

    def repr_bytes(self, x, level):
        """For bytes object type

        Stock method used for bytes had first step 'repr(x)' which was
            way too slow.

        Using repr_str from python source as a template.
        """
        str_rep = builtins.repr(x[:self.maxbytes])
        if len(str_rep) > self.maxbytes:
            i = max(0, (self.maxbytes-3)//2)
            j = max(0, self.maxbytes-3-i)
            str_rep = builtins.repr(x[:i] + x[len(x)-j:])
            str_rep = str_rep[:i] + '...' + str_rep[len(str_rep)-j:]
        return str_rep


q_repr = MarcamRepr()


def debug_fxn_factory(logger_fxn):
    """Factory to produce debug_fxn that logs to specified logger object

    Args:
        logger_fxn (logging.Logger.{info,debug,warning,error): Logger function
            send info msgs to.  Typically logging.Logger.info
    """
    # Use module-level DEBUG_FXN_STATE, so state is shared among all modules
    #   that instance this module, and not local to every
    #   instanced debug_fxn_factory.

    # debug decorator that announces function call/entry and lists args
    def debug_fxn_(func):
        """Function decorator that prints the function name and the arguments
        used in the function call before executing the function
        """
        def func_wrapper(*args, **kwargs):
            thread_name = threading.current_thread().name
            DEBUG_FXN_STATE[thread_name] = DEBUG_FXN_STATE.setdefault(thread_name, 0) + 1
            fxn_depth = DEBUG_FXN_STATE[thread_name]
            log_string = "FXN%s%d: %s.%s(\n"%(
                    "" if thread_name == 'MainThread' else "%s."%thread_name,
                    fxn_depth, func.__module__, func.__qualname__
                    )

            for arg in args:
                log_string += "    " + q_repr.repr(arg) + ",\n"
            for key in kwargs:
                log_string += "    " + key + "=" + q_repr.repr(kwargs[key]) + ",\n"
            log_string += "    )"
            logger_fxn(log_string)
            return_vals = func(*args, **kwargs)
            logger_fxn(
                    "<--FXN%s%d: %s.%s\n   RETURNS: %s",
                    "" if thread_name == 'MainThread' else "%s."%thread_name,
                    fxn_depth, func.__module__, func.__qualname__,
                    q_repr.repr(return_vals)
                    )
            DEBUG_FXN_STATE[thread_name] -= 1
            return return_vals
        return func_wrapper

    return debug_fxn_


# create debug function using this file's logger
debug_fxn = debug_fxn_factory(LOGGER.info)
debug_fxn_debug = debug_fxn_factory(LOGGER.debug)


def floor(num):
    """Simple numerical ceiling function.

    Args:
        num (float): input number

    Returns:
        int: next lowest integer if num is non-integer, else: num
    """
    if int(num) > num:
        # num is negative float
        # e.g. int(-2.5) = -2
        return int(num) - 1
    else:
        # num is integer, or num is positive float
        # e.g. int(2.0) = 2
        # e.g. int(2.5) = 2
        return int(num)

def ceil(num):
    """Simple numerical ceiling function.

    Args:
        num (float): input number

    Returns:
        int: next highest integer if num is non-integer, else: num
    """
    if int(num) < num:
        # num is positive float
        # e.g. int(2.5) = 2
        return int(num) + 1
    else:
        # num is integer, or num is negative float
        # e.g. int(2.0) = 2
        # e.g. int(-2.5) = -2
        return int(num)

def clip(num, num_min=None, num_max=None):
    """Clip to max and/or min values.  To not use limit, give argument None

    Args:
        num (float): input number
        num_min (float): minimum value, if less than this return this num
            Use None to designate no minimum value.
        num_max (float): maximum value, if more than this return this num
            Use None to designate no maximum value.

    Returns
        float: clipped version of input number
    """
    if num_min is not None and num_max is not None:
        return min(max(num, num_min), num_max)
    elif num_min is not None:
        return max(num, num_min)
    elif num_max is not None:
        return min(num, num_max)
    else:
        return num

@debug_fxn
def get_text_width_px(window, text_str):
    """Using window settings, find width in pixels of a text str.

    Args:
        window (wx.Window): Window to contain string using default font
        text_str (str): string to find the width of

    Returns:
        (int) width of text_str in pixels in the given window
    """
    # get width in pixels of the given font
    screen_dc = wx.ScreenDC()
    screen_dc.SetFont(window.GetFont())
    (text_width_px, _) = screen_dc.GetTextExtent(text_str)
    del screen_dc

    # add horizontal margins if present
    try:
        margins = window.GetMargins()
    except AttributeError:
        margins = wx.Point(-1, -1)
    if margins.x > 0:
        text_width_px = text_width_px + margins.x * 2

    return text_width_px

def on_evt_debug(evt):
    """
    Debugging for events: print all info and Skip

    Args:
        evt (wx.Event): any Event
    """
    # Resume normal Event Processing after this method returns
    evt.Skip()

    debug_print_evt_info(evt)

# global dicts to decode numbers to constants
EVT_TYPES = {}
for item in dir(wx):
    if item.startswith("wxEVT_"):
        EVT_TYPES[getattr(wx, item)] = item[2:]
EVT_CATEGORIES = {}
for item in dir(wx):
    if item.startswith("EVT_CATEGORY_"):
        EVT_CATEGORIES[getattr(wx, item)] = item

def debug_print_evt_info(evt):
    """Print debug info concerning an event

    Args:
        evt: Any wx Event
    """
    print("Event")
    print("    Type: %s (%d)"%(EVT_TYPES.get(evt.GetEventType(), ""), evt.GetEventType()))
    print("    Category: %s (%d)"%(
                EVT_CATEGORIES.get(evt.GetEventCategory(), ""),
                evt.GetEventCategory()
                )
            )
    print("    EventObject: " + repr(evt.GetEventObject()))
    print("    ID: " + repr(evt.GetId()))
    print("    RefData: " + repr(evt.GetRefData()))
    print("    ClassInfo:")
    print("        BaseClassName1: " + repr(evt.GetClassInfo().GetBaseClassName1()))
    print("        BaseClassName2: " + repr(evt.GetClassInfo().GetBaseClassName2()))
    print("        ClassName: " + repr(evt.GetClassInfo().GetClassName()))
    print("    ClassName: " + repr(evt.GetClassName()))
    print("    Timestamp: " + repr(evt.GetTimestamp()))
