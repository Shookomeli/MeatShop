import os
import sqlite3
from contextlib import closing
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader


# Project apps whose schema a MeatShop backup must contain
PROJECT_APPS = ('products', 'sales')

# Core tables present since the initial migrations; a backup without them is not a MeatShop database
REQUIRED_TABLES = (
    'django_migrations',
    'products_category',
    'products_product',
    'sales_invoice',
    'sales_invoiceitem',
    'sales_stockmovement',
)


def validate_backup_file(backup_path: Path) -> None:
    """
    Validates a candidate backup without modifying it or any other database.
    Raises CommandError if the file is not a healthy, compatible MeatShop SQLite database.
    Every SQLite connection is closed on both success and failure paths.
    """
    try:
        # mode=ro: validation must never write to (or create) the candidate file
        with closing(sqlite3.connect(f"{backup_path.as_uri()}?mode=ro", uri=True)) as conn:
            integrity_result = conn.execute("PRAGMA integrity_check;").fetchone()[0]
            if integrity_result != "ok":
                raise CommandError(f"فایل پشتیبان مخدوش است و قابل بازیابی نیست: {integrity_result}")

            tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            missing_tables = [t for t in REQUIRED_TABLES if t not in tables]
            if missing_tables:
                raise CommandError(
                    "فایل پشتیبان متعلق به پایگاه داده این نرم‌افزار نیست. "
                    f"جداول موردنیاز یافت نشد: {', '.join(missing_tables)}"
                )

            placeholders = ','.join('?' for _ in PROJECT_APPS)
            applied = set(conn.execute(
                f"SELECT app, name FROM django_migrations WHERE app IN ({placeholders})",
                PROJECT_APPS,
            ).fetchall())
    except CommandError:
        raise
    except sqlite3.Error as e:
        raise CommandError(f"خطا در اعتبارسنجی فایل پشتیبان: {str(e)}")

    for app in PROJECT_APPS:
        if (app, '0001_initial') not in applied:
            raise CommandError(f"فایل پشتیبان فاقد سابقه مهاجرت اولیه برنامه «{app}» است.")

    # A backup made by a newer version of the code cannot be safely used by this version
    known = {key for key in MigrationLoader(None, ignore_no_migrations=True).disk_migrations if key[0] in PROJECT_APPS}
    unknown = sorted(applied - known)
    if unknown:
        names = ', '.join(f"{app}.{name}" for app, name in unknown)
        raise CommandError(f"فایل پشتیبان شامل مهاجرت‌های ناشناخته (نسخه جدیدتر نرم‌افزار) است: {names}")


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
        if not backup_path.is_file():
            raise CommandError(f"فایل پشتیبان در مسیر {backup_path} یافت نشد.")

        if options.get('target_db'):
            target_db_path = Path(options['target_db']).resolve()
        else:
            target_db_path = Path(db_config['NAME']).resolve()

        # 1. Reject restoring a file onto itself
        if backup_path == target_db_path or (target_db_path.exists() and os.path.samefile(backup_path, target_db_path)):
            raise CommandError("مسیر فایل پشتیبان و پایگاه داده مقصد یکسان است؛ بازیابی انجام نشد.")

        # 2. Verify backup integrity and schema before touching the destination
        validate_backup_file(backup_path)

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

            # The SQLite backup API copies within a single transaction on the destination,
            # so a failure part-way leaves the existing destination content unchanged.
            with closing(sqlite3.connect(f"{backup_path.as_uri()}?mode=ro", uri=True)) as source_conn, \
                    closing(sqlite3.connect(str(target_db_path))) as dest_conn:
                source_conn.backup(dest_conn, pages=100)

            # Verify integrity of target after restore
            with closing(sqlite3.connect(str(target_db_path))) as chk_conn:
                chk_res = chk_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        except sqlite3.Error as e:
            raise CommandError(f"خطا در بازیابی پایگاه داده: {str(e)}")

        if chk_res != "ok":
            raise CommandError(f"خطای سلامت پایگاه داده پس از بازیابی: {chk_res}")

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ پایگاه داده با موفقیت از «{backup_path.name}» بازیابی شد.\n"
                f"مسیر دیتابیس: {target_db_path} | سلامت: PRAGMA integrity_check = ok"
            )
        )
