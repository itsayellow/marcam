pyinstaller ^
    -y ^
    --paths ./marcam ^
    --add-data marcam/marktool32.png;media ^
    --add-data marcam/pointer32.png;media ^
    --add-data marcam/marcam_help.html;media ^
    marcam/marcam.py
