#!/usr/bin/env/python3

import mcmfile
import pathlib

# the parent of this file is the tests directory
TESTS_PATH = pathlib.Path(__file__).resolve().parent
# path to testdata dir
TESTDATA_PATH = TESTS_PATH / 'testdata'

def test_is_valid():
    mcm_testfile = TESTDATA_PATH / 'checkerboard.mcm'
    assert mcmfile.is_valid(mcm_testfile) is True
