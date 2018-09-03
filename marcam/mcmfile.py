"""mcmfile: functions to read, write, manipulate Marcam .mcm files
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

import io
import json
import logging
import os
import pathlib
import shutil
import tempfile
import zipfile

import wx

import common
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


# for new files
MCM_VERSION = '1.0.0'
MCM_IMAGE_NAME = 'image.png'
MCM_INFO_NAME = 'info.json'

MCM_LEGACY_IMAGE_PREFIX = 'image.'

class McmFileError(Exception):
    """Any mcm-specific file error.
    """
    pass


@debug_fxn
def image_readable_fh(image_fh):
    """Check if wx.Image can read this file without making error dialog

    Args:
        image_fh (filehandle): filehandle of image stream to check for
            readability

    Returns:
        bool: True if image was readable by wx.Image
    """
    no_log = wx.LogNull()
    img_ok = wx.Image.CanRead(image_fh)
    # re-enable logging
    del no_log
    return img_ok

@debug_fxn
def image_readable(image_path):
    """Check if wx.Image can read this file without making error dialog

    Args:
        image_path (pathlike): path of image to check for readability

    Returns:
        bool: True if image was readable by wx.Image
    """
    no_log = wx.LogNull()
    img_ok = wx.Image.CanRead(str(image_path))
    # re-enable logging
    del no_log
    return img_ok

@debug_fxn
def read_image_fh(image_fh):
    """wx.Image read from file, with wx errror logging turned off.

    Args:
        image_fh (filehandle): filehandle of image stream to read

    Returns:
        wx.Image: wx Image object read from file
    """
    # disable logging, we don't care if there is e.g. TIFF image
    #   with unknown fields
    no_log = wx.LogNull()
    img = wx.Image(image_fh)
    # re-enable logging
    del no_log

    return img

@debug_fxn
def read_image(image_path):
    """wx.Image read from file, with wx errror logging turned off.

    Args:
        image_path (pathlike): path of image to read

    Returns:
        wx.Image: wx Image object read from file
    """
    # disable logging, we don't care if there is e.g. TIFF image
    #   with unknown fields
    no_log = wx.LogNull()
    img = wx.Image(str(image_path))
    # re-enable logging
    del no_log

    return img

@debug_fxn
def is_legacy_mcm_file(mcm_path):
    """Determine if this is a legacy mcm file (different format).

    Args:
        mcm_path (pathlike): path of mcm file to check if legacy

    Returns:
        bool: True if file is a legacy mcm file
    """
    try:
        with zipfile.ZipFile(str(mcm_path)) as mcm_container:
            legacy_mcm = MCM_INFO_NAME not in mcm_container.namelist()
    except (zipfile.BadZipFile, OSError):
        #raise McmFileError
        return False
    return legacy_mcm

@debug_fxn
def is_valid(mcm_path):
    """Detect if this image is readable by this program.

    Detects any readable .mcm file.

    Args:
        mcm_path (pathlike): path of mcm file to check if valid

    Returns:
        bool: True if file is a valid mcm file
    """
    # if legacy file use legacy file function
    if is_legacy_mcm_file(mcm_path):
        # Actually try and load file.  This is slow, but hopefully we
        #   won't often need to test legacy files.
        file_ok = (legacy_load(mcm_path) != (None, None, None))
        return file_ok

    # Modern MCM (version > 1.0)
    if zipfile.is_zipfile(str(mcm_path)):
        # for .mcm files
        # verify internals of zipfile
        try:
            with zipfile.ZipFile(str(mcm_path), 'r') as container_fh:
                with container_fh.open(MCM_INFO_NAME, 'r') as info_fh:
                    info = json.load(info_fh)

                marks_ok = info.get('marks', None) is not None
                image_name = info['mcm_image_name']

                png_mem_file = io.BytesIO()
                with container_fh.open(image_name, 'r') as img_fh:
                    png_mem_file.write(img_fh.read())
                png_mem_file.seek(0)

                # check if img is readable
                img_ok = image_readable_fh(png_mem_file)

                mcm_ok = img_ok and marks_ok

        except zipfile.BadZipFile:
            mcm_ok = False
    else:
        mcm_ok = False

    return mcm_ok

@debug_fxn
def load(imdata_path):
    """Load native app .mcm file

    Args:
        imdata_path (pathlike): path to .mcm file to open

    Returns:
        (wx.Image, list, str): (wx Image, list of mark coordinates, image name)
    """
    # Using BytesIO is almost 20% faster on a large image than using tempfile
    #   in one test (iMac, Fusion Drive)  (Average 375ms vs. 461ms)

    raise_mcm_file_error = False
    # init img_ok to False in case we don't load image
    img_ok = False

    # if legacy file use legacy file function
    if is_legacy_mcm_file(imdata_path):
        return legacy_load(imdata_path)

    # Modern MCM (version > 1.0)
    # first load image from zip
    try:
        with zipfile.ZipFile(str(imdata_path), 'r') as container_fh:
            with container_fh.open(MCM_INFO_NAME, 'r') as info_fh:
                info = json.load(info_fh)

            marks = info['marks']
            image_name = info['mcm_image_name']

            png_mem_file = io.BytesIO()
            with container_fh.open(image_name, 'r') as img_fh:
                png_mem_file.write(img_fh.read())
            png_mem_file.seek(0)
            img = read_image_fh(png_mem_file)

            # check if img loaded ok
            img_ok = img.IsOk()

    except (zipfile.BadZipFile, OSError) as err:
        LOGGER.warning(
                "Cannot open data in file '%s': %s", imdata_path, err,
                exc_info=True
                )
        raise_mcm_file_error = True

    if raise_mcm_file_error:
        # Do this here so this raise allows the finally above to execute
        raise McmFileError

    # error return
    if not img_ok:
        return (None, None, None)

    # make sure marks coordinates are tuples
    marks = [tuple(x) for x in marks]

    print("Elapsed time: %.1fms"%((time.time()-time_start)*1000))
    return (img, marks, image_name)


@debug_fxn
def save(imdata_path, img, marks):
    """Save image and mark locations to .mcm zipfile

    Args:
        imdata_path (pathlike): full path to filename to save to

    Returns:
        bool: whether save was successful, True or False
    """
    # In-memory filehandle to save PNG data to from Image
    png_mem_file = io.BytesIO()
    img.SaveFile(png_mem_file, wx.BITMAP_TYPE_PNG)
    png_mem_file.seek(0)

    mcm_info = {
            'mcm_version':MCM_VERSION,
            'mcm_image_name':MCM_IMAGE_NAME,
            'mcm_info_name':MCM_INFO_NAME,
            'marks':marks
            }
    # write new save file
    try:
        with zipfile.ZipFile(str(imdata_path), 'w') as container_fh:
            # write image file data to archive
            container_fh.writestr(MCM_IMAGE_NAME, png_mem_file.read())
            # write json text file to archive
            container_fh.writestr(
                    MCM_INFO_NAME,
                    json.dumps(mcm_info)
                    )
    except OSError:
        LOGGER.warning("Cannot save current data in file '%s'.", imdata_path)
        returnval = False
    else:
        returnval = True

    return returnval


@debug_fxn
def legacy_load(imdata_path):
    """For old mcm files only (before they contained 'info.json')

    Load legacy app .mcm file

    Args:
        imdata_path (pathlike): path to .mcm file to open

    Returns:
        (wx.Image, list, str): (wx Image, list of mark coordinates, image name)
    """
    # init img_ok to False in case we don't load image
    img_ok = False

    # first load image from zip
    try:
        with zipfile.ZipFile(str(imdata_path), 'r') as container_fh:
            namelist = container_fh.namelist()
            for name in namelist:
                if name.startswith(MCM_LEGACY_IMAGE_PREFIX):
                    tmp_dir_path = pathlib.Path(tempfile.mkdtemp())
                    container_fh.extract(name, str(tmp_dir_path))

                    if name.endswith(".1sc"):
                        img = image_proc.file1sc_to_image(tmp_dir_path / name)
                    else:
                        # disable logging, we don't care if there is e.g. TIFF image
                        #   with unknown fields
                        no_log = wx.LogNull()

                        img = wx.Image(str(tmp_dir_path / name))

                        # re-enable logging
                        del no_log
                    # check if img loaded ok
                    img_ok = img.IsOk()
                    img_name = name

                    # remove temp dir
                    (tmp_dir_path / name).unlink()
                    tmp_dir_path.rmdir()

                if name == "marks.txt":
                    with container_fh.open(name, 'r') as json_fh:
                        marks = json.load(json_fh)
                    marks = [tuple(x) for x in marks]
    except OSError:
        img_ok = False
        LOGGER.warning(
                "Cannot open data in file '%s'.", imdata_path,
                exc_info=True
                )
    # error return
    if not img_ok:
        return (None, None, None)

    # make sure marks coordinates are tuples
    marks = [tuple(x) for x in marks]

    return (img, marks, img_name)
