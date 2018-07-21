# -*- mode: python -*-

block_cipher = None


a = Analysis(['marcam\\marcam.py'],
             pathex=['./marcam', 'C:\\Users\\mclapp\\git\\marcam'],
             binaries=[],
             datas=[('marcam/media/marcam.ico', 'media'), ('marcam/media/selectmode32.png', 'media'), ('marcam/media/marktool32.png', 'media'), ('marcam/media/zoomout32.png', 'media'), ('marcam/media/zoomin32.png', 'media'), ('marcam/media/zoomfit32.png', 'media'), ('marcam/media/toclip32.png', 'media'), ('marcam/media/marcam_help.html', 'media'), ('marcam/media/help_markmode_off.png', 'media'), ('marcam/media/help_selectmode_off.png', 'media')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='marcam',
          debug=False,
          strip=False,
          upx=True,
          console=False , icon='marcam\\media\\marcam.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='marcam')
