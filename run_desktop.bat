@echo off
chcp 65001 > nul
title Facebook Reels & Article Extractor (Desktop Edition)
echo ========================================================
echo   FACEBOOK REELS & ARTICLE CONTENT EXTRACTOR TOOL (DESKTOP)
echo ========================================================
echo.
echo Dang khoi dong ung dung Desktop...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Co loi xay ra khi khoi chay ung dung.
    pause
)
