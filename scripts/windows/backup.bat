@echo off
chcp 65001 > nul
rem Force UTF-8 for Python I/O so Persian output never crashes when redirected to a log file
set PYTHONUTF8=1
echo =======================================================
echo   فروشگاه گوشت و مرغ - پشتیبان‌گیری خودکار پایگاه داده
echo =======================================================

echo ۱. اجرای پشتیبان‌گیری آنلاین...
python manage.py backup_database --output-dir "C:\MeatShop\backups"

echo ۲. پاکسازی نسخه‌های پشتیبان قدیمی‌تر از ۳۰ روز...
forfiles /p "C:\MeatShop\backups" /s /m *.sqlite3 /d -30 /c "cmd /c del @path" 2>nul

echo =======================================================
echo پایان فرآیند پشتیبان‌گیری
echo =======================================================
