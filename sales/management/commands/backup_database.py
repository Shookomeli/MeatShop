import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = "Creates a hot, crash-consistent SQLite backup with integrity verification."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help="Destination directory for backup file (defaults to BASE_DIR / 'backups')"
        )

    def handle(self, *args, **options):
        db_config = settings.DATABASES['default']
        if db_config['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError("دستور پشتیبان‌گیری ویژه پایگاه داده SQLite است.")

        # Determine target directory
        if options['output_dir']:
            backup_dir = Path(options['output_dir']).resolve()
        else:
            backup_dir = Path(settings.BASE_DIR) / 'backups'

        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"meatshop_backup_{timestamp_str}.sqlite3"
        target_backup_path = backup_dir / backup_filename

        self.stdout.write(f"شروع پشتیبان‌گیری آنلاین از پایگاه داده فعال...")

        try:
            connection.ensure_connection()
            # Use SQLite Online Backup API for hot, non-locking, crash-consistent snapshot.
            # closing() guarantees every handle is released even if the backup fails.
            with closing(sqlite3.connect(str(target_backup_path))) as dest_conn:
                if hasattr(connection, 'connection') and connection.connection:
                    connection.connection.backup(dest_conn, pages=100)
                else:
                    source_db_path = Path(db_config['NAME']).resolve()
                    with closing(sqlite3.connect(str(source_db_path))) as source_conn:
                        source_conn.backup(dest_conn, pages=100)

            # Verify integrity of the backup file
            with closing(sqlite3.connect(str(target_backup_path))) as verify_conn:
                integrity_result = verify_conn.execute("PRAGMA integrity_check;").fetchone()[0]

            if integrity_result != "ok":
                if target_backup_path.exists():
                    target_backup_path.unlink()
                raise CommandError(f"خطای سلامت پایگاه داده در فایل پشتیبان: {integrity_result}")

            file_size_kb = target_backup_path.stat().st_size / 1024
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ پشتیبان‌گیری با موفقیت انجام شد:\n"
                    f"مسیر فایل: {target_backup_path}\n"
                    f"حجم: {file_size_kb:.2f} KB | سلامت: PRAGMA integrity_check = ok"
                )
            )
            return str(target_backup_path)

        except Exception as e:
            if target_backup_path.exists():
                try:
                    target_backup_path.unlink()
                except Exception:
                    pass
            raise CommandError(f"خطا در ایجاد نسخه پشتیبان: {str(e)}")
