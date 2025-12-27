@ECHO OFF

uv run pyinstaller --onedir --noconsole --icon icon.ico --clean^
 CheckBrblImage.py

del dist\CheckBrblImage\_internal\PySide6\opengl32sw.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6Network.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6Pdf.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6Qml.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6QmlModels.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6Quick.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6Svg.dll
del dist\CheckBrblImage\_internal\PySide6\Qt6OpenGL.dll
rmdir /q /s dist\CheckBrblImage\_internal\PySide6\translations


