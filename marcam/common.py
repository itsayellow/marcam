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

def debug_fxn_factory(logger_fxn):
    """Factory to produce debug_fxn that logs to specified logger object

    Args:
        logger_fxn (logging.Logger.{info,debug,warning,error): Logger function
            send info msgs to.  Typically logging.Logger.info
    """

    # debug decorator that announces function call/entry and lists args
    def debug_fxn(func):
        """Function decorator that prints the function name and the arguments used
        in the function call before executing the function
        """
        # store initial depth attribute
        # TODO: consider using logger_fxn.marcam_depth instead of debug_fxn.depth?
        #       If this is allowed, depth can be global across all modules.
        debug_fxn.depth = 0
        def func_wrapper(*args, **kwargs):
            debug_fxn.depth += 1
            log_string = "FXN%d: %s.%s(\n"%(debug_fxn.depth, func.__module__, func.__qualname__)
            for arg in args[1:]:
                log_string += "    " + repr(arg) + ",\n"
            for key in kwargs:
                log_string += "    " + key + "=" + repr(kwargs[key]) + ",\n"
            log_string += "    )"
            logger_fxn(log_string)
            return_vals = func(*args, **kwargs)
            debug_fxn.depth -= 1
            return return_vals
        return func_wrapper

    return debug_fxn

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
