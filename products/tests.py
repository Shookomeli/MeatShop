from django.test import TestCase, Client
from django.conf import settings
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from products.models import Category, Product


class FoundationTestCase(TestCase):
    def test_settings_locale(self):
        self.assertEqual(settings.LANGUAGE_CODE, 'fa-ir')
        self.assertEqual(settings.TIME_ZONE, 'Asia/Tehran')
        self.assertTrue(settings.USE_I18N)

    def test_installed_apps(self):
        self.assertTrue(apps.is_installed('products'))
        self.assertTrue(apps.is_installed('sales'))
        # scale must NOT be in INSTALLED_APPS
        self.assertFalse(apps.is_installed('scale'))

    def test_scale_package_importable(self):
        from scale.base import ScaleInterface, ScaleError
        from scale.service import get_scale
        scale = get_scale()
        self.assertIsInstance(scale, ScaleInterface)


class ConfigurationTestCase(TestCase):
    def test_database_configuration_dev(self):
        from MeatShop.settings import db_name
        db_config = settings.DATABASES['default']
        self.assertEqual(db_config['ENGINE'], 'django.db.backends.sqlite3')
        self.assertTrue(str(db_name).endswith('db.sqlite3'))

    def test_currency_settings_valid(self):
        self.assertIn(settings.CURRENCY_DISPLAY_UNIT, ['TOMAN', 'RIAL'])

    def test_scale_mode_valid(self):
        self.assertIn(settings.SCALE_MODE, ['mock', 'keli_xk3118t1'])

    def test_secret_key_present(self):
        self.assertTrue(len(settings.SECRET_KEY) > 0)


class ProductCatalogueTestCase(TestCase):
    def setUp(self):
        self.cat_chicken, _ = Category.objects.get_or_create(
            slug="chicken",
            defaults={"name": "مرغ", "display_order": 1, "is_active": True}
        )
        self.cat_beef, _ = Category.objects.get_or_create(
            slug="beef",
            defaults={"name": "گوساله", "display_order": 3, "is_active": True}
        )
        self.parent_chicken, _ = Product.objects.get_or_create(
            category=self.cat_chicken,
            name="مرغ",
            defaults={"unit": "kg", "is_parent": True, "is_active": True}
        )
        self.product1, _ = Product.objects.get_or_create(
            category=self.cat_chicken,
            name="فیله مرغ تست",
            defaults={
                "code": "CHK-101",
                "unit": "kg",
                "price_per_unit_rial": 2500000,
                "parent": self.parent_chicken,
                "is_active": True,
            }
        )

    def test_category_creation_and_str(self):
        self.assertEqual(str(self.cat_chicken), "مرغ")
        self.assertTrue(self.cat_chicken.products.count() >= 1)

    def test_product_exact_persian_name_preserved(self):
        self.assertEqual(self.product1.name, "فیله مرغ تست")
        self.assertEqual(str(self.product1), "فیله مرغ تست")

    def test_parent_product_resolution(self):
        # Parent product resolves to itself
        self.assertEqual(self.parent_chicken.get_parent(), self.parent_chicken)
        # Child product resolves to parent
        self.assertEqual(self.product1.get_parent(), self.parent_chicken)
        # Sub-child also resolves to root parent
        sub_child = Product.objects.create(
            name="فیله خرد شده",
            category=self.cat_chicken,
            parent=self.product1
        )
        self.assertEqual(sub_child.get_parent(), self.parent_chicken)

    def test_product_cannot_be_own_parent(self):
        with self.assertRaises(ValidationError):
            p = Product(
                name="تست والد نامعتبر",
                category=self.cat_chicken
            )
            p.save()
            p.parent = p
            p.full_clean()

    def test_product_optional_code_and_uniqueness(self):
        prod_no_code1 = Product.objects.create(
            name="سینه شنسل تستی ۱",
            code=None,
            category=self.cat_chicken,
            parent=self.parent_chicken
        )
        prod_no_code2 = Product.objects.create(
            name="سینه سایز تستی ۲",
            code=None,
            category=self.cat_chicken,
            parent=self.parent_chicken
        )
        self.assertIsNone(prod_no_code1.code)
        self.assertIsNone(prod_no_code2.code)

        # Duplicate non-empty code must fail
        with self.assertRaises(ValidationError):
            duplicate = Product(
                name="تکه دیگر",
                code="CHK-101",
                category=self.cat_chicken
            )
            duplicate.full_clean()

    def test_product_empty_name_validation(self):
        with self.assertRaises(ValidationError):
            p = Product(name="   ", category=self.cat_chicken)
            p.full_clean()

    def test_product_price_display_formatting(self):
        self.assertEqual(self.product1.price_display, "250,000 تومان")
        p_no_price = Product.objects.create(
            name="سینه موادی بدون قیمت",
            category=self.cat_chicken,
            parent=self.parent_chicken,
            price_per_unit_rial=None
        )
        self.assertEqual(p_no_price.price_display, "تعیین نشده")

    def test_product_activation_toggle(self):
        self.assertTrue(self.product1.is_active)
        self.product1.is_active = False
        self.product1.save()
        self.assertFalse(self.product1.is_active)
        self.assertEqual(Product.objects.filter(is_active=False).count(), 1)


