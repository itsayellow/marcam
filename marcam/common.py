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
        debug_fxn.depth = 0
        def func_wrapper(*args, **kwargs):
            # TODO: for depth, possibly a function attribute to remember
            #   depth across function calls?
            debug_fxn.depth += 1
            log_string = "FXN%d:"%debug_fxn.depth + func.__qualname__ + "(\n"
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
