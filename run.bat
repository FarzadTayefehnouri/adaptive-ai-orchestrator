@echo off
chcp 65001 >nul
title سامانه هوش مصنوعی چندعاملی تطبیق‌پذیر
echo ========================================================
echo   در حال راه‌اندازی سامانه هوش مصنوعی چندعاملی...
echo ========================================================

:: بررسی پایتون
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [خطا] پایتون روی سیستم شما یافت نشد! لطفاً پایتون 3.10 به بالا را نصب کنید.
    pause
    exit /b 1
)

:: ایجاد یا فعال‌سازی محیط مجازی
if not exist "venv" (
    echo در حال ساخت محیط مجازی پایتون (venv)...
    python -m venv venv
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: بررسی فایل .env
if not exist ".env" (
    if exist ".env.example" (
        echo ایجاد فایل تنظیمات اولیه .env از روی نمونه...
        copy .env.example .env >nul
    )
)

:: اجرای سرور مانیتورینگ و باز کردن خودکار مرورگر
echo اجرای هسته سامانه و داشبورد مانیتورینگ...
python run_server.py

pause
