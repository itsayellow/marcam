# -*- mode: python -*-

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

import pathlib
import sys

def abspath(file_path):
    """From path relative to cwd, return string of absolute path.

    Args:
        file_path (pathlike): path relative to cwd

    Returns:
        str: absolute path string
    """
    return str(pathlib.Path(file_path).resolve())

# add ./marcam to PYTHONPATH to allow loading const.py
#   relative to execute dir (./)
sys.path.append(abspath('marcam'))

import const

block_cipher = None

# datas are sources relative to dir of this file
# Use computed absolute paths so we don't have to care.
# Paths seem to work but str() to be safe
marcam_datas = [
        (abspath('marcam/media/marcam.ico'), 'media'),
        (abspath('marcam/media/marcam_doc.ico'), 'media'),
        (abspath('marcam/media/marcam_help.html'), 'media'),
        # toolbar icons (absolute paths from const)
        (abspath(const.SELECTBMP_FNAME), 'media'),
        (abspath(const.MARKBMP_FNAME), 'media'),
        (abspath(const.TOCLIPBMP_FNAME), 'media'),
        (abspath(const.ZOOMOUTBMP_FNAME), 'media'),
        (abspath(const.ZOOMINBMP_FNAME), 'media'),
        (abspath(const.ZOOMFITBMP_FNAME), 'media'),
        ]

a = Analysis(
        # relative to dir of this file
        # Use computed absolute paths so we don't have to care.
        [abspath('marcam/marcam.py')],
        # relative to execute dir (./)
        pathex=[abspath('./marcam'), abspath('.')],
        binaries=[],
        datas=marcam_datas,
        hiddenimports=[],
        hookspath=[],
        runtime_hooks=[],
        excludes=[],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher
        )

pyz = PYZ(
        a.pure,
        a.zipped_data,
        cipher=block_cipher
        )

exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name='marcam',
        debug=False,
        strip=False,
        upx=True,
        console=False,
        # relative to execute dir (./)
        icon=abspath('marcam/media/marcam.ico')
        )

coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        name='marcam'
        )

# vim: filetype=python nowrap
