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
        (abspath('marcam/media/marcam_doc.icns'), 'media'),
        (abspath('marcam/media/marcam_help_mac.html'), 'media'),
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
        # If True, Provide assistance with debugging a frozen application.
        debug=False,
        # If not False, Apply a symbol-table strip to the executable and shared
        #   libs (not recommended for Windows).
        strip=False,
        # "UPX compresses executable files and libraries, making them smaller,
        #   sometimes much smaller."
        upx=True,
        # If True, Open a console window for standard i/o.
        console=False,
        # relative to execute dir (./)
        icon=abspath('marcam/media/marcam.icns')
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
        # relative to execute dir (./)
        icon='marcam/media/marcam.icns',
        bundle_identifier='com.itsayellow.osx.marcam',
        info_plist={
                'CFBundleDevelopmentRegion':'English',
                'CFBundleDisplayName':'Marcam',
                'CFBundleGetInfoString':'Count objects in images',
                'CFBundleIdentifier':'com.itsayellow.osx.marcam',
                'CFBundleName':'Marcam',
                #'CFBundleSignature':'????', # Do we need this?
                # CFBundleShortVersionString shows up in Finder 'Info'
                #   of app, and also in Marcam -> About version.
                # "specifies the release version number of the bundle, which
                #   identifies a released iteration of the app."
                'CFBundleShortVersionString':const.VERSION_PLIST_STR,
                # "specifies the build version number of the bundle, which
                #   identifies an iteration (released or unreleased) of the
                #   bundle."
                'CFBundleVersion':const.VERSION_PLIST_STR,
                #'NSAppleScriptEnabled':False, # by default is false
                #'NSMainNibFile':'MainMenu', # if we had a MainMenu.nib file
                'NSPrincipalClass':'NSApplication',
                'NSHumanReadableCopyright': u"Copyright \u00A9 2017-2018, " \
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
                        'CFBundleTypeIconFile':'media/marcam_doc.icns',
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

# vim: filetype=python nowrap
