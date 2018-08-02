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

import json
import logging
import os
import os.path
import tempfile
import zipfile

import wx

import common


# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug)


MCM_VERSION = '1.0.0'
MCM_IMAGE_NAME = 'image.png'
MCM_INFO_NAME = 'info.json'


class McmFileError(Exception):
    pass


@debug_fxn
def is_valid(mcm_path):
    """Detect if this image is readable by this program.

    Detects any readable .mcm file.
    """
    if zipfile.is_zipfile(mcm_path):
        # for .mcm files
        # verify internals of zipfile
        try:
            tmp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(mcm_path) as mcm_file:
                image_name = [
                        x for x in container_fh.namelist() if x.startswith(MCM_IMAGE_NAME)
                        ][0]
                mcm_file.extract(image_name, tmp_dir)
                no_log = wx.LogNull()
                img_ok = wx.Image.CanRead(os.path.join(tmp_dir, image_name))
                # re-enable logging
                del no_log
        except zipfile.BadZipFile:
            img_ok = False
        finally:
            # remove temp dir
            os.remove(os.path.join(tmp_dir, name))
            os.rmdir(tmp_dir)
    else:
        img_ok = False

    return img_ok

@debug_fxn
def load(imdata_path):
    """Load native app .mcm file

    Args:
        imdata_path (str): path to .mcm file to open
    """
    # legacy marks file name
    marks_file_name = 'marks.txt'
    # init img_ok to False in case we don't load image
    img_ok = False

    # first load image from zip
    try:
        with zipfile.ZipFile(imdata_path, 'r') as container_fh:
            with container_fh.open(MCM_INFO_NAME, 'r') as info_fh:
                info = json.load(info.fh)

            namelist = container_fh.namelist()
            for name in namelist:
                if name.startswith("image."):
                    # TODO: we need to remove tempdir
                    tmp_dir = tempfile.mkdtemp()
                    container_fh.extract(name, tmp_dir)

                    if name.endswith(".1sc"):
                        img = file1sc_to_image(os.path.join(tmp_dir, name))
                    else:
                        # disable logging, we don't care if there is e.g. TIFF image
                        #   with unknown fields
                        # TODO: could also just raise loglevel to Error and above
                        no_log = wx.LogNull()

                        img = wx.Image(os.path.join(tmp_dir, name))

                        # re-enable logging
                        del no_log
                    # check if img loaded ok
                    img_ok = img.IsOk()
                    img_name = name

                    # remove temp dir
                    os.remove(os.path.join(tmp_dir, name))
                    os.rmdir(tmp_dir)

                if name == "marks.txt":
                    with container_fh.open(name, 'r') as json_fh:
                        marks = json.load(json_fh)
                    marks = [tuple(x) for x in marks]
    except (zipfile.BadZipFile, OSError) as err:
        LOGGER.warning(
                "Cannot open data in file '%s': %s", imdata_path, err,
                exc_info=True
                )
        raise McmFileError

    # need: img, img_name, marks

    if img_ok:
        return (img, marks, img_name)
    else:
        return (None, None, None)


@debug_fxn
def save(imdata_path, img, marks):
    """Save image and mark locations to .mcm zipfile

    Args:
        imdata_path (str): full path to filename to save to
    """
    # make temp file for image file
    #   must make actual file for use with zipfile
    (temp_img_fd, temp_img_name) = tempfile.mkstemp()
    temp_img = os.fdopen(temp_img_fd, mode='wb')

    # copy source image into temp file
    # self.img_path: path to image we originally loaded
    # self.save_filepath: path to mcm file we've saved
    # self.img_panel.img_dc: max-res image data MemoryDC

    img.SaveFile(temp_img, wx.BITMAP_TYPE_PNG)
    temp_img.close()

    mcm_info = {
            'mcm_version':MCM_VERSION,
            'mcm_image_name':MCM_IMAGE_NAME,
            'mcm_info_name':MCM_INFO_NAME,
            'marks':marks
            }
    # write new save file
    try:
        with zipfile.ZipFile(imdata_path, 'w') as container_fh:
            # write image file to archive
            container_fh.write(temp_img_name, arcname=MCM_IMAGE_NAME)
            # write json text file to archive
            container_fh.writestr(
                    MCM_INFO_NAME,
                    json.dumps(mcm_info)
                    )
    except IOError:
        # TODO: need real error dialog
        LOGGER.warning("Cannot save current data in file '%s'.", imdata_path)
        returnval = None
    else:
        # TODO: do we really want these return values?
        returnval = (MCM_IMAGE_NAME, MCM_INFO_NAME)
    finally:
        # remove temp file
        os.unlink(temp_img_name)

    return returnval
