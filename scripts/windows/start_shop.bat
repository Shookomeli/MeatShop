@echo off
chcp 65001 > nul
rem Force UTF-8 for Python I/O so Persian output never crashes when redirected to a log file
set PYTHONUTF8=1
echo =======================================================
echo   فروشگاه گوشت و مرغ - اجرای سرور داخلی فروشگاه
echo =======================================================

echo در حال اجرای سرور روی پورت داخلی ۸۰۰۰...
echo آدرس دسترسی در مرورگر: http://localhost:8000
python manage.py runserver 0.0.0.0:8000
pause
