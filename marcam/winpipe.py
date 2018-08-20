#!/usr/bin/env python3

# original from:
# https://stackoverflow.com/questions/48542644/python-and-windows-named-pipes

import logging
import time
import sys
import win32pipe, win32file
#import win32security

import common

# https://docs.microsoft.com/en-us/windows/desktop/ipc/named-pipes
# https://docs.microsoft.com/en-us/windows/desktop/ipc/pipe-names
# https://docs.microsoft.com/en-us/windows/desktop/api/Winbase/nf-winbase-createnamedpipea
# http://timgolden.me.uk/pywin32-docs/win32pipe.html
# http://timgolden.me.uk/pywin32-docs/win32file.html

# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug, common.DEBUG_FXN_STATE)


# constant not defined by win32pipe
PIPE_REJECT_REMOTE_CLIENTS = 8


@debug_fxn
def create_named_pipe(pipe_name):
    pipe = win32pipe.CreateNamedPipe(
            # lpName
            # ----------
            # Unicode name of pipe.
            # Use the following form when specifying the name of a pipe in the
            # CreateFile, WaitNamedPipe, or CallNamedPipe function:
            #   \\ServerName\pipe\PipeName
            # where ServerName is either the name of a remote computer or a
            # period, to specify the local computer.  The pipe name string
            # specified by PipeName can include any character other than a
            # backslash, including numbers and special characters. The entire
            # pipe name string can be up to 256 characters long. Pipe names are
            # not case-sensitive.
            # The pipe server cannot create a pipe on another computer, so
            # CreateNamedPipe must use a period for the server name, as shown
            # in the following example.
            #   \\.\pipe\PipeName
            pipe_name,
            # dwOpenMode
            # ----------
            # can be one of:
            #   PIPE_ACCESS_DUPLEX, PIPE_ACCESS_INBOUND, PIPE_ACCESS_OUTBOUND
            win32pipe.PIPE_ACCESS_INBOUND,
            # dwPipeMode
            # ----------
            # can be one of:
            #   PIPE_TYPE_MESSAGE, PIPE_TYPE_BYTE,
            # additionally can have one of:
            #   PIPE_READMODE_MESSAGE, PIPE_READMODE_BYTE
            # additionally can have one of:
            #   PIPE_WAIT, PIPE_NOWAIT
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_BYTE \
                    | win32pipe.PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
            # nMaxInstances
            # -------------
            1,
            # nOutBufferSize
            # -------------
            65536,
            # nInBufferSize
            # -------------
            65536,
            # nDefaultTimeOut
            # ---------------
            # in milliseconds. 0 means "50 ms"
            0,
            # lpSecurity Attributes
            # ---------------------
            # can be PySECURITY_ATTRIBUTES, containing PySECURITY_DESCRIPTOR,
            #   to set pipe security for both client and server
            None
            )
    return pipe

@debug_fxn
def connect_and_wait(pipe):
    """Wait for a client connection, do not return until one is found.

    Assumes create_named_pipe used PIPE_WAIT mode.
    """
    try:
        win32pipe.ConnectNamedPipe(pipe, None)
    except win32file.error as e:
        (winerror, funcname, strerror) = e.args
        LOGGER.error("Windows error:\n    %s\n   %s\n    %s",
                winerror, funcname, strerror
                )
        raise

@debug_fxn
def client_connect_to_pipe(pipe_name):
    try:
        handle = win32file.CreateFile(
            pipe_name,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
    except win32file.error as e:
        (winerror, funcname, strerror) = e.args
        LOGGER.error("Windows error:\n    %s\n   %s\n    %s",
                winerror, funcname, strerror
                )
        raise

    return handle

@debug_fxn
def pipe_read(pipe):
    (hr, resp_bytes) = win32file.ReadFile(pipe, 64*1024)
    resp_str = resp_bytes.decode(encoding='utf-8')
    return resp_str

@debug_fxn
def pipe_server(pipe_name):
    print("pipe server")
    client_done = False

    pipe = create_named_pipe(pipe_name)
    print("waiting for client")
    connect_and_wait(pipe)
    print("got client")

    while not client_done:
        try:
            resp_str = pipe_read(pipe)
            print(f"message: {resp_str}")
        except win32file.error as e:
            (winerror, funcname, strerror) = e.args
            if winerror == 109:
                print("Client closed access to pipe.")
                print("    {0}".format(winerror))
                print("    {0}".format(funcname))
                print("    {0}".format(strerror))
                client_done = True
            else:
                LOGGER.error("Windows error:\n    %s\n   %s\n    %s",
                        winerror, funcname, strerror
                        )
                client_done = True
                raise
        finally:
            if client_done:
                win32file.CloseHandle(pipe)

    print("finished now")

@debug_fxn
def pipe_client(pipe_name):
    print("pipe client")
    quit = False

    try:
        handle = client_connect_to_pipe(pipe_name)
    except win32file.error as e:
        (winerror, funcname, strerror) = e.args
        if winerror==2:
            print("No pipe server.")
            return
        else:
            raise

    print("Connected to pipe.")

    while not quit:
        try:
            for count in range(5):
                some_data = f"count: {count}".encode(encoding='utf-8')
                win32file.WriteFile(
                        # handle to Named Pipe
                        handle,
                        # data in bytes format
                        some_data
                        )
                time.sleep(1)
            quit = True
        except win32file.error as e:
            (winerror, funcname, strerror) = e.args
            if winerror == 2:
                # ERROR_FILE_NOT_FOUND
                #   The system cannot find the file specified
                print("no pipe, trying again in a sec")
                print("    {0}".format(winerror))
                print("    {0}".format(funcname))
                print("    {0}".format(strerror))
                time.sleep(1)
            elif winerror == 109:
                # ERROR_BROKEN_PIPE
                #   The pipe has been ended.
                print("broken pipe, bye bye")
                print("    {0}".format(winerror))
                print("    {0}".format(funcname))
                print("    {0}".format(strerror))
                quit = True
            elif winerror == 232:
                # ERROR_NO_DATA
                #   The pipe is being closed.
                print("broken pipe, bye bye")
                print("    {0}".format(winerror))
                print("    {0}".format(funcname))
                print("    {0}".format(strerror))
                quit = True
            else:
                print("Windows error:")
                print("    {0}".format(winerror))
                print("    {0}".format(funcname))
                print("    {0}".format(strerror))


if __name__ == '__main__':
    pipe_name = r'\\.\pipe\Marcam-username'

    if len(sys.argv) < 2:
        print("need s or c as argument")
    elif sys.argv[1] == "s":
        pipe_server(pipe_name)
    elif sys.argv[1] == "c":
        pipe_client(pipe_name)
    else:
        print(f"no can do: {sys.argv[1]}")

