from django.core.management.base import BaseCommand
from products.models import Category, Product


INITIAL_CATEGORIES = [
    {"name": "مرغ", "slug": "chicken", "display_order": 1},
    {"name": "گوسفندی", "slug": "lamb", "display_order": 2},
    {"name": "گوساله", "slug": "beef", "display_order": 3},
    {"name": "بوقلمون", "slug": "turkey", "display_order": 4},
]

INITIAL_PRODUCTS_DATA = {
    "مرغ": [
        "سینه شنسل",
        "سینه سایز",
        "سینه با گوشواره",
        "سینه با کتف",
        "سینه موادی",
        "سینه سایز بی پوست",
        "سینه سایز بدون کتف",
        "سینه سایز بدون کتف با پوست",
        "سینه جوجه ای",
        "فیله مرغ",
        "رون سایز",
        "رون سایز بدون پوست",
        "رون سایز بدون کعب",
        "رون ممتاز",
        "رون ساق ران",
        "کعب ران",
        "رون شنسلی",
        "رون شنسلی موادی",
        "رون شنسلی با پوست",
        "ساق رون با پوست",
        "کعب رون با پوست",
        "رون با کمر",
        "بال و کتف",
        "بال و کتف با نک",
        "بال",
        "کتف",
        "بال و کتف موادی",
        "بال موادی",
        "کتف موادی",
        "کتف شنسلی",
        "مرغ ۴ تیکه",
        "مرغ ۸ تیکه",
        "مرغ جوجه ای",
        "مرغ کامل",
        "اکبر جوجه",
        "دم مرغ",
        "گردن مرغ",
        "اسکلت با گردن",
        "اسکلت بی گردن",
        "خورده مرغ",
        "چربی مرغ",
        "پوست مرغ",
        "ضایعات مرغ",
        "قلم مرغ",
        "نک بال",
        "چیکن برگر",
    ],
    "بوقلمون": [
        "سینه بوقلمون",
        "فیله بوقلمون",
        "رون بوقلمون",
    ],
    "گوسفندی": [
        "لاشه گوسفندی",
        "ران گوسفندی",
        "کف دست گوسفندی",
        "سردست گوسفندی",
        "مغز رون گوسفندی",
        "قلوه گاه گوسفندی",
        "دنده گوسفندی",
        "گردن گوسفندی",
        "راسته شاندیزی گوسفندی",
        "راسته گوسفندی",
        "راسته فیله ممتاز گوسفندی",
        "توپوز گوسفندی",
        "خورده گوسفندی",
        "استخوان گوسفندی",
        "قلم گوسفندی",
        "سر سینه گوسفندی",
        "چنجه گوسفندی",
        "کله پاچه گوسفندی",
        "سیراب شیردان گوسفندی",
        "جگر گوسفندی",
        "شل گوسفندی",
        "سفیدی گوسفندی",
        "چربی گوسفندی",
        "دنبه گوسفندی",
        "خوئک گوسفندی",
        "خوش گوشت گوسفندی",
        "زبون گوسفندی",
    ],
    "گوساله": [
        "رون گاوی",
        "ماهیچه گوساله",
        "گفدست گوساله",
        "کف دست ممتاز گاوی",
        "سردست گاوی",
        "بریسکت",
        "بریسکت بدون چربی",
        "سر سینه گاوی",
        "سر سینه ناپاک گاوی",
        "اب گوشتی گاوی",
        "دنده اب گوشتی گاوی",
        "قلوه گاه گاوی",
        "پیش ناف گاوی",
        "راسته با دور گاوی",
        "راسته مغز گاوی",
        "راسته با دور بدون فیله گاوی",
        "فیله مغز گاوی",
        "فیله با دور گاوی",
        "توپوز گاوی",
        "گنجشکک گاوی",
        "شاهپسند گاوی",
        "گردن گاوی",
        "مغز گردن گاوی",
        "پوست گردن گاو",
        "شاه رگ گاوی",
        "رگ و پی گاوی",
        "خورده پی گاوی",
        "خورده گوشت گاوی",
        "چربی گاوی",
        "خورده ممتاز گاوی",
        "دنبالیچه گاوی",
        "مغز گاوی",
        "زبون گاوی",
        "پاچه گاوی",
        "سیراب شیردان گاوی",
        "قلم گوساله",
        "استخوان گوساله",
        "جگر گوساله",
        "دل گوساله",
        "سفیدی گوساله",
        "چربی چال گاوی",
        "پی قلوه گاوی",
        "پرده پی گاوی",
        "سورخی گاوی",
        "لپ گاوی",
        "خوئک گاوی",
        "ضایعات گاوی",
        "چربی صنعتی گاوی",
        "اشغال گوشت گاوی",
        "غذای سگ گاوی",
        "برگر ۱۲۵ ممتاز",
        "برگر ۱۲۵ معمولی",
        "برگر ۱۵۰ ممتاز",
        "برگر ۱۵۰ معمولی",
        "برگر۱۸۰ ممتاز",
        "برگر 180معمولی",
    ],
}


class Command(BaseCommand):
    help = "Development-only idempotent import of the initial MeatShop categories and products for Vaka Protein."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("--- شروع بارگذاری داده‌های اولیه کاتالوگ واکا پروتئین ---"))

        created_categories = 0
        existing_categories = 0
        category_objects = {}

        for cat_data in INITIAL_CATEGORIES:
            category, created = Category.objects.get_or_create(
                slug=cat_data["slug"],
                defaults={
                    "name": cat_data["name"],
                    "display_order": cat_data["display_order"],
                    "is_active": True,
                }
            )
            category_objects[cat_data["name"]] = category
            if created:
                created_categories += 1
            else:
                existing_categories += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"دسته‌بندی‌ها: {created_categories} ایجاد شد، {existing_categories} از قبل موجود بود."
            )
        )

        # Ensure canonical parent products exist
        parent_products = {}
        for cat_name, cat_obj in category_objects.items():
            parent_prod, _ = Product.objects.get_or_create(
                category=cat_obj,
                name=cat_name,
                defaults={
                    "unit": "kg",
                    "is_parent": True,
                    "is_active": True,
                }
            )
            if not parent_prod.is_parent:
                parent_prod.is_parent = True
                parent_prod.save(update_fields=['is_parent'])
            parent_products[cat_name] = parent_prod

        created_products = 0
        existing_products = 0

        for cat_name, product_list in INITIAL_PRODUCTS_DATA.items():
            category = category_objects[cat_name]
            parent_product = parent_products[cat_name]
            for prod_name in product_list:
                product, created = Product.objects.get_or_create(
                    category=category,
                    name=prod_name,
                    defaults={
                        "code": None,
                        "unit": "kg",
                        "price_per_unit_rial": None,
                        "parent": parent_product,
                        "is_active": True,
                    }
                )
                if not created and product.parent_id is None and not product.is_parent:
                    product.parent = parent_product
                    product.save(update_fields=['parent'])
                if created:
                    created_products += 1
                else:
                    existing_products += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"اقلام کالاها: {created_products} قلم جدید ایجاد شد، {existing_products} قلم از قبل موجود بود."
            )
        )
        self.stdout.write(self.style.SUCCESS("--- پایان عملیات بدون دستکاری قیمت‌ها یا حذف سوابق ---"))
