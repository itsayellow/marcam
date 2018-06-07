"""Common functions used by multiple modules
"""

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
        def func_wrapper(*args, **kwargs):
            log_string = "FXN:" + func.__qualname__ + "(\n"
            for arg in args[1:]:
                log_string += "    " + repr(arg) + ",\n"
            for key in kwargs:
                log_string += "    " + key + "=" + repr(kwargs[key]) + ",\n"
            log_string += "    )"
            logger_fxn(log_string)
            return func(*args, **kwargs)
        return func_wrapper

    return debug_fxn
