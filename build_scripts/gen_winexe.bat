pyinstaller ^
    -y ^
    --paths ./marcam ^
    --add-data marcam/marktool32.png;media ^
    --add-data marcam/pointer32.png;media ^
    --add-data marcam/marcam_help.html;media ^
    --add-data marcam/help_markmode_off.png;media ^
    --add-data marcam/help_selectmode_off.png;media ^
    marcam/marcam.py
