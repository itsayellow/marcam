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
import biorad1sc_reader
from biorad1sc_reader import BioRadInvalidFileError, BioRadParsingError

import common
import colormaps

# logging stuff
#   not necessary to make a handler since we will be child logger of marcam
#   we use NullHandler so if no config at top level we won't default to printing
#       to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

# create debug function using this file's logger
debug_fxn = common.debug_fxn_factory(LOGGER.info, common.DEBUG_FXN_STATE)
debug_fxn_debug = common.debug_fxn_factory(LOGGER.debug, common.DEBUG_FXN_STATE)

# TODO: may want to use threads for some time-consuming operations


#-----------------------
# Image data conversions
@debug_fxn
def file1sc_to_image(file1sc_file):
    """Read in file1sc file and convert to wx.Image

    Args:
        file1sc_file (str): path to .1sc file

    Returns:
        wx.Image: image object
    """
    try:
        read1sc = biorad1sc_reader.Reader(file1sc_file)
    except (BioRadInvalidFileError, BioRadParsingError):
        # img_ok is false if 1sc is not valid 1sc file
        return False

    (img_x, img_y, img_data) = read1sc.get_img_data()

    # TODO: wx.Image is probably only 8-bits each color channel
    #   yet we have 16-bit images
    # wx.Image wants img_x * img_y * 3
    # TODO: shadow data with full 16-bit info
    img_data_rgb = np.zeros(img_data.size*3, dtype='uint8')
    img_data_rgb[0::3] = img_data//256
    img_data_rgb[1::3] = img_data//256
    img_data_rgb[2::3] = img_data//256
    img = wx.Image(img_x, img_y, bytes(img_data_rgb))
    return img

@debug_fxn
def image2memorydc(in_image, white_bg=False):
    """Converts wx.Image to wx.MemoryDC
    """
    # Create MemoryDC to return
    image_dc = wx.MemoryDC()
    # convert image to bitmap
    image_bmp = wx.Bitmap(in_image)
    if white_bg:
        # make white image of same size
        bg_image = wx.Image(in_image.GetWidth(), in_image.GetHeight())
        bg_image.Clear(value=b'\xff')
        bg_bmp = wx.Bitmap(bg_image)
        # use image_dc to draw onto bg_bmp
        image_dc.SelectObject(bg_bmp)
        image_dc.DrawBitmap(image_bmp, 0, 0)
    else:
        image_dc.SelectObject(image_bmp)

    return image_dc

@debug_fxn
def memorydc2image(wx_imagedc):
    wx_bitmap = wx_imagedc.GetAsBitmap()
    return wx_bitmap.ConvertToImage()

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
def image_invert(wx_image):
    pil_image = wximage2pilimage(wx_image)
    new_pil_image = PIL.ImageOps.invert(pil_image)
    wx_image = pilimage2wximage(new_pil_image)
    return wx_image

@debug_fxn
def image_autocontrast(wx_image, cutoff=0):
    pil_image = wximage2pilimage(wx_image)
    new_pil_image = PIL.ImageOps.autocontrast(pil_image, cutoff=cutoff)
    wx_image = pilimage2wximage(new_pil_image)
    return wx_image

@debug_fxn
def image_remap_colormap(wx_image, cmap='viridis'):
    """Remap colormap to new color map

    Intended to give false color to Black and White images.

    Args:
        cmap (string): desired colormap to map image to:
            'viridis' or 'magma' or 'plasma' or 'inferno'
    """
    # numpy method is ~18x faster than pure python list comprehension method
    start_time = time.time()
    width = wx_image.GetWidth()
    height = wx_image.GetHeight()
    image_data = np.array(wx_image.GetData())

    # Just get red channel, quick and dirty way.  Works exactly if original
    #   is grayscale.
    image_data_gray = image_data[::3]

    if cmap=='viridis':
        new_image_data = colormaps.VIRIDIS_DATA_24BIT_NP[image_data_gray].flatten()
    elif cmap=='plasma':
        new_image_data = colormaps.PLASMA_DATA_24BIT_NP[image_data_gray].flatten()
    elif cmap=='magma':
        new_image_data = colormaps.MAGMA_DATA_24BIT_NP[image_data_gray].flatten()
    elif cmap=='inferno':
        new_image_data = colormaps.INFERNO_DATA_24BIT_NP[image_data_gray].flatten()
    else:
        raise Exception("Internal Error: unknown colormap")

    wx_image = wx.Image(width, height, new_image_data)
    return wx_image

#-----------------------
# Image information

@debug_fxn
def get_image_info(image_dc):
    return_text = ""

    # convert image to PIL.Image
    pil_image = wximagedc2pilimage(image_dc)

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
