#!/usr/bin/env/python3

# Copyright 2018 Matthew A. Clapp
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

import pathlib
import pytest

import numpy as np
import wx

import image_proc

# the parent of this file is the tests directory
TESTS_PATH = pathlib.Path(__file__).resolve().parent
# path to testdata dir
TESTDATA_PATH = TESTS_PATH / 'testdata'
# path to testdata dir for image_proc.py
TESTDATA_IMAGEPROC = TESTDATA_PATH / 'image_proc'

TEST_INPUT_IMAGE = TESTDATA_IMAGEPROC / 'test_gray.png'


# necessary for using some wx functions
app = wx.App()


def image_same(wx_image_ref, wx_image_test):
    wx_image_ref_data = wx_image_ref.GetData()[::3]
    wx_image_test_data = wx_image_test.GetData()[::3]

    test_result = wx_image_ref_data == wx_image_test_data

    if not test_result:
        for i in range(int(len(wx_image_test_data)/16)):
            print("ref: ", end="")
            for j in range(16):
                byte = wx_image_ref_data[i*16 + j]
                print("%02x"%byte, end=" ")
            print("")
            print("tst: ", end="")
            for j in range(16):
                byte = wx_image_test_data[i*16 + j]
                print("%02x"%byte, end=" ")
            print("")
        print("")

    return test_result

@pytest.mark.skip(reason="Empty test")
def test_fh_1sc_to_image():
    pass

@pytest.mark.skip(reason="Empty test")
def test_file1sc_to_image():
    pass

@pytest.mark.skip(reason="Empty test")
def test_image2memorydc():
    pass

@pytest.mark.skip(reason="Empty test")
def test_wxmemorydc2pilimage():
    pass

@pytest.mark.skip(reason="Empty test")
def test_wxbitmap2pilimage():
    pass

@pytest.mark.skip(reason="Empty test")
def test_wximage2pilimage():
    pass

@pytest.mark.skip(reason="Empty test")
def test_pilimage2wximage():
    pass

def test_image_invert():
    test_input = wx.Image(str(TEST_INPUT_IMAGE))
    correct_output = wx.Image(str(TESTDATA_IMAGEPROC / 'test_gray_invert.png' ))
    test_output = image_proc.image_invert(test_input)
    assert image_same(correct_output, test_output)

@pytest.mark.skip(reason="Empty test")
def test_image_autocontrast():
    pass

def test_image_remap_colormap():
    for colormap in ['viridis', 'plasma', 'inferno', 'magma']:
        test_input = wx.Image(str(TEST_INPUT_IMAGE))
        correct_output = wx.Image(
                str(TESTDATA_IMAGEPROC / ('test_%s.png'%colormap))
                )
        test_output = image_proc.image_remap_colormap(
                test_input,
                cmap=colormap
                )
        assert image_same(correct_output, test_output)

@pytest.mark.skip(reason="Empty test")
def test_get_image_info():
    pass
