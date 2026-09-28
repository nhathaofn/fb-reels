@echo off
chcp 65001 > nul
title Dong goi ung dung Facebook Reels Extractor (.exe)
echo ========================================================
echo   DONG GOI UNG DUNG DESKTOP THANH FILE THUC THI (.EXE)
echo ========================================================
echo.

echo Dang don dep ban build cu...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo Dang tien hanh dong goi (Pre-bundling all libraries and components)...
pyinstaller --noconfirm --onedir --windowed ^
    --name "FacebookReelsExtractor" ^
    --add-data "src;src" ^
    --collect-all customtkinter ^
    --collect-all yt_dlp ^
    --collect-all trafilatura ^
    --collect-all playwright ^
    --collect-all certifi ^
    --collect-all openpyxl ^
    --collect-all httpx ^
    --collect-all bs4 ^
    --hidden-import "sqlite3" ^
    --hidden-import "PIL" ^
    --hidden-import "tkinter" ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Khoi tao thu muc du lieu tuong doi cho ban dong goi...
    if not exist "dist\FacebookReelsExtractor\output" mkdir "dist\FacebookReelsExtractor\output"
    if not exist "dist\FacebookReelsExtractor\output\excel" mkdir "dist\FacebookReelsExtractor\output\excel"
    if not exist "dist\FacebookReelsExtractor\output\videos" mkdir "dist\FacebookReelsExtractor\output\videos"
    if not exist "dist\FacebookReelsExtractor\output\captions" mkdir "dist\FacebookReelsExtractor\output\captions"
    if not exist "dist\FacebookReelsExtractor\browser_profile" mkdir "dist\FacebookReelsExtractor\browser_profile"
    if not exist "dist\FacebookReelsExtractor\browser_profile\profiles" mkdir "dist\FacebookReelsExtractor\browser_profile\profiles"
    
    echo.
    echo ========================================================
    echo   DONG GOI THANH CONG 100%!
    echo   Thu muc ung dung doc lap nam tai:
    echo   dist\FacebookReelsExtractor\
    echo.
    echo   File thuc thi chinh:
    echo   dist\FacebookReelsExtractor\FacebookReelsExtractor.exe
    echo.
    echo   * Ban chi can copy ca thu muc "FacebookReelsExtractor"
    echo     sang bat ky may tinh Windows nao la chay duoc ngay!
    echo   * Khong can cai dat Python, khong can cai thu vien!
    echo   * Duong dan du lieu hoan toan tuong doi ngay ben canh file .exe.
    echo ========================================================
) else (
    echo.
    echo [LOI] Co loi xay ra trong qua trinh dong goi!
)
if "%~1"=="" pause

