#!/usr/bin/env/python3

import mcmfile
import pathlib

TESTDATA_PATH = pathlib.Path.cwd() / '..' / 'tests' / 'testdata'
def test_is_valid():
    mcm_testfile = TESTDATA_PATH / 'checkerboard.mcm'
    assert mcmfile.is_valid(mcm_testfile) is True
