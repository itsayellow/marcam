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

import os.path
import sys

# add ./marcam to PYTHONPATH to allow loading const.py
#   relative to execute dir (./)
sys.path.append(os.path.abspath('marcam'))
import const

block_cipher = None

# datas relative to dir of this file (./build_scripts)
marcam_datas = [
        ('../marcam/media/marcam.ico', 'media'),
        ('../marcam/media/marcam_help.html', 'media'),
        ('../marcam/media/help_markmode_off.png', 'media'),
        ('../marcam/media/help_selectmode_off.png', 'media')
        # toolbar icons
        (os.path.relpath(const.SELECTBMP_FNAME, start='build_scripts'), 'media'),
        (os.path.relpath(const.MARKBMP_FNAME, start='build_scripts'), 'media'),
        (os.path.relpath(const.TOCLIPBMP_FNAME, start='build_scripts'), 'media'),
        (os.path.relpath(const.ZOOMOUTBMP_FNAME, start='build_scripts'), 'media'),
        (os.path.relpath(const.ZOOMINBMP_FNAME, start='build_scripts'), 'media'),
        (os.path.relpath(const.ZOOMFITBMP_FNAME, start='build_scripts'), 'media'),
        ]

a = Analysis(
        # relative to dir of this file (./build_scripts)
        ['..\\marcam\\marcam.py'],
        pathex=['./marcam', 'C:\\Users\\mclapp\\git\\marcam'],
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
        icon='marcam\\media\\marcam.ico')

coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        name='marcam'
        )

# vim: filetype=python
