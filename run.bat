@echo off
chcp 65001 > nul
title Facebook Reels & Article Content Extractor (LAN Server)
echo ========================================================
echo   FACEBOOK REELS & ARTICLE CONTENT EXTRACTOR TOOL (LAN)
echo ========================================================
echo.
echo   * Truy cap tai may chu:      http://localhost:8501
echo   * Cac may khac trong mang LAN truy cap: http://192.168.1.27:8501
echo.
echo Dang khoi dong Web UI che do mang LAN...
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
