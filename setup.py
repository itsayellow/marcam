"""
This is a setup.py script generated by py2applet

Usage:
    python3 setup.py py2app
"""

from setuptools import setup

APP = ['cellcounter/cellcounter.py']
APP_NAME = 'Cellcounter'
VERSION = '0.1.0'
DATA_FILES = [
        'cellcounter/topen32.png',
        'cellcounter/marktool32.png'
        ]
OPTIONS = {
        'argv_emulation':True,
        'iconfile':'cellcounter/cellcounter.icns',
        'optimize':1, # try one level of optimization?
        'plist':{
            'CFBundleName':APP_NAME,
            'CFBundleDisplayName':APP_NAME,
            'CFBundleGetInfoString':'Count cells in biological images',
            'CFBundleIdentifier':'com.itsayellow.osx.cellcounter',
            'CFBundleVersion':VERSION,
            'CFBundleShortVersionString':VERSION,
            'NSHumanReadableCopyright': u"Copyright © 2017, " \
                    "Matthew A. Clapp, All Rights Reserved",
            'CFBundleDocumentTypes':[
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
                ],
            'UTExportedTypeDeclarations': [{
                'UTTypeConformsTo': ["public.data"],
                'UTTypeIdentifier': "com.itsayellow.1sc",
                'UTTypeDescription': "Bio-Rad Gel File",
                'UTTypeTagSpecification': {'public.filename-extension': "1sc"}
            }],
            },
        }

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
