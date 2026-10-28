import os
import sqlite3
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = "Safely validates and restores a verified SQLite backup."

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help="Path to the .sqlite3 backup file to restore"
        )
        parser.add_argument(
            '--target-db',
            type=str,
            default=None,
            help="Optional path to target database (defaults to configured settings.DATABASES['default']['NAME'])"
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help="Bypass interactive user confirmation prompt (useful for automated scripts and tests)"
        )

    def handle(self, *args, **options):
        db_config = settings.DATABASES['default']
        if db_config['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError("دستور بازیابی ویژه پایگاه داده SQLite است.")

        backup_path = Path(options['backup_file']).resolve()
        if not backup_path.exists():
            raise CommandError(f"فایل پشتیبان در مسیر {backup_path} یافت نشد.")

        # 1. Verify backup integrity before doing anything
        try:
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()[0]
            conn.close()
            if integrity_result != "ok":
                raise CommandError(f"فایل پشتیبان مخدوش است و قابل بازیابی نیست: {integrity_result}")
        except Exception as e:
            raise CommandError(f"خطا در اعتبارسنجی فایل پشتیبان: {str(e)}")

        if options.get('target_db'):
            target_db_path = Path(options['target_db']).resolve()
        else:
            target_db_path = Path(db_config['NAME']).resolve()

        if not options['no_input']:
            confirm = input(
                f"هشدار: بازیابی این فایل موجب جایگزینی کامل پایگاه داده در «{target_db_path}» خواهد شد.\n"
                f"آیا برای ادامه اطمینان دارید؟ (yes/no): "
            )
            if confirm.strip().lower() != 'yes':
                self.stdout.write(self.style.WARNING("عملیات بازیابی توسط کاربر لغو گردید."))
                return

        try:
            # Close active Django connection so database file is not locked
            connection.close()

            source_conn = sqlite3.connect(str(backup_path))
            dest_conn = sqlite3.connect(str(target_db_path))

            with dest_conn:
                source_conn.backup(dest_conn, pages=100)

            source_conn.close()
            dest_conn.close()

            # Verify integrity of target after restore
            chk_conn = sqlite3.connect(str(target_db_path))
            chk_cursor = chk_conn.cursor()
            chk_cursor.execute("PRAGMA integrity_check;")
            chk_res = chk_cursor.fetchone()[0]
            chk_conn.close()

            if chk_res != "ok":
                raise CommandError(f"خطای سلامت پایگاه داده پس از بازیابی: {chk_res}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ پایگاه داده با موفقیت از «{backup_path.name}» بازیابی شد.\n"
                    f"مسیر دیتابیس: {target_db_path} | سلامت: PRAGMA integrity_check = ok"
                )
            )

        except Exception as e:
            raise CommandError(f"خطا در بازیابی پایگاه داده: {str(e)}")
