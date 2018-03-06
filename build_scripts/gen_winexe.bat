pyinstaller ^
    -y ^
    --paths ./marcam ^
    --add-data marcam/marktool32.png;img ^
    --add-data marcam/pointer32.png;img ^
    marcam/marcam.py
