# -*- mode: python -*-

block_cipher = None


a = Analysis(
        ['../marcam/marcam.py'],
        pathex=['marcam', '.'],
        binaries=[],
        datas=[
            ('../marcam/media/marktool24.png', 'media'),
            ('../marcam/media/pointer_mac24f.png', 'media'),
            ('../marcam/media/marcam_help.html', 'media'),
            ('../marcam/media/help_markmode_off.png', 'media'),
            ('../marcam/media/help_selectmode_off.png', 'media')
            ],
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
                'CFBundleShortVersionString':'0.3.0',
                'CFBundleVersion':'0.3.0',
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
