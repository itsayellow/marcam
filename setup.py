"""
This is a setup.py script generated by py2applet

Usage:
    python3 setup.py py2app
"""

import sys


# global
mainscript = 'cellcounter/cellcounter.py'
app_name = 'Cellcounter'
data_files = [
        'cellcounter/topen32.png',
        'cellcounter/marktool32.png',
        'cellcounter/cellcounter_help.html',
        'cellcounter/cellcounter_help_markmodeoff.png'
        ]
version = '0.1.0'


if sys.platform == 'darwin':
    from setuptools import setup
    # Mac and py2app
    py2app_options = {
            'argv_emulation':True, # if enabled makes app start minimized (?)
            'iconfile':'cellcounter/cellcounter.icns',
            'optimize':1, # try one level of optimization?
            'plist':{
                'CFBundleName':app_name,
                'CFBundleDisplayName':app_name,
                'CFBundleGetInfoString':'Count cells in biological images',
                'CFBundleIdentifier':'com.itsayellow.osx.cellcounter',
                'CFBundleVersion':version,
                'CFBundleShortVersionString':version,
                'NSHumanReadableCopyright': u"Copyright © 2017, " \
                        "Matthew A. Clapp, All Rights Reserved",
                'CFBundleDocumentTypes':[
                    {
                        'CFBundleTypeName':'Cellcounter Image Data File',
                        'CFBundleTypeRole':'Editor',
                        'CFBundleTypeIconFile':'cellcounter_doc.icns',
                        'LSHandlerRank': "Owner",
                        'LSItemContentTypes': ["com.itsayellow.cco"],
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
                        'UTTypeIdentifier': "com.itsayellow.cco",
                        'UTTypeDescription': "Cellcounter Image Data File",
                        'UTTypeTagSpecification': {'public.filename-extension': "cco"}
                        },
                    {
                        'UTTypeConformsTo': ["public.data"],
                        'UTTypeIdentifier': "com.itsayellow.1sc",
                        'UTTypeDescription': "Bio-Rad Gel File",
                        'UTTypeTagSpecification': {'public.filename-extension': "1sc"}
                        },
                    ],
                },
            }
    extra_options = dict(
            app=[mainscript],
            data_files=data_files,
            options={'py2app': py2app_options},
            setup_requires=['py2app']
            )
elif sys.platform == 'win32':
    from distutils.core import setup
    import py2exe
    options = {
            }
    # Windows and py2exe
    # win32 is name of platform even on 64-bit Windows!
    extra_options = dict(
            windows=[mainscript],
            #setup_requires=['py2exe'],
            data_files=data_files,
            options={'py2exe': options},
            )
else:
    # for unix-like platforms to use setup.py install to install main script
    extra_options = dict(
            scripts=[mainscript],
            )

setup(
        name=app_name,
        **extra_options
)
