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

import logging
import os
import os.path
import tempfile
import zipfile

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


@debug_fxn
def is_valid(image_path):
    """Detect if this image is readable by this program.

    Detects any readable .mcm file.
    """
    if zipfile.is_zipfile(image_path):
        # for .mcm files
        # verify internals of zipfile
        try:
            with zipfile.Zipfile(image_path) as mcm_file:
                with mcm_file.open('image.png') as png_file:
                    no_log = wx.LogNull()
                    img_ok = wx.Image.CanRead(png_file)
                    # re-enable logging
                    del no_log
        except zipfile.BadZipFile:
            img_ok = False
    else:
        img_ok = False

    return img_ok

@debug_fxn
def load(imdata_path):
    """Load native app .mcm file

    Args:
        imdata_path (str): path to .mcm file to open
    """
    # init img_ok to False in case we don't load image
    img_ok = False

    # first load image from zip
    try:
        with zipfile.ZipFile(imdata_path, 'r') as container_fh:
            namelist = container_fh.namelist()
            for name in namelist:
                if name.startswith("image."):
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
    except IOError:
        # TODO: need real error dialog
        LOGGER.warning(
                "Cannot open data in file '%s'.", imdata_path,
                exc_info=True
                )

    # img_ok will only be True if we successfully loaded file
    if img_ok:
        return (img, marks, img_name)
    else:
        return None

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

    current_img = image_proc.memorydc2image(self.img_panel.img_dc)
    current_img.SaveFile(temp_img, wx.BITMAP_TYPE_PNG)
    temp_img.close()

    #if isinstance(self.img_path, str):
    #    # pathname for plain image file
    #    with open(self.img_path, 'rb') as img_fh:
    #        temp_img.write(img_fh.read())
    #else:
    #    # mcm zipfile component image file
    #    with zipfile.ZipFile(self.img_path[0], 'r') as container_fh:
    #        temp_img.write(container_fh.open(self.img_path[1]).read())
    #temp_img.close()

    ## get archive name for image in zip
    #if isinstance(self.img_path, str):
    #    (_, imgfile_ext) = os.path.splitext(self.img_path)
    #    img_arcname = "image" + imgfile_ext
    #else:
    #    img_arcname = self.img_path[1]

    img_arcname = "image.png"
    markdata_name = "marks.txt"

    # write new save file
    try:
        with zipfile.ZipFile(imdata_path, 'w') as container_fh:
            container_fh.write(temp_img_name, arcname=img_arcname)
            container_fh.writestr(
                    markdata_name,
                    json.dumps(self.img_panel.marks, separators=(',', ':'))
                    )
    except IOError:
        # TODO: need real error dialog
        LOGGER.warning("Cannot save current data in file '%s'.", imdata_path)
        returnval = None
    else:
        returnval = (img_arcname, markdata_name)
    finally:
        os.unlink(temp_img_name)

    return returnval