class SeedCatalogueCommandTestCase(TestCase):
    def test_idempotent_seed_catalogue_execution(self):
        call_command('seed_catalogue')
        
        # Check that only the 4 parent categories exist
        self.assertEqual(Category.objects.count(), 4)
        cat_names = set(Category.objects.values_list('name', flat=True))
        expected_cats = {"مرغ", "گوسفندی", "گوساله", "بوقلمون"}
        self.assertEqual(cat_names, expected_cats)

        # Verify the 4 canonical parent products exist with is_parent=True
        for cat_name in expected_cats:
            cat = Category.objects.get(name=cat_name)
            parent_prod = Product.objects.filter(category=cat, is_parent=True).first()
            self.assertIsNotNone(parent_prod, f"کالای والد برای {cat_name} یافت نشد.")

        # Second execution: verify idempotency (no duplicates created)
        call_command('seed_catalogue')
        self.assertEqual(Category.objects.count(), 4)


class ProductViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.cat, _ = Category.objects.get_or_create(
            slug="chicken",
            defaults={"name": "مرغ", "display_order": 1, "is_active": True}
        )
        self.parent_chicken, _ = Product.objects.get_or_create(
            category=self.cat,
            name="مرغ",
            defaults={"unit": "kg", "is_parent": True, "is_active": True}
        )
        self.p1, _ = Product.objects.get_or_create(
            category=self.cat,
            name="فیله مرغ تستی",
            defaults={
                "code": "101",
                "price_per_unit_rial": 2500000,
                "parent": self.parent_chicken,
                "is_active": True,
            }
        )
        self.p2, _ = Product.objects.get_or_create(
            category=self.cat,
            name="سینه شنسل تستی",
            defaults={
                "code": None,
                "price_per_unit_rial": None,
                "parent": self.parent_chicken,
                "is_active": False,
            }
        )

    def test_product_list_view_status_code(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فیله مرغ تستی")
        self.assertContains(response, "سینه شنسل تستی")

    def test_product_list_search_and_filter(self):
        res = self.client.get(reverse('product_list') + '?q=فیله')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "فیله مرغ تستی")
        self.assertNotContains(res, "سینه شنسل تستی")

        res_active = self.client.get(reverse('product_list') + '?status=active')
        self.assertEqual(res_active.status_code, 200)
        self.assertContains(res_active, "فیله مرغ تستی")
        self.assertNotContains(res_active, "سینه شنسل تستی")

    def test_product_search_persian_and_english_and_arabic_digits(self):
        # English digits: 101
        res1 = self.client.get(reverse('product_list') + '?q=101')
        self.assertEqual(res1.status_code, 200)
        self.assertContains(res1, "فیله مرغ تستی")

        # Persian digits: ۱۰۱
        res2 = self.client.get(reverse('product_list') + '?q=۱۰۱')
        self.assertEqual(res2.status_code, 200)
        self.assertContains(res2, "فیله مرغ تستی")

        # Arabic-Indic digits: ١٠١
        res3 = self.client.get(reverse('product_list') + '?q=١٠١')
        self.assertEqual(res3.status_code, 200)
        self.assertContains(res3, "فیله مرغ تستی")

    def test_product_create_view_post(self):
        post_data = {
            'name': 'گردن مرغ تازه منحصر',
            'category': self.cat.id,
            'code': '1099',
            'unit': 'kg',
            'price_per_unit_rial': 1200000,
            'is_active': True,
            'description': 'بسته‌بندی پاک شده',
        }
        response = self.client.post(reverse('product_create'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(name='گردن مرغ تازه منحصر').exists())

    def test_product_update_view_post(self):
        update_data = {
            'name': 'فیله مرغ ممتاز بروزشده',
            'category': self.cat.id,
            'code': '101',
            'unit': 'kg',
            'price_per_unit_rial': 2600000,
            'is_active': True,
            'description': '',
        }
        response = self.client.post(reverse('product_edit', args=[self.p1.id]), update_data)
        self.assertEqual(response.status_code, 302)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.name, 'فیله مرغ ممتاز بروزشده')
        self.assertEqual(self.p1.price_per_unit_rial, 2600000)

    def test_product_toggle_active_post(self):
        self.assertTrue(self.p1.is_active)
        res = self.client.post(reverse('product_toggle_active', args=[self.p1.id]))
        self.assertEqual(res.status_code, 302)
        self.p1.refresh_from_db()
        self.assertFalse(self.p1.is_active)


class ProductCatalogueCategoryIntegrityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.cat_chicken, _ = Category.objects.get_or_create(
            slug="chicken",
            defaults={"name": "مرغ", "display_order": 1, "is_active": True}
        )
        self.cat_beef, _ = Category.objects.get_or_create(
            slug="beef",
            defaults={"name": "گوساله", "display_order": 3, "is_active": True}
        )
        self.parent_chicken, _ = Product.objects.get_or_create(
            category=self.cat_chicken,
            name="مرغ",
            defaults={"unit": "kg", "is_parent": True, "is_active": True}
        )
        self.parent_beef, _ = Product.objects.get_or_create(
            category=self.cat_beef,
            name="گوساله",
            defaults={"unit": "kg", "is_parent": True, "is_active": True}
        )

    def test_auto_parent_assignment_on_save(self):
        """Creating a child cut without explicit parent automatically links it to the category canonical parent."""
        cut = Product.objects.create(
            name="سینه کبابی مرغ",
            category=self.cat_chicken,
            unit="kg",
        )
        self.assertEqual(cut.parent, self.parent_chicken)

    def test_product_form_category_and_parent_querysets(self):
        """ProductForm orders categories and restricts parent choices to parent products."""
        from products.forms import ProductForm
        form = ProductForm()
        # Category choices must be ordered by display_order
        cat_choices = list(form.fields['category'].queryset)
        self.assertEqual(cat_choices[0].slug, "chicken")
        self.assertTrue(all(cat_choices[i].display_order <= cat_choices[i+1].display_order for i in range(len(cat_choices)-1)))

        # Parent choices must only include parent products (is_parent=True)
        parent_choices = list(form.fields['parent'].queryset)
        self.assertTrue(all(p.is_parent for p in parent_choices))
        self.assertIn(self.parent_chicken, parent_choices)
        self.assertIn(self.parent_beef, parent_choices)

    def test_product_list_parent_first_ordering(self):
        """Product list view displays parent product before child products within each category."""
        Product.objects.create(
            name="بال مرغ",
            category=self.cat_chicken,
            parent=self.parent_chicken,
            unit="kg"
        )
        res = self.client.get(reverse('product_list'))
        self.assertEqual(res.status_code, 200)
        prods = list(res.context['products'])

        chicken_prods = [p for p in prods if p.category_id == self.cat_chicken.id]
        self.assertEqual(chicken_prods[0].id, self.parent_chicken.id)
        self.assertTrue(chicken_prods[0].is_parent)

