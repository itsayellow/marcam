"""Image Processing: image manipulation and image info routines
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
import time

import wx
import numpy as np
import PIL.Image
import PIL.ImageStat
import PIL.ImageOps

import common
import colormaps

# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug)

# TODO: may want to use threads for some time-consuming operations

#-----------------------
# Image data conversions

@debug_fxn
def image2memorydc(in_image, white_bg=False):
    """Converts wx.Image to wx.MemoryDC
    """
    # Create MemoryDC to return
    image_dc = wx.MemoryDC()
    # convert image to bitmap
    img_bmp = wx.Bitmap(in_image)
    if white_bg:
        # make white image of same size
        bg_img = wx.Image(in_image.GetWidth(), in_image.GetHeight())
        bg_img.Clear(value=b'\xff')
        bg_bmp = wx.Bitmap(bg_img)
        # use image_dc to draw onto bg_bmp
        image_dc.SelectObject(bg_bmp)
        image_dc.DrawBitmap(img_bmp, 0, 0)
    else:
        image_dc.SelectObject(img_bmp)

    return image_dc

@debug_fxn
def wximagedc2pilimage(wx_imagedc):
    wx_bitmap = wx_imagedc.GetAsBitmap()
    return wxbitmap2pilimage(wx_bitmap)

@debug_fxn
def wxbitmap2pilimage(wx_bitmap):
    wx_image = wx_bitmap.ConvertToImage()
    return wximage2pilimage(wx_image)

@debug_fxn
def wximage2pilimage(wx_image):
    image_data = wx_image.GetData()
    #pil_image = PIL.Image.new('RGB', (wx_image.GetWidth(), wx_image.GetHeight()))
    pil_image = PIL.Image.frombytes(
            'RGB',
            (wx_image.GetWidth(), wx_image.GetHeight()),
            bytes(image_data)
            )
    return pil_image

@debug_fxn
def pilimage2wximage(pil_image):
    (width, height) = pil_image.size
    pil_image_data = pil_image.tobytes()
    wx_image = wx.Image(width, height, pil_image_data)
    return wx_image

#-----------------------
# Image processing

@debug_fxn
def image_invert(img_dc):
    pil_image = wximagedc2pilimage(img_dc)
    new_pil_image = PIL.ImageOps.invert(pil_image)
    wx_image = pilimage2wximage(new_pil_image)
    return wx_image

@debug_fxn
def image_autocontrast(img_dc):
    pil_image = wximagedc2pilimage(img_dc)
    new_pil_image = PIL.ImageOps.autocontrast(pil_image)
    wx_image = pilimage2wximage(new_pil_image)
    return wx_image

def image_remap_colormap(img_dc):
    wx_bitmap = img_dc.GetAsBitmap()
    wx_image = wx_bitmap.ConvertToImage()
    width = wx_image.GetWidth()
    height = wx_image.GetHeight()

    image_data = wx_image.GetData()
    new_image_data = [
            colormaps.VIRIDIS_DATA_24BIT[int(x)] for x in image_data[::3]
            ]
    # flatten new_image_data which is now a list of triples
    new_image_data = bytearray(
            [x for sublist in new_image_data for x in sublist]
            )
    wx_image = wx.Image(width, height, new_image_data)
    return wx_image

#-----------------------
# Image information

@debug_fxn
def get_image_info(img_dc):
    return_text = ""

    # convert image to PIL.Image
    pil_image = wximagedc2pilimage(img_dc)

    # get band names
    band_names = pil_image.getbands()
    bands_num = len(band_names)

    # get Statistics from PIL

    # Brightness Extrema
    image_stats = PIL.ImageStat.Stat(pil_image)
    return_text += "Brightness\n"
    return_text += "----------\n"
    for (i, extreme) in enumerate(image_stats.extrema):
        return_text += band_names[i] + " (Min., Max.): " + repr(extreme) + "\n"

    # Histogram
    histogram = pil_image.histogram()
    return_text += "\n\n"
    return_text += "Histogram" + ("s" if bands_num > 1 else "") + "\n"
    return_text += "---------" + ("-" if bands_num > 1 else "") + "\n"
    # band_hist_len should be 256, but we'll double-check to be sure
    band_hist_len = int(len(histogram)/bands_num)
    histograms = [
            histogram[i*band_hist_len:(i+1)*band_hist_len] for i in range(bands_num)
            ]
    for (i, hist) in enumerate(histograms):
        return_text += band_names[i] + ": " + repr(hist) + "\n\n"

    return return_text
