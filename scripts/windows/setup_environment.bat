@echo off
chcp 65001 > nul
rem Force UTF-8 for Python I/O so Persian output never crashes when redirected to a log file
set PYTHONUTF8=1
echo =======================================================
echo   فروشگاه گوشت و مرغ - راه‌اندازی اولیه محیط ویندوز
echo =======================================================

echo ۱. بررسی نصب پایتون...
python --version
if errorlevel 1 (
    echo [خطا] پایتون بر روی سیستم نصب نیست یا در PATH قرار ندارد.
    pause
    exit /b 1
)

echo ۲. ایجاد پوشه‌های عملیاتی فروشگاه در درایو C...
if not exist "C:\MeatShop\data" mkdir "C:\MeatShop\data"
if not exist "C:\MeatShop\backups" mkdir "C:\MeatShop\backups"

echo ۳. نصب پیش‌نیازهای نرم‌افزار...
pip install -r requirements.txt
if errorlevel 1 (
    echo [خطا] اشکال در نصب کتابخانه‌ها.
    pause
    exit /b 1
)

echo ۴. اجرای مهاجرت‌های ساختار پایگاه داده (Migrate)...
python manage.py migrate
if errorlevel 1 (
    echo [خطا] مهاجرت دیتابیس با شکست مواجه شد.
    pause
    exit /b 1
)

echo ۵. بارگذاری انواع استاندارد ظروف پارسنگ...
python manage.py seed_tare_types

echo =======================================================
echo ✓ محیط فروشگاه با موفقیت آماده شد!
echo جهت شروع به کار، فایل start_shop.bat را اجرا فرمایید.
echo =======================================================
pause
