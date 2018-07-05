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

import os
import os.path
import sys

# add ./marcam to PYTHONPATH to allow loading const.py
sys.path.append(os.path.abspath('marcam'))
import const

block_cipher = None

marcam_datas = [
            ('../marcam/media/marcam.ico', 'media'),
            ('../marcam/media/marcam_help.html', 'media'),
            ('../marcam/media/help_markmode_off.png', 'media'),
            ('../marcam/media/help_selectmode_off.png', 'media')
            ]
# make sure toolbar icons are added
marcam_datas.append(
        (os.path.relpath(const.SELECTBMP_FNAME, start='build_scripts'), 'media')
        )
marcam_datas.append(
        (os.path.relpath(const.MARKBMP_FNAME, start='build_scripts'), 'media')
        )

a = Analysis(
        ['../marcam/marcam.py'],
        pathex=['marcam', '.'],
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
        a.pure, a.zipped_data,
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
        icon='marcam/media/marcam.icns'
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

app = BUNDLE(
        coll,
        name='Marcam.app',
        icon='marcam/media/marcam.icns',
        bundle_identifier='com.itsayellow.osx.marcam',
        info_plist={
                'CFBundleDevelopmentRegion':'English',
                'CFBundleDisplayName':'Marcam',
                'CFBundleGetInfoString':'Count objects in images',
                'CFBundleIdentifier':'com.itsayellow.osx.marcam',
                'CFBundleName':'Marcam',
                'CFBundleShortVersionString':const.VERSION_STR,
                'CFBundleVersion':const.VERSION_STR,
                'NSPrincipalClass':'NSApplication',
                'NSHumanReadableCopyright': u"Copyright \u00A9 2018, " \
                        "Matthew A. Clapp, All Rights Reserved",
                'CFBundleDocumentTypes':[
                    {
                        'CFBundleTypeName':'Marcam Image Data File',
                        'CFBundleTypeRole':'Editor',
                        'CFBundleTypeIconFile':'media/marcam_doc.icns',
                        'LSHandlerRank': "Owner",
                        'LSItemContentTypes': ["com.itsayellow.mcm"],
                        },
                    {
                        'CFBundleTypeName':'Bio-Rad Gel File',
                        'CFBundleTypeRole':'Viewer',
                        #'CFBundleTypeIconFile':'.icns',
                        'LSHandlerRank': "Alternate",
                        'LSItemContentTypes': ["com.itsayellow.1sc"],
                        },
                    {
                        'CFBundleTypeName':'TIFF Image',
                        'CFBundleTypeRole':'Viewer',
                        'LSHandlerRank': "Alternate",
                        'LSItemContentTypes': ["public.tiff"],
                        },
                    {
                        'CFBundleTypeName':'PNG Image',
                        'CFBundleTypeRole':'Viewer',
                        'LSHandlerRank': "Alternate",
                        'LSItemContentTypes': ["public.png"],
                        },
                    {
                        'CFBundleTypeName':'JPEG Image',
                        'CFBundleTypeRole':'Viewer',
                        'LSHandlerRank': "Alternate",
                        'LSItemContentTypes': ["public.jpeg"],
                        },
                    ],
                'UTExportedTypeDeclarations': [
                    {
                        'UTTypeConformsTo': ["public.data"],
                        'UTTypeIdentifier': "com.itsayellow.mcm",
                        'UTTypeDescription': "Marcam Image Data File",
                        'UTTypeTagSpecification': {'public.filename-extension': "mcm"}
                        },
                    {
                        'UTTypeConformsTo': ["public.data"],
                        'UTTypeIdentifier': "com.itsayellow.1sc",
                        'UTTypeDescription': "Bio-Rad Gel File",
                        'UTTypeTagSpecification': {'public.filename-extension': "1sc"}
                        },
                    ],
            },
        )

# vim: filetype=python
