#!/usr/bin/env/python3

import pathlib
import wx
import zipfile

import mcmfile

# the parent of this file is the tests directory
TESTS_PATH = pathlib.Path(__file__).resolve().parent
# path to testdata dir
TESTDATA_PATH = TESTS_PATH / 'testdata'

# test read files
TIFF_FILE = TESTDATA_PATH / 'test1_ref.tif'
LEGACY_MCM_1SC_FILE = TESTDATA_PATH / 'legacy_mcm_1sc_A11 2015-12-15 11hr 55min.mcm'
MCM_1_0_FILE = TESTDATA_PATH / 'single_pixel_lines.mcm'

# test save files
SAVE_MCM_FILEPATH = TESTDATA_PATH / 'test_save_file.mcm'

def test_is_valid_legacy():
    assert mcmfile.is_valid(LEGACY_MCM_1SC_FILE) is True

def test_is_valid_mcm_1_0_file():
    assert mcmfile.is_valid(MCM_1_0_FILE) is True

def test_load_legacy_mcm_file():
    # legacy mcm file
    (wx_image, marks, img_name) = mcmfile.load(LEGACY_MCM_1SC_FILE)
    assert wx_image.IsOk()
    assert isinstance(marks, list)
    assert isinstance(img_name, str)

def test_load_mcm_1_0_file():
    # legacy mcm file
    (wx_image, marks, img_name) = mcmfile.load(MCM_1_0_FILE)
    assert wx_image.IsOk()
    assert isinstance(marks, list)
    assert isinstance(img_name, str)

def test_save():
    app = wx.App()
    test_img = wx.Image(str(TIFF_FILE))
    test_marks = [(1,4), (2,10), (20,5)]
    save_returnval = mcmfile.save(str(SAVE_MCM_FILEPATH), test_img, test_marks)
    assert save_returnval
    assert zipfile.is_zipfile(str(SAVE_MCM_FILEPATH))
    # delete test save file
    SAVE_MCM_FILEPATH.unlink()
