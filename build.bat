@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt || exit /b 1
python -m PyInstaller --noconfirm --onefile --windowed --name ModDeleter --collect-all tkinterdnd2 --collect-all sv_ttk app.py || exit /b 1
echo.
echo Done: dist\ModDeleter.exe
