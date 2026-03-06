@echo off
echo Installing build tools and dependencies...
pip install pyinstaller supabase

echo.
echo Building TimeTracker.exe...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name TimeTracker ^
    --collect-all supabase ^
    --collect-all gotrue ^
    --collect-all postgrest ^
    --collect-all realtime ^
    --collect-all storage3 ^
    --collect-all supafunc ^
    --hidden-import httpx ^
    --hidden-import httpcore ^
    --hidden-import anyio ^
    --hidden-import sniffio ^
    --hidden-import certifi ^
    timetracker.py

echo.
if exist dist\TimeTracker.exe (
    echo SUCCESS: dist\TimeTracker.exe is ready to distribute.
) else (
    echo FAILED: check the output above for errors.
)
pause
