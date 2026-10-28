from django.core.management.base import BaseCommand
from sales.models import TareType


INITIAL_TARE_TYPES = [
    {"name": "سبد ۱۵۰۰ گرمی", "tare_weight_grams": 1500, "is_custom": False},
    {"name": "سبد ۱۸۰۰ گرمی", "tare_weight_grams": 1800, "is_custom": False},
    {"name": "سبد ۲۰۰۰ گرمی", "tare_weight_grams": 2000, "is_custom": False},
    {"name": "قلاب ۲۵۰۰ گرمی", "tare_weight_grams": 2500, "is_custom": False},
    {"name": "قلاب ۳۹۰۰ گرمی", "tare_weight_grams": 3900, "is_custom": False},
    {"name": "پالت ۱۲۲۰۰ گرمی", "tare_weight_grams": 12200, "is_custom": False},
    {"name": "کارتن ۱۰۰۰ گرمی", "tare_weight_grams": 1000, "is_custom": False},
    {"name": "کالای فله / بدون ظرف", "tare_weight_grams": 0, "is_custom": False},
    {"name": "چرخ‌دستی / گاری (پارسنگ دستی)", "tare_weight_grams": 0, "is_custom": True},
]


class Command(BaseCommand):
    help = "Seed standard container tare types into the database."

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0
        for tare_data in INITIAL_TARE_TYPES:
            obj, created = TareType.objects.get_or_create(
                name=tare_data["name"],
                defaults={
                    "tare_weight_grams": tare_data["tare_weight_grams"],
                    "is_custom": tare_data["is_custom"],
                    "is_active": True,
                }
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"انواع پارسنگ: {created_count} ایجاد شد، {existing_count} از قبل موجود بود."
            )
        )
