from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, datetime
import uuid
from products.models import Category, Product
from sales.models import (
    TareType,
    GoodsReceipt,
    GoodsReceiptItem,
    GoodsIssue,
    GoodsIssueItem,
    WeighingTareRow,
    StockMovement,
    StockMovementDirection,
    StockMovementType,
    ProcessingRecord,
    ProcessingInputLine,
    ProcessingOutputLine,
    ProcessingReconciliationStatus,
    Invoice,
    InvoiceItem,
    InvoiceType,
    GoodsIssueReason,
    DocumentStatus,
    Operator,
)
from sales.services import (
    calculate_tare_and_net,
    get_parent_stock_balance,
    get_product_stock_balance,
    get_product_independent_stock,
    get_product_available_stock,
    get_all_stock_balances,
    finalize_goods_receipt,
    finalize_goods_issue,
    finalize_invoice,
    generate_invoice_from_source_documents,
    cancel_invoice,
    finalize_processing_record,
    InvalidTareWeightError,
    InsufficientStockError,
    BusinessLogicError,
)
from sales.date_utils import (
    to_jalali_date,
    to_jalali_datetime,
    parse_jalali_or_gregorian_date,
    get_tehran_date_range_bounds,
    to_persian_digits,
    to_latin_digits,
)


def get_test_category(name="مرغ", slug="chicken"):
    cat, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
    return cat


class Phase4DataModelsTestCase(TestCase):
    def setUp(self):
        self.category = get_test_category("مرغ", "chicken")
        self.product = Product.objects.create(
            name="سینه سایز",
            code="101",
            category=self.category,
            unit="kg",
            price_per_unit_rial=2000000,
        )
        self.tare_basket = TareType.objects.create(
            name="سبد ۱۵۰۰ گرمی",
            tare_weight_grams=1500,
            is_custom=False,
        )

    def test_tare_type_kg_conversion(self):
        self.assertEqual(self.tare_basket.tare_weight_kg, Decimal("1.5"))
        self.assertIn("1.5", str(self.tare_basket))

    def test_weighing_tare_row_calculation(self):
        receipt = GoodsReceipt.objects.create(
            document_number="REC-001",
            supplier_name="مرغداری کوثر",
            product=self.product,
            gross_weight_kg=Decimal("25.000"),
            total_tare_weight_kg=Decimal("3.000"),
            net_weight_kg=Decimal("22.000"),
        )
        # 2 baskets of 1500g each = 3.000 kg
        row = WeighingTareRow.objects.create(
            goods_receipt=receipt,
            tare_type=self.tare_basket,
            tare_name_snapshot=self.tare_basket.name,
            unit_tare_grams=1500,
            quantity=2,
        )
        self.assertEqual(row.subtotal_tare_kg, Decimal("3.000"))

    def test_goods_receipt_gross_less_than_tare_validation(self):
        receipt = GoodsReceipt(
            document_number="REC-002",
            supplier_name="مرغداری کوثر",
            product=self.product,
            gross_weight_kg=Decimal("2.000"),
            total_tare_weight_kg=Decimal("3.000"),
            net_weight_kg=Decimal("-1.000"),
        )
        with self.assertRaises(ValidationError):
            receipt.clean()

    def test_goods_receipt_unique_document_number(self):
        GoodsReceipt.objects.create(
            document_number="REC-DUP-01",
            supplier_name="تأمین‌کننده ۱",
            product=self.product,
            gross_weight_kg=Decimal("20.000"),
            total_tare_weight_kg=Decimal("1.500"),
            net_weight_kg=Decimal("18.500"),
        )
        with self.assertRaises(IntegrityError):
            GoodsReceipt.objects.create(
                document_number="REC-DUP-01",
                supplier_name="تأمین‌کننده ۲",
                product=self.product,
                gross_weight_kg=Decimal("30.000"),
                total_tare_weight_kg=Decimal("1.500"),
                net_weight_kg=Decimal("28.500"),
            )

    def test_goods_issue_unique_document_number(self):
        GoodsIssue.objects.create(
            document_number="ISS-001",
            product=self.product,
            gross_weight_kg=Decimal("50.000"),
            total_tare_weight_kg=Decimal("4.500"),
            net_weight_kg=Decimal("45.500"),
            goods_owner_name="فروشگاه مرکزی",
            recipient_name="رستوران گلستان",
        )
        with self.assertRaises(IntegrityError):
            GoodsIssue.objects.create(
                document_number="ISS-001",
                product=self.product,
                gross_weight_kg=Decimal("10.000"),
                total_tare_weight_kg=Decimal("1.500"),
                net_weight_kg=Decimal("8.500"),
                goods_owner_name="فروشگاه مرکزی",
                recipient_name="مشتری دیگر",
            )

    def test_product_foreign_key_protection_on_documents(self):
        # Product referenced in a receipt cannot be deleted
        GoodsReceipt.objects.create(
            document_number="REC-PROT-01",
            supplier_name="تأمین‌کننده",
            product=self.product,
            gross_weight_kg=Decimal("10.000"),
            total_tare_weight_kg=Decimal("1.500"),
            net_weight_kg=Decimal("8.500"),
        )
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_stock_movement_ledger(self):
        mv = StockMovement.objects.create(
            product=self.product,
            direction=StockMovementDirection.IN,
            movement_type=StockMovementType.RECEIPT,
            net_weight_kg=Decimal("120.750"),
            reference_document_number="REC-001",
            remarks="ورود اولیه به انبار",
        )
        self.assertEqual(mv.direction, "IN")
        self.assertEqual(mv.net_weight_kg, Decimal("120.750"))
        self.assertIn("+", str(mv))

    def test_invoice_and_item_snapshot(self):
        inv = Invoice.objects.create(
            document_number="INV-001",
            goods_owner_name="فروشگاه پروتئین",
            buyer_name="رستوران صدف",
            driver_name="رضا محمدی",
            total_amount_rial=50000000,
        )
        item = InvoiceItem.objects.create(
            invoice=inv,
            product=self.product,
            product_name_snapshot=self.product.name,
            quantity=1,
            net_weight_kg=Decimal("25.000"),
            unit_price_rial=2000000,
            total_price_rial=50000000,
        )
        self.assertEqual(item.product_name_snapshot, "سینه سایز")
        self.assertEqual(inv.total_amount_display, "5,000,000 تومان")
        self.assertEqual(item.unit_price_display, "200,000 تومان")

    def test_processing_record_and_lines(self):
        output_product = Product.objects.create(
            name="فیله مرغ",
            category=self.category,
            unit="kg",
        )
        prc = ProcessingRecord.objects.create(
            document_number="PRC-001",
            total_input_weight_kg=Decimal("100.000"),
            total_output_weight_kg=Decimal("96.000"),
            unexplained_variance_kg=Decimal("4.000"),
            yield_percentage=Decimal("96.00"),
        )
        in_line = ProcessingInputLine.objects.create(
            processing_record=prc,
            product=self.product,
            net_weight_kg=Decimal("100.000"),
        )
        out_line = ProcessingOutputLine.objects.create(
            processing_record=prc,
            product=output_product,
            net_weight_kg=Decimal("96.000"),
            is_byproduct_or_waste=False,
        )
        self.assertEqual(prc.input_lines.count(), 1)
        self.assertEqual(prc.output_lines.count(), 1)
        self.assertEqual(prc.unexplained_variance_kg, Decimal("4.000"))


class Phase5BusinessServicesTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("فرآورده‌های آزمایشی", "test-processing-cuts")
        self.prod_chicken = Product.objects.create(
            name="مرغ کامل",
            code="100",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=1000000,
        )
        self.prod_fillet = Product.objects.create(
            name="فیله مرغ",
            code="101",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=2500000,
        )
        self.prod_waste = Product.objects.create(
            name="اسکلت بی گردن",
            code="102",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=300000,
        )
        self.tare_basket = TareType.objects.create(
            name="سبد ۱۸۰۰ گرمی",
            tare_weight_grams=1800,
            is_custom=False,
        )
        self.tare_hook = TareType.objects.create(
            name="قلاب ۲۵۰۰ گرمی",
            tare_weight_grams=2500,
            is_custom=False,
        )
        self.tare_cart = TareType.objects.create(
            name="چرخ‌دستی",
            tare_weight_grams=0,
            is_custom=True,
        )

    def test_multi_row_tare_calculation(self):
        # 3 baskets (1.8kg each = 5.4kg) + 2 hooks (2.5kg each = 5.0kg) + 1 custom cart (4.0kg)
        # Total tare = 5.4 + 5.0 + 4.0 = 14.400 kg
        # Gross = 100.000 kg -> Net = 85.600 kg
        tare_entries = [
            {'tare_type': self.tare_basket, 'quantity': 3},
            {'tare_type': self.tare_hook, 'quantity': 2},
            {'tare_type': self.tare_cart, 'quantity': 1, 'custom_tare_grams': 4000},
        ]
        res = calculate_tare_and_net(Decimal("100.000"), tare_entries)
        self.assertEqual(res['gross_weight_kg'], Decimal("100.000"))
        self.assertEqual(res['total_tare_weight_kg'], Decimal("14.400"))
        self.assertEqual(res['net_weight_kg'], Decimal("85.600"))
        self.assertEqual(len(res['tare_rows']), 3)

    def test_tare_calculation_gross_less_than_tare_raises(self):
        tare_entries = [
            {'tare_type': self.tare_basket, 'quantity': 10},  # 18.0 kg tare
        ]
        with self.assertRaises(InvalidTareWeightError):
            calculate_tare_and_net(Decimal("15.000"), tare_entries)

    def test_finalize_goods_receipt_increases_stock(self):
        # Initial stock balance is 0
        self.assertEqual(get_product_stock_balance(self.prod_chicken), Decimal("0.000"))

        tare_entries = [{'tare_type': self.tare_basket, 'quantity': 2}]  # 3.6 kg tare
        # Gross = 50.000 kg -> Net = 46.400 kg
        receipt = finalize_goods_receipt(
            document_number="REC-2026-001",
            supplier_name="کشتارگاه ماکیان",
            product=self.prod_chicken,
            gross_weight_kg=Decimal("50.000"),
            tare_entries=tare_entries,
        )
        self.assertEqual(receipt.net_weight_kg, Decimal("46.400"))
        self.assertEqual(receipt.status, DocumentStatus.FINALIZED)

        # Stock balance should now be exactly 46.400 kg
        self.assertEqual(get_product_stock_balance(self.prod_chicken), Decimal("46.400"))
        self.assertEqual(receipt.tare_rows.count(), 1)

    def test_finalize_goods_issue_deducts_stock(self):
        # First receive 100 kg
        finalize_goods_receipt(
            document_number="REC-IN-100",
            supplier_name="کشتارگاه",
            product=self.prod_chicken,
            gross_weight_kg=Decimal("101.800"),
            tare_entries=[{'tare_type': self.tare_basket, 'quantity': 1}],  # 1.8 kg
        )
        self.assertEqual(get_product_stock_balance(self.prod_chicken), Decimal("100.000"))

        # Issue 40 kg
        issue = finalize_goods_issue(
            document_number="ISS-2026-001",
            product=self.prod_chicken,
            gross_weight_kg=Decimal("41.800"),
            tare_entries=[{'tare_type': self.tare_basket, 'quantity': 1}],  # 1.8 kg
            goods_owner_name="فروشگاه مرکزی",
            recipient_name="رستوران ترنج",
            unit_price_rial=1100000,
        )
        self.assertEqual(issue.net_weight_kg, Decimal("40.000"))
        self.assertEqual(issue.line_total_rial, 44000000)  # 40 * 1,100,000

        # Remaining balance should be 60.000 kg
        self.assertEqual(get_product_stock_balance(self.prod_chicken), Decimal("60.000"))

    def test_finalize_goods_issue_insufficient_stock_rejection(self):
        # Stock balance is 0; attempting to issue 10 kg must raise InsufficientStockError
        tare_entries = [{'tare_type': self.tare_basket, 'quantity': 1}]  # 1.8 kg
        with self.assertRaises(InsufficientStockError):
            finalize_goods_issue(
                document_number="ISS-FAIL-01",
                product=self.prod_chicken,
                gross_weight_kg=Decimal("11.800"),
                tare_entries=tare_entries,
                goods_owner_name="فروشگاه",
                recipient_name="مشتری",
            )
        # Ensure no records were persisted (transaction rollback)
        self.assertFalse(GoodsIssue.objects.filter(document_number="ISS-FAIL-01").exists())
        self.assertFalse(StockMovement.objects.filter(reference_document_number="ISS-FAIL-01").exists())

    def test_finalize_invoice_snapshots_and_sums(self):
        items = [
            {
                'product': self.prod_chicken,
                'quantity': 2,
                'net_weight_kg': Decimal("50.000"),
                'unit_price_rial': 1000000,
            },
            {
                'product': self.prod_fillet,
                'quantity': 1,
                'net_weight_kg': Decimal("20.000"),
                'unit_price_rial': 2500000,
            },
        ]
        # Line 1: 50 * 1,000,000 = 50,000,000 Rial
        # Line 2: 20 * 2,500,000 = 50,000,000 Rial
        # Total = 100,000,000 Rial (10,000,000 Toman)
        invoice = finalize_invoice(
            document_number="INV-2026-901",
            goods_owner_name="فروشگاه مرکزی",
            buyer_name="هتل اسپیناس",
            driver_name="جواد رضایی",
            items_data=items,
        )
        self.assertEqual(invoice.total_amount_rial, 100000000)
        self.assertEqual(invoice.total_amount_display, "10,000,000 تومان")
        self.assertEqual(invoice.items.count(), 2)

        item1 = invoice.items.first()
        self.assertEqual(item1.product_name_snapshot, "مرغ کامل")
        self.assertEqual(item1.total_price_rial, 50000000)

    def test_processing_reconciliation_zero_variance(self):
        # Seed 100 kg whole chicken
        finalize_goods_receipt(
            document_number="REC-PRC-01",
            supplier_name="کشتارگاه",
            product=self.prod_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        # 100 kg in -> 65 kg fillet + 35 kg skeleton waste = 100 kg out (0 variance)
        inputs = [{'product': self.prod_chicken, 'net_weight_kg': Decimal("100.000")}]
        outputs = [
            {'product': self.prod_fillet, 'net_weight_kg': Decimal("65.000"), 'is_byproduct_or_waste': False},
            {'product': self.prod_waste, 'net_weight_kg': Decimal("35.000"), 'is_byproduct_or_waste': True},
        ]
        prc = finalize_processing_record(
            document_number="PRC-BALANCED-01",
            input_items=inputs,
            output_items=outputs,
        )
        self.assertEqual(prc.unexplained_variance_kg, Decimal("0.000"))
        self.assertEqual(prc.yield_percentage, Decimal("100.00"))
        self.assertEqual(prc.reconciliation_status, ProcessingReconciliationStatus.RECONCILED)

        # Inventory check: chicken = 0 kg, fillet = 65 kg, waste = 35 kg
        self.assertEqual(get_product_stock_balance(self.prod_chicken), Decimal("0.000"))
        self.assertEqual(get_product_stock_balance(self.prod_fillet), Decimal("65.000"))
        self.assertEqual(get_product_stock_balance(self.prod_waste), Decimal("35.000"))

    def test_processing_reconciliation_unexplained_loss(self):
        finalize_goods_receipt(
            document_number="REC-PRC-02",
            supplier_name="کشتارگاه",
            product=self.prod_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        # 100 kg in -> 60 kg fillet + 35 kg waste = 95 kg out (5 kg unexplained loss)
        inputs = [{'product': self.prod_chicken, 'net_weight_kg': Decimal("100.000")}]
        outputs = [
            {'product': self.prod_fillet, 'net_weight_kg': Decimal("60.000")},
            {'product': self.prod_waste, 'net_weight_kg': Decimal("35.000")},
        ]
        prc = finalize_processing_record(
            document_number="PRC-LOSS-01",
            input_items=inputs,
            output_items=outputs,
        )
        self.assertEqual(prc.unexplained_variance_kg, Decimal("5.000"))
        self.assertEqual(prc.yield_percentage, Decimal("95.00"))
        self.assertEqual(prc.reconciliation_status, ProcessingReconciliationStatus.UNEXPLAINED_LOSS)

    def test_processing_reconciliation_negative_variance_flag(self):
        finalize_goods_receipt(
            document_number="REC-PRC-03",
            supplier_name="کشتارگاه",
            product=self.prod_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        # 100 kg in -> 102 kg output recorded (anomaly: output > input)
        inputs = [{'product': self.prod_chicken, 'net_weight_kg': Decimal("100.000")}]
        outputs = [
            {'product': self.prod_fillet, 'net_weight_kg': Decimal("102.000")},
        ]
        prc = finalize_processing_record(
            document_number="PRC-ANOMALY-01",
            input_items=inputs,
            output_items=outputs,
        )
        self.assertEqual(prc.unexplained_variance_kg, Decimal("-2.000"))
        self.assertEqual(prc.reconciliation_status, ProcessingReconciliationStatus.NEGATIVE_VARIANCE_FLAGGED)


class Phase7ViewsAndWorkflowsTestCase(TestCase):
    def setUp(self):
        from django.test import Client
        from django.urls import reverse
        self.client = Client()
        self.category = get_test_category("مرغ", "chicken")
        self.product = Product.objects.create(
            name="سینه شنسل",
            code="101",
            category=self.category,
            unit="kg",
            price_per_unit_rial=2200000,
        )
        self.tare_basket = TareType.objects.create(
            name="سبد ۱۵۰۰ گرمی",
            tare_weight_grams=1500,
            is_custom=False,
        )
        self.tare_hook = TareType.objects.create(
            name="قلاب ۲۵۰۰ گرمی",
            tare_weight_grams=2500,
            is_custom=False,
        )

    def test_inventory_overview_view(self):
        from django.urls import reverse
        response = self.client.get(reverse('inventory_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "موجودی لحظه‌ای انبار")
        self.assertContains(response, "سینه شنسل")

    def test_goods_receipt_create_and_list_workflow(self):
        from django.urls import reverse
        # GET form
        res_get = self.client.get(reverse('receipt_create'))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "سبد ۱۵۰۰ گرمی")

        # POST valid receipt: gross 50.000 kg, tare: 2 baskets (3.0 kg) -> net 47.000 kg
        post_data = {
            'product': self.product.id,
            'supplier_name': 'کشتارگاه سپید بال',
            'supplier_document_ref': 'BL-8801',
            'gross_weight_kg': '50.000',
            'package_count': '15',
            'condition_notes': 'کیفیت عالی',
            'remarks': 'بار صبحگاهی',
            'tare_type_id': [str(self.tare_basket.id)],
            'tare_qty': ['2'],
            'custom_tare_grams': ['0'],
        }
        res_post = self.client.post(reverse('receipt_create'), post_data)
        self.assertEqual(res_post.status_code, 302)

        # Verify receipt created and stock increased
        self.assertEqual(GoodsReceipt.objects.count(), 1)
        receipt = GoodsReceipt.objects.first()
        self.assertEqual(receipt.net_weight_kg, Decimal("47.000"))
        self.assertEqual(get_product_stock_balance(self.product), Decimal("47.000"))

        # Check receipt list
        res_list = self.client.get(reverse('receipt_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, receipt.document_number)
        self.assertContains(res_list, "کشتارگاه سپید بال")

    def test_goods_issue_create_success_workflow(self):
        from django.urls import reverse
        # Seed initial stock of 60.000 kg
        finalize_goods_receipt(
            document_number="REC-SEED-01",
            supplier_name="کشتارگاه",
            product=self.product,
            gross_weight_kg=Decimal("60.000"),
            tare_entries=[],
        )
        self.assertEqual(get_product_stock_balance(self.product), Decimal("60.000"))

        # GET issue form
        res_get = self.client.get(reverse('issue_create'))
        self.assertEqual(res_get.status_code, 200)

        # POST valid issue: gross 25.000 kg, tare: 1 basket (1.5 kg) -> net 23.500 kg
        post_data = {
            'product': self.product.id,
            'goods_owner_name': 'فروشگاه مرکزی',
            'recipient_name': 'رستوران نارنجستان',
            'driver_name': 'اصغر کمالی',
            'destination_address': 'خیابان ولیعصر',
            'issue_reason': 'SALE',
            'unit_price_rial': '2300000',
            'gross_weight_kg': '25.000',
            'remarks': 'تحویل تحویل‌دار',
            'tare_type_id': [str(self.tare_basket.id)],
            'tare_qty': ['1'],
            'custom_tare_grams': ['0'],
        }
        res_post = self.client.post(reverse('issue_create'), post_data)
        self.assertEqual(res_post.status_code, 302)

        # Check stock balance decremented: 60 - 23.500 = 36.500 kg
        self.assertEqual(get_product_stock_balance(self.product), Decimal("36.500"))
        self.assertEqual(GoodsIssue.objects.count(), 1)

    def test_goods_issue_insufficient_stock_fails_gracefully(self):
        from django.urls import reverse
        # Stock balance is 0. Attempting to issue 20 kg must fail gracefully
        post_data = {
            'product': self.product.id,
            'goods_owner_name': 'فروشگاه',
            'recipient_name': 'مشتری',
            'driver_name': '',
            'destination_address': '',
            'issue_reason': 'SALE',
            'unit_price_rial': '2000000',
            'gross_weight_kg': '20.000',
            'remarks': '',
            'tare_type_id': [],
            'tare_qty': [],
            'custom_tare_grams': [],
        }
        res_post = self.client.post(reverse('issue_create'), post_data)
        # Should re-render or stay on page with error message
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(GoodsIssue.objects.count(), 0)
        self.assertEqual(get_product_stock_balance(self.product), Decimal("0.000"))

    def test_invoice_create_and_detail_workflow(self):
        from django.urls import reverse
        # GET invoice form
        res_get = self.client.get(reverse('invoice_create'))
        self.assertEqual(res_get.status_code, 200)

        # POST invoice
        post_data = {
            'goods_owner_name': 'فروشگاه پروتئین',
            'buyer_name': 'تالار پذیرایی رویال',
            'driver_name': 'حسین مرادی',
            'remarks': 'تسویه ماهانه',
            'product_id': [str(self.product.id)],
            'net_weight_kg': ['30.000'],
            'quantity': ['2'],
            'unit_price_rial': ['2200000'],
        }
        res_post = self.client.post(reverse('invoice_create'), post_data)
        self.assertEqual(res_post.status_code, 302)

        invoice = Invoice.objects.first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.buyer_name, 'تالار پذیرایی رویال')
        self.assertEqual(invoice.items.count(), 1)

        # Detail view
        res_detail = self.client.get(reverse('invoice_detail', args=[invoice.pk]))
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, invoice.document_number)
        self.assertContains(res_detail, "تالار پذیرایی رویال")

    def test_scale_api_endpoints(self):
        import json
        from django.urls import reverse
        # Test set scale weight
        res_set = self.client.post(
            reverse('scale_set_weight_api'),
            data=json.dumps({'weight': '35.400', 'settling_duration': 0.05}),
            content_type='application/json'
        )
        self.assertEqual(res_set.status_code, 200)
        data_set = res_set.json()
        self.assertTrue(data_set['success'])
        self.assertEqual(data_set['target_weight'], 35.4)

        # Wait for settling
        import time
        time.sleep(0.06)

        # Test read scale weight
        res_read = self.client.get(reverse('scale_read_api'))
        self.assertEqual(res_read.status_code, 200)
        data_read = res_read.json()
        self.assertTrue(data_read['success'])
        self.assertEqual(data_read['weight_kg'], 35.4)
        self.assertTrue(data_read['is_stable'])


class Phase8InventoryLossAndParentModelTestCase(TestCase):
    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.cat = get_test_category("مرغ", "chicken")
        self.parent_chicken = Product.objects.create(
            name="مرغ کامل",
            code="PARENT-CHICKEN",
            category=self.cat,
            unit="kg",
            is_parent=True,
        )
        self.child_fillet = Product.objects.create(
            name="فیله مرغ",
            code="CHICKEN-FILLET",
            category=self.cat,
            unit="kg",
            parent=self.parent_chicken,
        )
        self.child_wings = Product.objects.create(
            name="بال مرغ",
            code="CHICKEN-WINGS",
            category=self.cat,
            unit="kg",
            parent=self.parent_chicken,
        )

    def test_parent_stock_balance_and_child_movements(self):
        # 1. Receipt of 100 kg parent chicken
        finalize_goods_receipt(
            document_number="REC-PARENT-01",
            supplier_name="کشتارگاه سپید",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("100.000"))
        # Child product does not have independent stock, but has available stock through parent
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("0.000"))
        self.assertEqual(get_product_available_stock(self.child_fillet), Decimal("100.000"))

        # 2. Issue of 40 kg fillet child cut (consumes parent stock)
        finalize_goods_issue(
            document_number="ISS-CHILD-01",
            product=self.child_fillet,
            goods_owner_name="واکا پروتئین",
            recipient_name="رستوران البرز",
            gross_weight_kg=Decimal("40.000"),
            tare_entries=[],
        )
        # Parent stock reduced to 60 kg
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("60.000"))
        self.assertEqual(get_product_stock_balance(self.child_wings), Decimal("0.000"))
        self.assertEqual(get_product_available_stock(self.child_wings), Decimal("60.000"))

        # 3. Attempting to issue 70 kg exceeds available 60 kg -> InsufficientStockError
        with self.assertRaises(InsufficientStockError):
            finalize_goods_issue(
                document_number="ISS-OVER-01",
                product=self.child_wings,
                goods_owner_name="واکا پروتئین",
                recipient_name="رستوران البرز",
                gross_weight_kg=Decimal("70.000"),
                tare_entries=[],
            )

    def test_inventory_loss_calculation(self):
        from sales.services import calculate_inventory_loss
        # Receive 100 kg parent chicken
        finalize_goods_receipt(
            document_number="REC-LOSS-01",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        # Issue 55 kg fillet and 35 kg wings (total 90 kg child cuts)
        finalize_goods_issue(
            document_number="ISS-LOSS-01",
            product=self.child_fillet,
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری ۱",
            gross_weight_kg=Decimal("55.000"),
            tare_entries=[],
        )
        finalize_goods_issue(
            document_number="ISS-LOSS-02",
            product=self.child_wings,
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری ۲",
            gross_weight_kg=Decimal("35.000"),
            tare_entries=[],
        )

        loss_data = calculate_inventory_loss(self.parent_chicken)
        self.assertEqual(loss_data['parent_in_kg'], Decimal("100.000"))
        self.assertEqual(loss_data['child_out_kg'], Decimal("90.000"))
        self.assertEqual(loss_data['loss_kg'], Decimal("10.000"))
        self.assertEqual(loss_data['loss_pct'], Decimal("10.00"))
        self.assertEqual(loss_data['yield_pct'], Decimal("90.00"))
        self.assertEqual(len(loss_data['cuts_breakdown']), 2)

    def test_inventory_loss_report_view(self):
        from django.urls import reverse
        res = self.client.get(reverse('report_loss'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "گزارش جامع افت و راندمان انبار")
        self.assertContains(res, "واکا پروتئین")

    def test_goods_receipt_with_operator_and_backdated_document_date(self):
        from django.urls import reverse
        from sales.models import Operator
        Operator.objects.get_or_create(name="متصدی ۱", defaults={"display_order": 1, "is_active": True})

        post_data = {
            'supplier_name': 'کشتارگاه مرکزی',
            'supplier_document_ref': 'REF-1234',
            'document_date': '1403/05/10',
            'operator_select': 'متصدی ۱',
            'items_json': f'[{{"product_id": {self.parent_chicken.id}, "gross_weight_kg": 50.0, "total_tare_weight_kg": 0.0, "net_weight_kg": 50.0, "tare_entries": []}}]',
        }
        res = self.client.post(reverse('receipt_create'), post_data)
        self.assertEqual(res.status_code, 302)

        receipt = GoodsReceipt.objects.filter(supplier_name='کشتارگاه مرکزی').first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.document_date, date(2024, 7, 31))
        self.assertEqual(receipt.operator_name, 'متصدی ۱')

    def test_goods_receipt_form_errors_and_data_retention(self):
        from django.urls import reverse
        # Submit invalid document_date
        post_data = {
            'supplier_name': 'تأمین‌کننده تست',
            'supplier_document_ref': 'REF-INVALID',
            'document_date': '1403/13/45',  # Invalid date
            'operator_select': '__custom__',
            'operator_custom': 'علی انباردار',
            'items_json': '[]',
        }
        res = self.client.post(reverse('receipt_create'), post_data)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "خطاهای ثبت رسید ورود کالا")
        self.assertContains(res, "REF-INVALID")
        self.assertContains(res, "علی انباردار")


class Phase9ReportingAndAnalyticsTestCase(TestCase):
    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.category = get_test_category("مرغ", "chicken")
        self.prod1 = Product.objects.create(
            name="فیله مرغ",
            code="101",
            category=self.category,
            unit="kg",
            price_per_unit_rial=2500000,
        )
        self.prod2 = Product.objects.create(
            name="سینه شنسل",
            code="102",
            category=self.category,
            unit="kg",
            price_per_unit_rial=2000000,
        )
        # Create finalized invoice
        self.inv = finalize_invoice(
            document_number="INV-REP-01",
            goods_owner_name="فروشگاه مرکزی",
            buyer_name="رستوران نمونه",
            driver_name="علی اکبری",
            items_data=[
                {
                    'product': self.prod1,
                    'net_weight_kg': Decimal("20.000"),
                    'quantity': 1,
                    'unit_price_rial': 2500000,
                },
                {
                    'product': self.prod2,
                    'net_weight_kg': Decimal("10.000"),
                    'quantity': 1,
                    'unit_price_rial': 2000000,
                },
            ]
        )

    def test_reports_hub_view(self):
        from django.urls import reverse
        res = self.client.get(reverse('reports_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "مرکز گزارش‌ها")
        self.assertContains(res, "مجموع فروش ثبتی")

    def test_sales_summary_report_filtering(self):
        from django.urls import reverse
        # Unfiltered
        res = self.client.get(reverse('report_sales'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "فیله مرغ")
        # Total revenue: (20*2.5m) + (10*2m) = 50m + 20m = 70,000,000 Rial = 7,000,000 Toman
        self.assertEqual(res.context['total_revenue_rial'], 70000000)
        self.assertEqual(res.context['total_sold_weight_kg'], Decimal("30.000"))

        # Filter by buyer
        res_buyer = self.client.get(reverse('report_sales') + '?buyer=نمونه')
        self.assertEqual(res_buyer.status_code, 200)
        self.assertEqual(res_buyer.context['invoice_count'], 1)
        self.assertContains(res_buyer, "نمونه")

        # Filter by non-matching buyer
        res_none = self.client.get(reverse('report_sales') + '?buyer=ناموجود')
        self.assertEqual(res_none.status_code, 200)
        self.assertEqual(res_none.context['invoice_count'], 0)

    def test_inventory_balance_report(self):
        from django.urls import reverse
        res = self.client.get(reverse('report_inventory'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ممیزی و موازنه موجودی انبار")
        self.assertContains(res, "فیله مرغ")

    def test_inventory_loss_report(self):
        from django.urls import reverse
        res = self.client.get(reverse('report_loss'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "گزارش جامع افت و راندمان انبار")

    def test_tare_analysis_report(self):
        from django.urls import reverse
        res = self.client.get(reverse('report_tare'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "تحلیل آماری و فراوانی مصرف ظروف پارسنگ")

    def test_export_sales_csv(self):
        from django.urls import reverse
        res = self.client.get(reverse('export_sales_csv'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8-sig')
        content = res.content.decode('utf-8')
        self.assertIn('شماره فاکتور', content)
        self.assertIn('INV-REP-01', content)
        self.assertIn('فیله مرغ', content)

    def test_export_inventory_csv(self):
        from django.urls import reverse
        res = self.client.get(reverse('export_inventory_csv'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8-sig')
        content = res.content.decode('utf-8')
        self.assertIn('ردیف', content)
        self.assertIn('فیله مرغ', content)


class Phase10BackupAndDeploymentTestCase(TestCase):
    def test_backup_database_command_execution(self):
        import tempfile
        import sqlite3
        from pathlib import Path
        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as temp_dir:
            call_command('backup_database', output_dir=temp_dir)
            backup_files = list(Path(temp_dir).glob("*.sqlite3"))
            self.assertEqual(len(backup_files), 1)

            backup_file = backup_files[0]
            self.assertTrue(backup_file.stat().st_size > 0)

            # Check SQLite integrity
            conn = sqlite3.connect(str(backup_file))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()[0]
            conn.close()
            self.assertEqual(res, "ok")

    def test_restore_database_validation_and_recovery(self):
        import tempfile
        import sqlite3
        from pathlib import Path
        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Create backup
            call_command('backup_database', output_dir=temp_dir)
            backup_file = list(Path(temp_dir).glob("*.sqlite3"))[0]

            # 2. Restore backup into target file
            target_restored_db = Path(temp_dir) / "restored_test.sqlite3"
            call_command('restore_database', str(backup_file), target_db=str(target_restored_db), no_input=True)

            # 3. Verify restored file exists and has ok integrity
            self.assertTrue(target_restored_db.exists())
            conn = sqlite3.connect(str(target_restored_db))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            self.assertEqual(cursor.fetchone()[0], "ok")
            conn.close()

    def test_restore_corrupt_file_rejected(self):
        import tempfile
        from pathlib import Path
        from django.core.management import call_command, CommandError

        with tempfile.TemporaryDirectory() as temp_dir:
            corrupt_file = Path(temp_dir) / "corrupt.sqlite3"
            corrupt_file.write_bytes(b"THIS IS CORRUPT GARBAGE DATA AND NOT SQLITE")

            with self.assertRaises(CommandError):
                call_command('restore_database', str(corrupt_file), no_input=True)

    def test_django_system_and_deployment_check(self):
        from django.core.management import call_command
        # Verifies that system check passes with 0 issues
        call_command('check')


class JalaliDateUtilsTestCase(TestCase):
    def test_persian_and_latin_digit_conversion(self):
        self.assertEqual(to_persian_digits("0123456789"), "۰۱۲۳۴۵۶۷۸۹")
        self.assertEqual(to_persian_digits(1405), "۱۴۰۵")
        self.assertEqual(to_persian_digits(None), "")
        self.assertEqual(to_latin_digits("۰۱۲۳۴۵۶۷۸۹"), "0123456789")
        self.assertEqual(to_latin_digits("٠١٢٣٤٥٦٧٨٩"), "0123456789")
        self.assertEqual(to_latin_digits(""), "")

    def test_to_jalali_date_conversion(self):
        # 2026-10-24 is 1405-08-02 in Jalali calendar
        g_date = date(2026, 10, 24)
        j_str = to_jalali_date(g_date, persian_digits=False)
        self.assertEqual(j_str, "1405/08/02")
        j_str_fa = to_jalali_date(g_date, persian_digits=True)
        self.assertEqual(j_str_fa, "۱۴۰۵/۰۸/۰۲")

    def test_parse_jalali_or_gregorian_date(self):
        # Jalali with Latin digits
        parsed_j = parse_jalali_or_gregorian_date("1405/08/02")
        self.assertEqual(parsed_j, date(2026, 10, 24))

        # Jalali with dash separator
        parsed_j_dash = parse_jalali_or_gregorian_date("1405-08-02")
        self.assertEqual(parsed_j_dash, date(2026, 10, 24))

        # Jalali with Persian digits
        parsed_j_fa = parse_jalali_or_gregorian_date("۱۴۰۵/۰۸/۰۲")
        self.assertEqual(parsed_j_fa, date(2026, 10, 24))

        # Gregorian date
        parsed_g = parse_jalali_or_gregorian_date("2026-10-24")
        self.assertEqual(parsed_g, date(2026, 10, 24))

        # None or empty returns None
        self.assertIsNone(parse_jalali_or_gregorian_date(""))
        self.assertIsNone(parse_jalali_or_gregorian_date(None))

    def test_jalali_leap_year_handling(self):
        # In the Persian calendar:
        # Year 1403 is a leap year (kabiseh), so Esfand has 30 days (1403/12/30 is valid)
        parsed_leap = parse_jalali_or_gregorian_date("1403/12/30")
        self.assertEqual(parsed_leap, date(2025, 3, 20))

        # Year 1404 is NOT a leap year, so Esfand has only 29 days (1404/12/30 is invalid)
        with self.assertRaises(ValueError):
            parse_jalali_or_gregorian_date("1404/12/30")

    def test_invalid_date_formats_raise(self):
        with self.assertRaises(ValueError):
            parse_jalali_or_gregorian_date("not-a-date")
        with self.assertRaises(ValueError):
            parse_jalali_or_gregorian_date("1405/13/01")  # Month 13 is invalid

    def test_get_tehran_date_range_bounds(self):
        start_d = date(2026, 10, 24)
        end_d = date(2026, 10, 25)
        start_dt, end_dt = get_tehran_date_range_bounds(start_d, end_d)
        self.assertIsNotNone(start_dt)
        self.assertIsNotNone(end_dt)
        self.assertEqual(start_dt.hour, 0)
        self.assertEqual(start_dt.minute, 0)
        self.assertEqual(end_dt.hour, 23)
        self.assertEqual(end_dt.minute, 59)

    def test_templatetag_filters(self):
        from sales.templatetags.jalali_tags import (
            jdate_filter,
            fa_digits_filter,
            format_weight_kg_filter,
            toman_display_filter,
        )
        self.assertEqual(fa_digits_filter(12345), "۱۲۳۴۵")
        self.assertEqual(format_weight_kg_filter(Decimal("12.500")), "۱۲.۵۰۰")
        self.assertEqual(toman_display_filter(50000000), "۵,۰۰۰,۰۰۰")  # 50,000,000 Rial = 5,000,000 Toman


class MultiItemGoodsIssueTestCase(TestCase):
    def setUp(self):
        self.category = get_test_category("گوشت قرمز", "red-meat")
        self.prod_beef = Product.objects.create(
            name="راسته گوساله",
            code="B-101",
            category=self.category,
            unit="kg",
            price_per_unit_rial=6000000,
        )
        self.prod_mutton = Product.objects.create(
            name="ران گوسفندی",
            code="M-201",
            category=self.category,
            unit="kg",
            price_per_unit_rial=7500000,
        )
        self.tare_basket = TareType.objects.create(
            name="سبد ۱۵۰۰ گرمی",
            tare_weight_grams=1500,
            is_custom=False,
        )
        self.tare_hook = TareType.objects.create(
            name="قلاب ۲۵۰۰ گرمی",
            tare_weight_grams=2500,
            is_custom=False,
        )
        # Seed stock: 100 kg beef, 50 kg mutton
        finalize_goods_receipt(
            document_number="REC-BEEF-01",
            supplier_name="کشتارگاه نمونه",
            product=self.prod_beef,
            gross_weight_kg=Decimal("101.500"),
            tare_entries=[{'tare_type': self.tare_basket, 'quantity': 1}],  # 1.5 kg tare -> 100 kg net
        )
        finalize_goods_receipt(
            document_number="REC-MUTTON-01",
            supplier_name="کشتارگاه نمونه",
            product=self.prod_mutton,
            gross_weight_kg=Decimal("52.500"),
            tare_entries=[{'tare_type': self.tare_hook, 'quantity': 1}],  # 2.5 kg tare -> 50 kg net
        )

    def test_multi_item_goods_issue_creation_and_inventory(self):
        items_data = [
            {
                'product': self.prod_beef,
                'gross_weight_kg': Decimal("31.500"),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],  # 1.5kg tare -> 30kg net
                'unit_price_rial': 6000000,
                'remarks': 'راسته بدون چربی',
            },
            {
                'product': self.prod_mutton,
                'gross_weight_kg': Decimal("22.500"),
                'tare_entries': [{'tare_type': self.tare_hook, 'quantity': 1}],  # 2.5kg tare -> 20kg net
                'unit_price_rial': 7500000,
                'remarks': 'ران قلوه‌گاه جدا',
            },
        ]
        issue = finalize_goods_issue(
            document_number="ISS-MULTI-01",
            goods_owner_name="فروشگاه مرکزی",
            recipient_name="رستوران البرز",
            driver_name="رضا رضایی",
            destination_address="ونک",
            items_data=items_data,
        )
        self.assertEqual(issue.items.count(), 2)
        self.assertEqual(issue.total_gross_weight_kg, Decimal("54.000"))
        self.assertEqual(issue.total_net_weight_kg, Decimal("50.000"))
        # 30kg * 6,000,000 + 20kg * 7,500,000 = 180,000,000 + 150,000,000 = 330,000,000 Rials
        self.assertEqual(issue.total_amount_rial, 330000000)

        # Check stock movements: 2 OUT movements
        beef_out = StockMovement.objects.filter(
            product=self.prod_beef,
            reference_document_number="ISS-MULTI-01",
            direction=StockMovementDirection.OUT
        ).first()
        self.assertIsNotNone(beef_out)
        self.assertEqual(beef_out.net_weight_kg, Decimal("30.000"))

        mutton_out = StockMovement.objects.filter(
            product=self.prod_mutton,
            reference_document_number="ISS-MULTI-01",
            direction=StockMovementDirection.OUT
        ).first()
        self.assertIsNotNone(mutton_out)
        self.assertEqual(mutton_out.net_weight_kg, Decimal("20.000"))

        # Check remaining stock: beef 100 - 30 = 70 kg, mutton 50 - 20 = 30 kg
        self.assertEqual(get_product_stock_balance(self.prod_beef), Decimal("70.000"))
        self.assertEqual(get_product_stock_balance(self.prod_mutton), Decimal("30.000"))

        # Verify tare rows per item
        item1 = issue.items.filter(product=self.prod_beef).first()
        self.assertEqual(item1.tare_rows.count(), 1)
        self.assertEqual(item1.net_weight_kg, Decimal("30.000"))
        self.assertEqual(item1.line_total_rial, 180000000)

    def test_multi_item_aggregate_same_product_demand_validation(self):
        # We have 100 kg beef. If 2 items ask for 60 kg + 50 kg = 110 kg, it must fail atomically!
        items_data = [
            {
                'product': self.prod_beef,
                'gross_weight_kg': Decimal("61.500"),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],  # 60 kg net
            },
            {
                'product': self.prod_beef,
                'gross_weight_kg': Decimal("51.500"),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],  # 50 kg net
            },
        ]
        with self.assertRaises(InsufficientStockError):
            finalize_goods_issue(
                document_number="ISS-OVERDEMAND-01",
                goods_owner_name="فروشگاه مرکزی",
                recipient_name="رستوران",
                items_data=items_data,
            )
        # Verify rollback: stock remains untouched at 100 kg
        self.assertEqual(get_product_stock_balance(self.prod_beef), Decimal("100.000"))
        self.assertFalse(GoodsIssue.objects.filter(document_number="ISS-OVERDEMAND-01").exists())

    def test_multi_item_insufficient_stock_rollback_across_products(self):
        # Mutton only has 50 kg. Asking for 60 kg must roll back everything, including beef.
        items_data = [
            {
                'product': self.prod_beef,
                'gross_weight_kg': Decimal("11.500"),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],  # 10 kg net
            },
            {
                'product': self.prod_mutton,
                'gross_weight_kg': Decimal("62.500"),
                'tare_entries': [{'tare_type': self.tare_hook, 'quantity': 1}],  # 60 kg net > 50 kg available
            },
        ]
        with self.assertRaises(InsufficientStockError):
            finalize_goods_issue(
                document_number="ISS-FAIL-ROLLBACK",
                goods_owner_name="فروشگاه مرکزی",
                recipient_name="مشتری",
                items_data=items_data,
            )
        self.assertEqual(get_product_stock_balance(self.prod_beef), Decimal("100.000"))
        self.assertEqual(get_product_stock_balance(self.prod_mutton), Decimal("50.000"))
        self.assertFalse(GoodsIssue.objects.filter(document_number="ISS-FAIL-ROLLBACK").exists())


class LegacyGoodsIssueCompatibilityTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("گوشت", "meat")
        self.prod = Product.objects.create(
            name="قلوه‌گاه",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=4000000,
        )

    def test_legacy_single_item_properties(self):
        # Emulate a legacy issue without child GoodsIssueItem rows
        legacy_issue = GoodsIssue.objects.create(
            document_number="ISS-LEGACY-01",
            product=self.prod,
            gross_weight_kg=Decimal("15.500"),
            total_tare_weight_kg=Decimal("1.500"),
            net_weight_kg=Decimal("14.000"),
            unit_price_rial=4000000,
            line_total_rial=56000000,
            goods_owner_name="فروشگاه",
            recipient_name="مشتری قدیمی",
        )
        self.assertEqual(legacy_issue.items_count, 1)
        self.assertEqual(legacy_issue.aggregate_net_weight, Decimal("14.000"))
        self.assertEqual(legacy_issue.primary_product_name, "قلوه‌گاه")
        self.assertEqual(legacy_issue.effective_total_amount_rial, 56000000)

    def test_legacy_issue_with_null_product_graceful_handling(self):
        # Edge case: incomplete legacy record with product=None
        legacy_issue_null = GoodsIssue.objects.create(
            document_number="ISS-LEGACY-NULL",
            product=None,
            gross_weight_kg=Decimal("10.000"),
            total_tare_weight_kg=Decimal("0.000"),
            net_weight_kg=Decimal("10.000"),
            goods_owner_name="فروشگاه",
            recipient_name="مشتری",
        )
        self.assertEqual(legacy_issue_null.items_count, 0)
        self.assertEqual(legacy_issue_null.primary_product_name, "بدون کالا")
        self.assertEqual(legacy_issue_null.aggregate_net_weight, Decimal("10.000"))

    def test_legacy_issue_detail_view_renders_successfully(self):
        from django.test import Client
        from django.urls import reverse
        client = Client()
        legacy_issue = GoodsIssue.objects.create(
            document_number="ISS-LEGACY-VIEW",
            product=self.prod,
            gross_weight_kg=Decimal("20.000"),
            total_tare_weight_kg=Decimal("1.500"),
            net_weight_kg=Decimal("18.500"),
            goods_owner_name="فروشگاه مرکزی",
            recipient_name="رستوران سنتی",
        )
        res = client.get(reverse('issue_detail', args=[legacy_issue.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ISS-LEGACY-VIEW")
        self.assertContains(res, "قلوه‌گاه")


class InvoiceFromSourceWorkflowTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("طیور", "poultry")
        self.product = Product.objects.create(
            name="بوقلمون",
            code="B-01",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=3000000,
        )
        self.tare = TareType.objects.create(
            name="سبد ۲ کیلویی",
            tare_weight_grams=2000,
            is_custom=False,
        )
        # Receipt 50 kg
        self.receipt = finalize_goods_receipt(
            document_number="REC-SRC-01",
            supplier_name="مزرعه بوقلمون پارس",
            product=self.product,
            gross_weight_kg=Decimal("52.000"),
            tare_entries=[{'tare_type': self.tare, 'quantity': 1}],
        )
        # Issue 20 kg
        self.issue = finalize_goods_issue(
            document_number="ISS-SRC-01",
            goods_owner_name="فروشگاه پروتئینی",
            recipient_name="رستوران شاندیز",
            product=self.product,
            gross_weight_kg=Decimal("22.000"),
            tare_entries=[{'tare_type': self.tare, 'quantity': 1}],
            unit_price_rial=3500000,
        )

    def test_sales_invoice_from_goods_issue_no_double_inventory_deduction(self):
        # Record count of stock movements before invoicing
        initial_movement_count = StockMovement.objects.count()
        initial_stock = get_product_stock_balance(self.product)

        # Generate sales invoice from source issue
        invoice = generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[self.issue.id],
            buyer_or_supplier_name="رستوران شاندیز",
        )
        self.assertEqual(invoice.invoice_type, InvoiceType.SALE)
        self.assertEqual(invoice.items.count(), 1)
        item = invoice.items.first()
        self.assertEqual(item.net_weight_kg, Decimal("20.000"))
        self.assertEqual(item.unit_price_rial, 3500000)
        self.assertEqual(item.total_price_rial, 70000000)  # 20 * 3,500,000

        # Source issue must now be locked to invoice
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.invoice, invoice)
        self.assertTrue(self.issue.is_invoiced)

        # CRITICAL TEST: Generating invoice must NOT create any new StockMovements!
        final_movement_count = StockMovement.objects.count()
        self.assertEqual(final_movement_count, initial_movement_count)
        self.assertEqual(get_product_stock_balance(self.product), initial_stock)

    def test_purchase_invoice_from_goods_receipt_requires_price(self):
        # Attempting without purchase price must raise BusinessLogicError
        with self.assertRaises(BusinessLogicError):
            generate_invoice_from_source_documents(
                source_type='PURCHASE',
                document_ids=[self.receipt.id],
                prices_override={},  # Missing purchase price
            )

        # Supplying purchase price: 2,800,000 Rials/kg
        invoice = generate_invoice_from_source_documents(
            source_type='PURCHASE',
            document_ids=[self.receipt.id],
            prices_override={f"receipt_{self.receipt.id}": 2800000},
        )
        self.assertEqual(invoice.invoice_type, InvoiceType.PURCHASE)
        self.assertEqual(invoice.items.count(), 1)
        item = invoice.items.first()
        self.assertEqual(item.source_receipt, self.receipt)
        self.assertEqual(item.net_weight_kg, Decimal("50.000"))
        self.assertEqual(item.unit_price_rial, 2800000)
        self.assertEqual(item.total_price_rial, 140000000)  # 50 * 2,800,000

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.invoice, invoice)
        self.assertTrue(self.receipt.is_invoiced)

    def test_prevent_duplicate_invoicing_of_same_source(self):
        generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[self.issue.id],
        )
        # Second attempt must be rejected
        with self.assertRaises(BusinessLogicError):
            generate_invoice_from_source_documents(
                source_type='SALE',
                document_ids=[self.issue.id],
            )

    def test_safe_invoice_cancellation_releases_sources_without_deletion(self):
        invoice = generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[self.issue.id],
        )
        self.issue.refresh_from_db()
        self.assertTrue(self.issue.is_invoiced)

        # Cancel invoice
        cancel_invoice(invoice, cancellation_reason="اصلاح اقلام فاکتور")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, DocumentStatus.CANCELLED)
        self.assertIn("اصلاح اقلام فاکتور", invoice.remarks)

        # Source issue must be freed
        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.invoice)
        self.assertFalse(self.issue.is_invoiced)

        # Invoice record still exists in database for financial audit
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk).exists())


class InvoiceQuantityDisplayAndCalculationsTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("بسته‌بندی", "packaging")
        self.prod = Product.objects.create(
            name="تخم مرغ دانه‌ای",
            category=self.cat,
            unit="piece",
            price_per_unit_rial=50000,
        )

    def test_large_six_digit_quantity_calculation_and_display(self):
        from django.test import Client
        from django.urls import reverse
        client = Client()

        # 150,000 pieces * 50,000 Rials = 7,500,000,000 Rials (750,000,000 Tomans)
        items = [{
            'product': self.prod,
            'quantity': 150000,
            'net_weight_kg': Decimal("150.000"),
            'unit_price_rial': 50000,
        }]
        inv = finalize_invoice(
            document_number="INV-QTY-001",
            goods_owner_name="فروشگاه",
            buyer_name="پخش سراسری",
            items_data=items,
        )
        self.assertEqual(inv.total_amount_rial, 7500000000)
        item = inv.items.first()
        self.assertEqual(item.quantity, 150000)
        self.assertEqual(item.total_price_rial, 7500000000)

        # Check detail page rendering
        res = client.get(reverse('invoice_detail', args=[inv.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "INV-QTY-001")
        # Ensure 6-digit quantity is rendered in the response with Persian digits
        self.assertContains(res, "۱۵۰۰۰۰")
        # Ensure column width is sufficient and tabular-nums is applied
        self.assertContains(res, "tabular-nums")

    def test_invoice_form_renders_wide_quantity_column(self):
        from django.test import Client
        from django.urls import reverse
        client = Client()
        res = client.get(reverse('invoice_create'))
        self.assertEqual(res.status_code, 200)
        # Check that quantity column style is widened
        self.assertContains(res, "width: 125px")


class IdempotencyTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("مرغ", "chicken")
        self.prod = Product.objects.create(
            name="شنسل",
            category=self.cat,
            unit="kg",
        )

    def test_goods_receipt_idempotency_prevents_duplicate_stock(self):
        key = str(uuid.uuid4())
        r1 = finalize_goods_receipt(
            document_number="REC-IDEM-01",
            supplier_name="تأمین‌کننده",
            product=self.prod,
            gross_weight_kg=Decimal("50.000"),
            tare_entries=[],
            idempotency_key=key,
        )
        # Calling again with identical key returns the same receipt without posting another stock movement
        r2 = finalize_goods_receipt(
            document_number="REC-IDEM-02",
            supplier_name="تأمین‌کننده دیگر",
            product=self.prod,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
            idempotency_key=key,
        )
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(GoodsReceipt.objects.filter(idempotency_key=key).count(), 1)
        # Stock balance must be 50 kg, NOT 150 kg
        self.assertEqual(get_product_stock_balance(self.prod), Decimal("50.000"))

    def test_goods_issue_idempotency_prevents_duplicate_deduction(self):
        # Stock is 50 kg
        finalize_goods_receipt(
            document_number="REC-SEED-IDEM",
            supplier_name="تأمین‌کننده",
            product=self.prod,
            gross_weight_kg=Decimal("50.000"),
            tare_entries=[],
        )
        key = str(uuid.uuid4())
        i1 = finalize_goods_issue(
            document_number="ISS-IDEM-01",
            goods_owner_name="فروشگاه",
            recipient_name="مشتری",
            product=self.prod,
            gross_weight_kg=Decimal("20.000"),
            tare_entries=[],
            idempotency_key=key,
        )
        i2 = finalize_goods_issue(
            document_number="ISS-IDEM-02",
            goods_owner_name="فروشگاه",
            recipient_name="مشتری",
            product=self.prod,
            gross_weight_kg=Decimal("20.000"),
            tare_entries=[],
            idempotency_key=key,
        )
        self.assertEqual(i1.id, i2.id)
        self.assertEqual(GoodsIssue.objects.filter(idempotency_key=key).count(), 1)
        # Stock balance must be 50 - 20 = 30 kg, NOT 10 kg
        self.assertEqual(get_product_stock_balance(self.prod), Decimal("30.000"))


class GoodsReceiptDetailAndSearchTestCase(TestCase):
    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.cat = get_test_category("گوشت گوسفند", "sheep")
        self.prod = Product.objects.create(
            name="راسته بره",
            code="BRH-01",
            category=self.cat,
            unit="kg",
        )
        self.tare = TareType.objects.create(
            name="سبد ۲ کیلوگرمی",
            tare_weight_grams=2000,
        )
        self.receipt = finalize_goods_receipt(
            document_number="REC-20261024-0099",
            supplier_name="کشتارگاه مرصاد",
            product=self.prod,
            gross_weight_kg=Decimal("42.000"),
            tare_entries=[{'tare_type': self.tare, 'quantity': 1}],
            supplier_document_ref="BAR-9901",
            condition_notes="بسته‌بندی سالم و دمای ۴ درجه",
        )

    def test_goods_receipt_detail_view(self):
        from django.urls import reverse
        res = self.client.get(reverse('receipt_detail', args=[self.receipt.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "رسید ورود کالا")
        self.assertContains(res, "REC-20261024-0099")
        self.assertContains(res, "کشتارگاه مرصاد")
        self.assertContains(res, "راسته بره")
        self.assertContains(res, "۴۰.۰۰۰")  # Net weight 40.000 kg

    def test_goods_receipt_create_form_search_elements(self):
        from django.urls import reverse
        res = self.client.get(reverse('receipt_create'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="product-search"')
        self.assertContains(res, 'id="category-filters"')
        self.assertContains(res, 'id="selected-product-card"')
        self.assertContains(res, 'id="btn-clear-selection"')
        self.assertContains(res, 'id="btn-add-product-to-receipt"')
        self.assertContains(res, 'id="committed-receipt-items-table"')
        self.assertContains(res, 'name="idempotency_key"')


class ProductSelectionFeedbackTestCase(TestCase):
    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.cat1 = get_test_category("گوشت گاو", "beef")
        self.cat2 = get_test_category("مرغ و ماکیان", "chicken")
        self.prod1 = Product.objects.create(
            name="فیله گوساله",
            code="B-101",
            category=self.cat1,
            unit="kg",
            price_per_unit_rial=4500000,
        )
        self.prod2 = Product.objects.create(
            name="سینه مرغ",
            code="C-201",
            category=self.cat2,
            unit="kg",
            price_per_unit_rial=1800000,
        )

    def test_receipt_form_contains_selected_product_card_elements(self):
        from django.urls import reverse
        res = self.client.get(reverse('receipt_create'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="selected-product-card"')
        self.assertContains(res, 'id="selected-card-name"')
        self.assertContains(res, 'id="selected-card-code"')
        self.assertContains(res, 'id="selected-card-category"')
        self.assertContains(res, 'id="btn-clear-selection"')
        self.assertContains(res, 'id="active-line-product-id"')

    def test_issue_form_contains_selected_product_card_elements(self):
        from django.urls import reverse
        res = self.client.get(reverse('issue_create'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="selected-product-card"')
        self.assertContains(res, 'id="selected-card-name"')
        self.assertContains(res, 'id="selected-card-stock"')
        self.assertContains(res, 'id="btn-clear-selection"')
        self.assertContains(res, 'id="active-issue-product-id"')

    def test_invoice_form_contains_search_and_selected_card_elements(self):
        from django.urls import reverse
        res = self.client.get(reverse('invoice_create'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="product-search"')
        self.assertContains(res, 'id="category-filters"')
        self.assertContains(res, 'id="selected-product-card"')
        self.assertContains(res, 'id="btn-add-line-to-table"')
        self.assertContains(res, 'id="committed-invoice-table"')

    def test_server_side_validation_rejects_missing_product_on_receipt(self):
        from django.urls import reverse
        res = self.client.post(reverse('receipt_create'), {
            'supplier_name': 'کشتارگاه کوثر',
            'product': '',
            'gross_weight_kg': '10.000',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "لطفاً کالا را انتخاب نمایید")

    def test_server_side_validation_rejects_invalid_product_on_receipt(self):
        from django.urls import reverse
        res = self.client.post(reverse('receipt_create'), {
            'supplier_name': 'کشتارگاه کوثر',
            'product': '999999',  # non-existent
            'gross_weight_kg': '10.000',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "کالای انتخاب‌شده معتبر نمی‌باشد")


class MultiItemGoodsReceiptTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("گوشت گوساله", "beef")
        self.p1 = Product.objects.create(name="راسته گوساله", code="B01", category=self.cat, unit="kg")
        self.p2 = Product.objects.create(name="ران گوساله", code="B02", category=self.cat, unit="kg")
        self.tare_basket = TareType.objects.create(name="سبد ۲ کیلویی", tare_weight_grams=2000)

    def test_multi_item_goods_receipt_creation_and_stock_movements(self):
        items_data = [
            {
                'product': self.p1,
                'gross_weight_kg': Decimal('32.000'),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],
                'package_count': 2,
                'condition_notes': 'عالی',
                'remarks': 'ردیف ۱',
            },
            {
                'product': self.p2,
                'gross_weight_kg': Decimal('54.000'),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 2}],  # 4 kg tare
                'package_count': 3,
                'condition_notes': 'سالم',
                'remarks': 'ردیف ۲',
            },
        ]
        receipt = finalize_goods_receipt(
            document_number="REC-MULTI-001",
            supplier_name="دامداری نمونه",
            items_data=items_data,
        )

        self.assertEqual(receipt.items.count(), 2)
        item1 = receipt.items.get(product=self.p1)
        item2 = receipt.items.get(product=self.p2)

        self.assertEqual(item1.net_weight_kg, Decimal('30.000'))
        self.assertEqual(item2.net_weight_kg, Decimal('50.000'))

        # Check document-level totals
        self.assertEqual(receipt.total_gross_weight_kg, Decimal('86.000'))
        self.assertEqual(receipt.total_net_weight_kg, Decimal('80.000'))
        self.assertEqual(receipt.aggregate_gross_weight, Decimal('86.000'))
        self.assertEqual(receipt.aggregate_net_weight, Decimal('80.000'))
        self.assertEqual(receipt.aggregate_tare_weight, Decimal('6.000'))

        # Consistency test: gross - tare == net
        self.assertEqual(receipt.aggregate_gross_weight - receipt.aggregate_tare_weight, receipt.aggregate_net_weight)

        # Check stock movements (IN)
        mov1 = StockMovement.objects.get(product=self.p1, reference_document_number="REC-MULTI-001")
        mov2 = StockMovement.objects.get(product=self.p2, reference_document_number="REC-MULTI-001")
        self.assertEqual(mov1.net_weight_kg, Decimal('30.000'))
        self.assertEqual(mov1.direction, StockMovementDirection.IN)
        self.assertEqual(mov2.net_weight_kg, Decimal('50.000'))
        self.assertEqual(mov2.direction, StockMovementDirection.IN)

        # Verify stock balance strictly follows StockMovement ledger (each cut reflects its independent balance)
        self.assertEqual(get_product_stock_balance(self.p1), Decimal('30.000'))
        self.assertEqual(get_product_stock_balance(self.p2), Decimal('50.000'))

    def test_multi_item_receipt_atomic_rollback_on_invalid_tare(self):
        items_data = [
            {
                'product': self.p1,
                'gross_weight_kg': Decimal('30.000'),
                'tare_entries': [],
            },
            {
                'product': self.p2,
                'gross_weight_kg': Decimal('1.000'),
                'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],  # 2.000 kg tare > 1.000 gross
            },
        ]
        with self.assertRaises(InvalidTareWeightError):
            finalize_goods_receipt(
                document_number="REC-MULTI-FAIL",
                supplier_name="تأمین‌کننده تست",
                items_data=items_data,
            )

        # Confirm zero database persistence after atomic rollback
        self.assertFalse(GoodsReceipt.objects.filter(document_number="REC-MULTI-FAIL").exists())
        self.assertFalse(GoodsReceiptItem.objects.filter(goods_receipt__document_number="REC-MULTI-FAIL").exists())
        self.assertFalse(StockMovement.objects.filter(reference_document_number="REC-MULTI-FAIL").exists())

    def test_receipt_idempotency_prevents_duplicate_stock_and_handles_race(self):
        import uuid
        key = f"key-rec-{uuid.uuid4()}"
        items_data = [{
            'product': self.p1,
            'gross_weight_kg': Decimal('22.000'),
            'tare_entries': [{'tare_type': self.tare_basket, 'quantity': 1}],  # 20 kg net
        }]

        r1 = finalize_goods_receipt(
            document_number="REC-IDEMP-01",
            supplier_name="کشتارگاه سپید",
            items_data=items_data,
            idempotency_key=key,
        )
        r2 = finalize_goods_receipt(
            document_number="REC-IDEMP-01",
            supplier_name="کشتارگاه سپید",
            items_data=items_data,
            idempotency_key=key,
        )
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(GoodsReceipt.objects.filter(idempotency_key=key).count(), 1)
        self.assertEqual(StockMovement.objects.filter(reference_document_number="REC-IDEMP-01").count(), 1)
        self.assertEqual(get_product_stock_balance(self.p1), Decimal('20.000'))


class GoodsReceiptMigrationTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("ماکیان", "poultry")
        self.prod = Product.objects.create(name="بوقلمون کامل", code="T01", category=self.cat, unit="kg")
        self.tare = TareType.objects.create(name="سبد ۳ کیلویی", tare_weight_grams=3000)

    def test_migration_0005_backfills_items_without_creating_stock_movements(self):
        import importlib
        mig_0005 = importlib.import_module('sales.migrations.0005_backfill_goods_receipt_items')
        backfill_goods_receipt_items = mig_0005.backfill_goods_receipt_items
        from django.apps import apps

        initial_movements_count = StockMovement.objects.count()

        # Create a historical receipt without items
        rec = GoodsReceipt.objects.create(
            document_number="REC-HIST-01",
            supplier_name="مزرعه بوقلمون",
            product=self.prod,
            gross_weight_kg=Decimal('43.000'),
            total_tare_weight_kg=Decimal('3.000'),
            net_weight_kg=Decimal('40.000'),
            package_count=4,
            condition_notes="سالم",
            remarks="بار قدیمی",
        )
        tare_row = WeighingTareRow.objects.create(
            goods_receipt=rec,
            tare_type=self.tare,
            tare_name_snapshot=self.tare.name,
            unit_tare_grams=3000,
            quantity=1,
        )

        self.assertEqual(rec.items.count(), 0)
        self.assertIsNone(tare_row.goods_receipt_item)

        # Run backfill function
        backfill_goods_receipt_items(apps, None)

        rec.refresh_from_db()
        tare_row.refresh_from_db()

        self.assertEqual(rec.items.count(), 1)
        created_item = rec.items.first()
        self.assertEqual(created_item.product, self.prod)
        self.assertEqual(created_item.net_weight_kg, Decimal('40.000'))
        self.assertEqual(tare_row.goods_receipt_item, created_item)

        # Zero stock movements invariant
        self.assertEqual(StockMovement.objects.count(), initial_movements_count)

    def test_migration_0005_skips_incomplete_historical_records_safely(self):
        import importlib
        mig_0005 = importlib.import_module('sales.migrations.0005_backfill_goods_receipt_items')
        backfill_goods_receipt_items = mig_0005.backfill_goods_receipt_items
        from django.apps import apps

        # Incomplete draft record where product_id or weight is None
        incomplete_rec = GoodsReceipt.objects.create(
            document_number="REC-DRAFT-INCOMPLETE",
            supplier_name="مبدأ نامشخص",
            product=None,
            gross_weight_kg=None,
            net_weight_kg=None,
        )

        backfill_goods_receipt_items(apps, None)

        incomplete_rec.refresh_from_db()
        self.assertEqual(incomplete_rec.items.count(), 0)
        self.assertEqual(incomplete_rec.primary_product_name, "ثبت اولیه بدون کالا / ناقص")

    def test_legacy_and_incomplete_receipt_detail_view_renders_correctly(self):
        from django.test import Client
        from django.urls import reverse
        client = Client()

        incomplete_rec = GoodsReceipt.objects.create(
            document_number="REC-VIEW-INCOMPLETE",
            supplier_name="مبدأ ناقص",
            product=None,
            gross_weight_kg=None,
            net_weight_kg=None,
        )
        res = client.get(reverse('receipt_detail', args=[incomplete_rec.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "REC-VIEW-INCOMPLETE")
        self.assertContains(res, "ثبت اولیه بدون کالا / ناقص")


class MultiItemGoodsIssueWorkflowTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("گوشت گوساله", "beef")
        self.prod = Product.objects.create(name="سردست گوساله", code="B-SD", category=self.cat, unit="kg")
        # Seed 100 kg into inventory
        StockMovement.objects.create(
            product=self.prod,
            direction=StockMovementDirection.IN,
            movement_type=StockMovementType.RECEIPT,
            net_weight_kg=Decimal('100.000'),
            reference_document_number="SEED-100",
        )

    def test_goods_issue_aggregate_demand_across_multiple_lines(self):
        # Line 1 requests 60 kg, Line 2 requests 50 kg -> total 110 kg > available 100 kg
        items_data = [
            {
                'product': self.prod,
                'gross_weight_kg': Decimal('60.000'),
                'tare_entries': [],
            },
            {
                'product': self.prod,
                'gross_weight_kg': Decimal('50.000'),
                'tare_entries': [],
            },
        ]
        with self.assertRaises(InsufficientStockError):
            finalize_goods_issue(
                document_number="ISS-OVERDEMAND-01",
                goods_owner_name="فروشگاه",
                recipient_name="مشتری",
                items_data=items_data,
            )

        # Inventory balance remains 100 kg
        self.assertEqual(get_product_stock_balance(self.prod), Decimal('100.000'))

    def test_goods_issue_multi_line_success_and_ledger(self):
        # Line 1: 30 kg, Line 2: 40 kg -> total 70 kg <= 100 kg
        items_data = [
            {
                'product': self.prod,
                'gross_weight_kg': Decimal('30.000'),
                'tare_entries': [],
            },
            {
                'product': self.prod,
                'gross_weight_kg': Decimal('40.000'),
                'tare_entries': [],
            },
        ]
        issue = finalize_goods_issue(
            document_number="ISS-MULTI-OK",
            goods_owner_name="فروشگاه",
            recipient_name="رستوران پایتخت",
            items_data=items_data,
        )
        self.assertEqual(issue.items.count(), 2)
        self.assertEqual(issue.aggregate_net_weight, Decimal('70.000'))
        # 100 - 70 = 30 kg
        self.assertEqual(get_product_stock_balance(self.prod), Decimal('30.000'))


class InvoiceProductSearchAndCalculationTestCase(TestCase):
    def setUp(self):
        self.cat = get_test_category("گوشت گوسفندی", "lamb")
        self.p1 = Product.objects.create(
            name="ماهیچه گوسفندی",
            code="L-MAH",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=5000000,
        )
        self.p2 = Product.objects.create(
            name="دنبه گوسفندی",
            code="L-DON",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=2500000,
        )

    def test_invoice_independent_lines_calculation(self):
        items_data = [
            {
                'product': self.p1,
                'net_weight_kg': Decimal('3.500'),
                'quantity': 1,
                'unit_price_rial': 5000000,  # 3.5 * 5,000,000 = 17,500,000 Rials (1,750,000 Tomans)
            },
            {
                'product': self.p2,
                'net_weight_kg': Decimal('2.000'),
                'quantity': 1,
                'unit_price_rial': 2500000,  # 2.0 * 2,500,000 = 5,000,000 Rials (500,000 Tomans)
            },
        ]
        inv = finalize_invoice(
            document_number="INV-CALC-001",
            goods_owner_name="فروشگاه گوشت",
            buyer_name="هتل کوهستان",
            items_data=items_data,
        )
        self.assertEqual(inv.items.count(), 2)
        self.assertEqual(inv.total_amount_rial, 22500000)
        self.assertEqual(inv.total_amount_display, "2,250,000 تومان")

    def test_invoice_from_source_traceability(self):
        # Multi-item goods receipt
        tare = TareType.objects.create(name="سبد ۱ کیلویی", tare_weight_grams=1000)
        receipt = finalize_goods_receipt(
            document_number="REC-SRC-001",
            supplier_name="کشتارگاه دام",
            items_data=[
                {
                    'product': self.p1,
                    'gross_weight_kg': Decimal('21.000'),
                    'tare_entries': [{'tare_type': tare, 'quantity': 1}],  # 20 kg net
                },
            ],
        )
        inv_item_obj = receipt.items.first()

        invoice = generate_invoice_from_source_documents(
            source_type='PURCHASE',
            document_ids=[receipt.id],
            prices_override={f"receipt_item_{inv_item_obj.id}": 4000000},
        )
        self.assertEqual(invoice.items.count(), 1)
        inv_item = invoice.items.first()
        self.assertEqual(inv_item.source_receipt, receipt)
        self.assertEqual(inv_item.source_receipt_item, inv_item_obj)
        self.assertEqual(inv_item.unit_price_rial, 4000000)
        self.assertEqual(inv_item.total_price_rial, 80000000)  # 20 * 4,000,000


class Phase1ParentChildInventoryTestCase(TestCase):
    def setUp(self):
        self.cat_chicken, _ = Category.objects.get_or_create(
            slug='chicken',
            defaults={'name': 'مرغ', 'display_order': 1, 'is_active': True}
        )
        self.parent_chicken = Product.objects.create(
            name="مرغ کامل",
            code="CHK-PAR",
            category=self.cat_chicken,
            unit="kg",
            is_parent=True,
            is_active=True,
        )
        self.child_fillet = Product.objects.create(
            name="فیله مرغ",
            code="CHK-FIL",
            category=self.cat_chicken,
            unit="kg",
            parent=self.parent_chicken,
            is_parent=False,
            is_active=True,
        )
        self.child_wings = Product.objects.create(
            name="بال مرغ",
            code="CHK-WNG",
            category=self.cat_chicken,
            unit="kg",
            parent=self.parent_chicken,
            is_parent=False,
            is_active=True,
        )

    def test_receiving_2000kg_parent_product_increases_only_parent_stock(self):
        # Receiving 2,000 kg of chicken carcass
        receipt = finalize_goods_receipt(
            document_number="REC-2000-CHK",
            supplier_name="کشتارگاه سپید",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("2000.000"),
            tare_entries=[],
        )
        self.assertEqual(receipt.net_weight_kg, Decimal("2000.000"))

        # 1. Parent product stock increases by exactly 2,000 kg
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("2000.000"))
        self.assertEqual(get_parent_stock_balance(self.parent_chicken), Decimal("2000.000"))

        # 2. Child products independent balances are NOT increased
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("0.000"))
        self.assertEqual(get_product_stock_balance(self.child_wings), Decimal("0.000"))

        # 3. Available stock via parent-child consumption rule reflects parent stock
        self.assertEqual(get_product_available_stock(self.child_fillet), Decimal("2000.000"))
        self.assertEqual(get_product_available_stock(self.child_wings), Decimal("2000.000"))

        # 4. Exactly one StockMovement recorded
        movements = StockMovement.objects.filter(reference_document_number="REC-2000-CHK")
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().product, self.parent_chicken)
        self.assertEqual(movements.first().net_weight_kg, Decimal("2000.000"))

    def test_child_independent_stock_distinct_from_parent(self):
        # Direct delivery of 50 kg Fillet from external supplier
        finalize_goods_receipt(
            document_number="REC-50-FIL",
            supplier_name="تأمین‌کننده قطعات",
            product=self.child_fillet,
            gross_weight_kg=Decimal("50.000"),
            tare_entries=[],
        )
        # Child has 50 kg independent stock
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("50.000"))
        # Parent has 0 kg carcass stock (fillet is not whole carcass)
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("0.000"))
        # Other child has 0 kg
        self.assertEqual(get_product_stock_balance(self.child_wings), Decimal("0.000"))
        # Fillet available is 50 kg (50 own + 0 parent)
        self.assertEqual(get_product_available_stock(self.child_fillet), Decimal("50.000"))

    def test_outgoing_child_issue_consumes_child_stock_first_and_parent_remainder(self):
        # Setup: Child Fillet has 30 kg, Parent Chicken has 100 kg
        finalize_goods_receipt(
            document_number="REC-INIT-PAR",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        finalize_goods_receipt(
            document_number="REC-INIT-FIL",
            supplier_name="کشتارگاه",
            product=self.child_fillet,
            gross_weight_kg=Decimal("30.000"),
            tare_entries=[],
        )
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("30.000"))
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("100.000"))

        # Request 50 kg of Fillet:
        # Expected: 30 kg consumed from child independent stock + 20 kg consumed from parent stock
        issue = finalize_goods_issue(
            document_number="ISS-P1-001",
            product=self.child_fillet,
            gross_weight_kg=Decimal("50.000"),
            tare_entries=[],
            goods_owner_name="واکا پروتئین",
            recipient_name="رستوران پارس",
        )
        self.assertEqual(issue.aggregate_net_weight, Decimal("50.000"))

        # Resulting balances:
        # Child Fillet: 30 - 30 = 0 kg
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("0.000"))
        # Parent Chicken: 100 - 20 = 80 kg
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("80.000"))
        # Fillet available through remaining parent = 80 kg
        self.assertEqual(get_product_available_stock(self.child_fillet), Decimal("80.000"))

        # Verify movements:
        movements = StockMovement.objects.filter(reference_document_number="ISS-P1-001").order_by('id')
        self.assertEqual(movements.count(), 2)

        # Movement 1: 30 kg OUT on child fillet (independent stock)
        m_child = movements.filter(remarks__contains="مستقل").first()
        self.assertIsNotNone(m_child)
        self.assertEqual(m_child.product, self.child_fillet)
        self.assertEqual(m_child.net_weight_kg, Decimal("30.000"))
        self.assertEqual(m_child.direction, StockMovementDirection.OUT)

        # Movement 2: 20 kg OUT drawing from parent pool
        m_parent = movements.filter(remarks__contains="سهمیه والد").first()
        self.assertIsNotNone(m_parent)
        self.assertEqual(m_parent.product, self.child_fillet)
        self.assertEqual(m_parent.parent_product, self.parent_chicken)
        self.assertEqual(m_parent.net_weight_kg, Decimal("20.000"))
        self.assertEqual(m_parent.direction, StockMovementDirection.OUT)

    def test_outgoing_child_issue_exclusively_from_child_stock_when_sufficient(self):
        # Child Fillet has 60 kg, Parent has 100 kg
        finalize_goods_receipt(
            document_number="REC-CH-60",
            supplier_name="کشتارگاه",
            product=self.child_fillet,
            gross_weight_kg=Decimal("60.000"),
            tare_entries=[],
        )
        finalize_goods_receipt(
            document_number="REC-PA-100",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )

        # Issue 40 kg Fillet
        finalize_goods_issue(
            document_number="ISS-CH-ONLY",
            product=self.child_fillet,
            gross_weight_kg=Decimal("40.000"),
            tare_entries=[],
            goods_owner_name="واکا پروتئین",
            recipient_name="رستوران ترنج",
        )

        # Child Fillet remaining: 60 - 40 = 20 kg
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("20.000"))
        # Parent Chicken stock untouched: 100 kg
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("100.000"))

        # Exactly 1 movement created on child product
        movements = StockMovement.objects.filter(reference_document_number="ISS-CH-ONLY")
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().product, self.child_fillet)
        self.assertEqual(movements.first().net_weight_kg, Decimal("40.000"))

    def test_outgoing_child_issue_exclusively_from_parent_when_child_empty(self):
        # Child Fillet has 0 kg, Parent has 100 kg
        finalize_goods_receipt(
            document_number="REC-PA-ONLY",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )

        # Issue 40 kg Fillet
        finalize_goods_issue(
            document_number="ISS-PA-FALLBACK",
            product=self.child_fillet,
            gross_weight_kg=Decimal("40.000"),
            tare_entries=[],
            goods_owner_name="واکا پروتئین",
            recipient_name="رستوران ترنج",
        )

        # Child Fillet remaining: 0 kg
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("0.000"))
        # Parent Chicken stock reduced: 100 - 40 = 60 kg
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("60.000"))

        # Exactly 1 movement created representing child cut drawing from parent pool
        movements = StockMovement.objects.filter(reference_document_number="ISS-PA-FALLBACK")
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().product, self.child_fillet)
        self.assertEqual(movements.first().parent_product, self.parent_chicken)
        self.assertEqual(movements.first().net_weight_kg, Decimal("40.000"))

    def test_insufficient_stock_raises_error_and_rolls_back_completely(self):
        # Child Fillet has 10 kg, Parent Chicken has 20 kg (total available: 30 kg)
        finalize_goods_receipt(
            document_number="REC-S-FIL",
            supplier_name="کشتارگاه",
            product=self.child_fillet,
            gross_weight_kg=Decimal("10.000"),
            tare_entries=[],
        )
        finalize_goods_receipt(
            document_number="REC-S-PAR",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("20.000"),
            tare_entries=[],
        )

        # Attempt to issue 50 kg -> InsufficientStockError
        with self.assertRaises(InsufficientStockError):
            finalize_goods_issue(
                document_number="ISS-FAIL-STOCK",
                product=self.child_fillet,
                gross_weight_kg=Decimal("50.000"),
                tare_entries=[],
                goods_owner_name="واکا پروتئین",
                recipient_name="مشتری",
            )

        # Confirm zero records persisted for ISS-FAIL-STOCK
        self.assertFalse(GoodsIssue.objects.filter(document_number="ISS-FAIL-STOCK").exists())
        self.assertFalse(GoodsIssueItem.objects.filter(goods_issue__document_number="ISS-FAIL-STOCK").exists())
        self.assertFalse(StockMovement.objects.filter(reference_document_number="ISS-FAIL-STOCK").exists())

        # Balances untouched
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("10.000"))
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("20.000"))

    def test_multi_line_issue_child_and_parent_allocation(self):
        # Parent Chicken: 100 kg
        # Child Fillet: 30 kg
        # Child Wings: 10 kg
        finalize_goods_receipt(
            document_number="REC-M-PAR",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )
        finalize_goods_receipt(
            document_number="REC-M-FIL",
            supplier_name="کشتارگاه",
            product=self.child_fillet,
            gross_weight_kg=Decimal("30.000"),
            tare_entries=[],
        )
        finalize_goods_receipt(
            document_number="REC-M-WNG",
            supplier_name="کشتارگاه",
            product=self.child_wings,
            gross_weight_kg=Decimal("10.000"),
            tare_entries=[],
        )

        # Issue multi-line:
        # Line 1: Fillet 50 kg (consumes 30 fillet + 20 parent)
        # Line 2: Wings 40 kg (consumes 10 wings + 30 parent)
        # Total parent consumed: 50 kg (100 - 50 = 50 kg remaining)
        issue = finalize_goods_issue(
            document_number="ISS-MULTI-ALLOC",
            goods_owner_name="واکا پروتئین",
            recipient_name="هتل اسپیناس",
            items_data=[
                {
                    'product': self.child_fillet,
                    'gross_weight_kg': Decimal("50.000"),
                    'tare_entries': [],
                },
                {
                    'product': self.child_wings,
                    'gross_weight_kg': Decimal("40.000"),
                    'tare_entries': [],
                },
            ]
        )
        self.assertEqual(issue.aggregate_net_weight, Decimal("90.000"))

        # Balances:
        self.assertEqual(get_product_stock_balance(self.child_fillet), Decimal("0.000"))
        self.assertEqual(get_product_stock_balance(self.child_wings), Decimal("0.000"))
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("50.000"))

        # Total movements:
        # 1 for fillet (30kg), 1 for wings (10kg), 1 for parent (fillet portion 20kg), 1 for parent (wings portion 30kg)
        movements = StockMovement.objects.filter(reference_document_number="ISS-MULTI-ALLOC")
        self.assertEqual(movements.count(), 4)
        total_out = sum(m.net_weight_kg for m in movements)
        self.assertEqual(total_out, Decimal("90.000"))

    def test_goods_issue_retry_idempotency_prevents_duplicate_movements(self):
        finalize_goods_receipt(
            document_number="REC-IDEM-PAR",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
        )

        idemp_key = f"key-{uuid.uuid4()}"
        iss1 = finalize_goods_issue(
            document_number="ISS-IDEMP-01",
            product=self.child_fillet,
            gross_weight_kg=Decimal("40.000"),
            tare_entries=[],
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری",
            idempotency_key=idemp_key,
        )
        iss2 = finalize_goods_issue(
            document_number="ISS-IDEMP-01",
            product=self.child_fillet,
            gross_weight_kg=Decimal("40.000"),
            tare_entries=[],
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری",
            idempotency_key=idemp_key,
        )
        self.assertEqual(iss1.id, iss2.id)
        self.assertEqual(GoodsIssue.objects.filter(idempotency_key=idemp_key).count(), 1)
        self.assertEqual(StockMovement.objects.filter(reference_document_number="ISS-IDEMP-01").count(), 1)
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal("60.000"))


class Phase2PhysicalReconciliationTestCase(TestCase):
    """
    Authoritative test suite for Phase 2: Physical Inventory Reconciliation and Loss Calculation.
    Covers the 15 requirements specified in Section 7 of instructions.
    """

    def setUp(self):
        from products.models import Category, Product
        from django.contrib.auth.models import User
        from sales.models import (
            PhysicalInventoryReconciliation,
            ReconciliationStatus,
            StockMovement,
            StockMovementDirection,
            StockMovementType,
        )
        from sales.services import (
            calculate_physical_reconciliation,
            approve_physical_reconciliation,
            close_physical_reconciliation,
            UnauthorizedReconciliationError,
            ReconciliationLockedError,
            IncompleteReconciliationError,
            finalize_goods_receipt,
            finalize_goods_issue,
        )

        self.category = Category.objects.create(name="ماکیان انبارگردانی", slug="poultry-recon")
        self.parent_chicken = Product.objects.create(
            name="مرغ کامل انبارگردانی",
            category=self.category,
            is_parent=True,
            unit="kg",
        )
        self.child_fillet = Product.objects.create(
            name="فیله مرغ انبارگردانی",
            category=self.category,
            parent=self.parent_chicken,
            is_parent=False,
            unit="kg",
        )
        # Users
        self.admin_user = User.objects.create_user(
            username="recon_admin",
            password="password",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="recon_clerk",
            password="password",
            is_staff=False,
            is_superuser=False,
        )

    def test_01_authoritative_expected_closing_stock_formula(self):
        """1. expected_closing_stock = opening_stock + receipts - issues (300 + 1000 - 1100 = 200)"""
        from sales.services import calculate_physical_reconciliation, finalize_goods_receipt, finalize_goods_issue

        start_date = date(2026, 10, 1)
        end_date = date(2026, 10, 7)

        # Pre-period receipt establishing initial 300 kg inventory
        finalize_goods_receipt(
            document_number="REC-P2-PREV",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("300.000"),
            tare_entries=[],
            document_date=date(2026, 9, 30),
        )

        # Period Receipts: 1,000 kg
        finalize_goods_receipt(
            document_number="REC-P2-01",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("1000.000"),
            tare_entries=[],
            document_date=date(2026, 10, 2),
        )
        # Period Issues: 1,100 kg (from parent pool)
        finalize_goods_issue(
            document_number="ISS-P2-01",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("1100.000"),
            tare_entries=[],
            goods_owner_name="واکا",
            recipient_name="رستوران",
            document_date=date(2026, 10, 5),
        )

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=start_date,
            end_date=end_date,
            opening_stock=Decimal("300.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("200.000"),
        )
        self.assertEqual(recon.opening_stock_kg, Decimal("300.000"))
        self.assertEqual(recon.period_receipts_kg, Decimal("1000.000"))
        self.assertEqual(recon.period_issues_kg, Decimal("1100.000"))
        # 300 + 1000 - 1100 = 200
        self.assertEqual(recon.expected_closing_stock_kg, Decimal("200.000"))

    def test_02_actual_less_than_expected_produces_positive_shortage(self):
        """2. Actual physical closing stock < expected produces positive discrepancy (shortage: 200 - 180 = 20)."""
        from sales.services import calculate_physical_reconciliation

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("200.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("180.000"),
        )
        self.assertEqual(recon.expected_closing_stock_kg, Decimal("200.000"))
        self.assertEqual(recon.actual_physical_closing_stock_kg, Decimal("180.000"))
        # discrepancy = 200 - 180 = 20 kg (positive = shortage)
        self.assertEqual(recon.discrepancy_kg, Decimal("20.000"))
        self.assertEqual(recon.discrepancy_type, 'SHORTAGE')
        # discrepancy % = (20 / 200) * 100 = 10.00%
        self.assertEqual(recon.discrepancy_percentage, Decimal("10.00"))

    def test_03_actual_greater_than_expected_produces_negative_surplus(self):
        """3. Actual physical closing stock > expected produces negative discrepancy (surplus: 200 - 220 = -20)."""
        from sales.services import calculate_physical_reconciliation

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("200.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("220.000"),
        )
        self.assertEqual(recon.expected_closing_stock_kg, Decimal("200.000"))
        self.assertEqual(recon.actual_physical_closing_stock_kg, Decimal("220.000"))
        # discrepancy = 200 - 220 = -20 kg (negative = surplus)
        self.assertEqual(recon.discrepancy_kg, Decimal("-20.000"))
        self.assertEqual(recon.discrepancy_type, 'SURPLUS')
        self.assertEqual(recon.discrepancy_percentage, Decimal("-10.00"))

    def test_04_actual_equals_expected_produces_zero_discrepancy(self):
        """4. Actual physical closing stock == expected produces zero discrepancy."""
        from sales.services import calculate_physical_reconciliation

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("200.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("200.000"),
        )
        self.assertEqual(recon.discrepancy_kg, Decimal("0.000"))
        self.assertEqual(recon.discrepancy_type, 'RECONCILED')
        self.assertEqual(recon.discrepancy_percentage, Decimal("0.00"))

    def test_05_missing_physical_closing_stock_leaves_reconciliation_incomplete(self):
        """5. Missing physical closing stock leaves reconciliation incomplete and does not claim confirmed loss."""
        from sales.services import (
            calculate_physical_reconciliation,
            approve_physical_reconciliation,
            IncompleteReconciliationError,
        )
        from sales.models import ReconciliationStatus

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("300.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=None,
            save_record=True,
        )
        self.assertFalse(recon.is_complete)
        self.assertIsNone(recon.discrepancy_kg)
        self.assertIsNone(recon.discrepancy_percentage)
        self.assertEqual(recon.status, ReconciliationStatus.DRAFT)
        self.assertEqual(recon.discrepancy_type, 'INCOMPLETE')

        # Cannot approve an incomplete reconciliation
        with self.assertRaises(IncompleteReconciliationError):
            approve_physical_reconciliation(recon, user=self.admin_user)

    def test_06_subsequent_period_uses_previous_period_actual_physical_closing_as_opening(self):
        """6. Subsequent period uses the previous period's actual physical closing stock as opening stock."""
        from sales.services import (
            calculate_physical_reconciliation,
            approve_physical_reconciliation,
            finalize_goods_receipt,
            finalize_goods_issue,
        )
        from sales.models import ReconciliationStatus

        # Period 1: 2026-10-01 to 2026-10-07
        recon1 = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("300.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("185.000"),
            save_record=True,
        )
        recon1 = approve_physical_reconciliation(recon1, user=self.admin_user)
        self.assertEqual(recon1.status, ReconciliationStatus.APPROVED)

        # Period 2 movements
        finalize_goods_receipt(
            document_number="REC-P2-06",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("500.000"),
            tare_entries=[],
            document_date=date(2026, 10, 9),
        )
        finalize_goods_issue(
            document_number="ISS-P2-06",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("400.000"),
            tare_entries=[],
            goods_owner_name="واکا",
            recipient_name="مشتری",
            document_date=date(2026, 10, 12),
        )

        # Period 2: 2026-10-08 to 2026-10-14 without explicit opening_stock
        recon2 = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 8),
            end_date=date(2026, 10, 14),
            opening_stock=None,
            actual_physical_closing_stock=Decimal("280.000"),
        )
        # Should carry over 185.000 from Period 1's actual closing
        self.assertEqual(recon2.opening_stock_kg, Decimal("185.000"))
        self.assertTrue(recon2.is_opening_verified)
        self.assertEqual(recon2.period_receipts_kg, Decimal("500.000"))
        self.assertEqual(recon2.period_issues_kg, Decimal("400.000"))
        # Expected = 185 + 500 - 400 = 285.000
        self.assertEqual(recon2.expected_closing_stock_kg, Decimal("285.000"))
        # Discrepancy = 285 - 280 = 5.000 kg shortage
        self.assertEqual(recon2.discrepancy_kg, Decimal("5.000"))

    def test_07_missing_or_unverified_opening_stock_handled_safely(self):
        """7. Missing or unverified opening stock is handled safely without guessing numbers."""
        from sales.services import calculate_physical_reconciliation, approve_physical_reconciliation, IncompleteReconciliationError

        # Brand new product with no prior reconciliations and no opening provided
        recon = calculate_physical_reconciliation(
            product=self.child_fillet,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=None,
            actual_physical_closing_stock=Decimal("50.000"),
            save_record=True,
        )
        self.assertIsNone(recon.opening_stock_kg)
        self.assertFalse(recon.is_opening_verified)
        self.assertIsNone(recon.expected_closing_stock_kg)
        self.assertIsNone(recon.discrepancy_kg)
        self.assertFalse(recon.is_complete)

        # Must not be approvable without verified opening
        with self.assertRaises(IncompleteReconciliationError):
            approve_physical_reconciliation(recon, user=self.admin_user)

    def test_08_zero_or_negative_denominator_percentage_handled_safely(self):
        """8. Division by zero in percentage calculation is handled without raising an exception."""
        from sales.services import calculate_physical_reconciliation

        # Expected closing stock is 0 (opening 100, issues 100)
        recon_zero = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("0.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("10.000"),
        )
        self.assertEqual(recon_zero.expected_closing_stock_kg, Decimal("0.000"))
        self.assertEqual(recon_zero.discrepancy_kg, Decimal("-10.000"))
        # Zero denominator should safely result in None or N/A, never raising ZeroDivisionError
        self.assertIsNone(recon_zero.discrepancy_percentage)
        self.assertEqual(recon_zero.discrepancy_percentage_display, "N/A")

    def test_09_parent_and_child_pools_do_not_double_count(self):
        """9. Parent and child stock pools are reconciled without double-counting the same physical inventory."""
        from sales.services import (
            calculate_physical_reconciliation,
            finalize_goods_receipt,
            finalize_goods_issue,
        )

        start_date = date(2026, 10, 1)
        end_date = date(2026, 10, 7)

        # Parent receipt: 2,000 kg
        finalize_goods_receipt(
            document_number="REC-POOL-PAR",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal("2000.000"),
            tare_entries=[],
            document_date=date(2026, 10, 2),
        )
        # Child Fillet independent receipt: 100 kg
        finalize_goods_receipt(
            document_number="REC-POOL-FIL",
            supplier_name="کشتارگاه",
            product=self.child_fillet,
            gross_weight_kg=Decimal("100.000"),
            tare_entries=[],
            document_date=date(2026, 10, 3),
        )
        # Issue 40 kg of Fillet (comes from Fillet's independent stock first)
        finalize_goods_issue(
            document_number="ISS-POOL-FIL",
            product=self.child_fillet,
            gross_weight_kg=Decimal("40.000"),
            tare_entries=[],
            goods_owner_name="واکا",
            recipient_name="رستوران",
            document_date=date(2026, 10, 4),
        )

        # Reconcile Child Fillet:
        recon_child = calculate_physical_reconciliation(
            product=self.child_fillet,
            start_date=start_date,
            end_date=end_date,
            opening_stock=Decimal("0.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("60.000"),
        )
        # Child had 100 kg receipts, 40 kg issues = 60 kg expected
        self.assertEqual(recon_child.period_receipts_kg, Decimal("100.000"))
        self.assertEqual(recon_child.period_issues_kg, Decimal("40.000"))
        self.assertEqual(recon_child.expected_closing_stock_kg, Decimal("60.000"))
        self.assertEqual(recon_child.discrepancy_kg, Decimal("0.000"))

        # Reconcile Parent Chicken pool:
        recon_parent = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=start_date,
            end_date=end_date,
            opening_stock=Decimal("0.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("2000.000"),
        )
        # Parent had 2000 kg receipts, 0 issues from parent pool (child 40kg was independent)
        self.assertEqual(recon_parent.period_receipts_kg, Decimal("2000.000"))
        self.assertEqual(recon_parent.period_issues_kg, Decimal("0.000"))
        self.assertEqual(recon_parent.expected_closing_stock_kg, Decimal("2000.000"))
        self.assertEqual(recon_parent.discrepancy_kg, Decimal("0.000"))

    def test_10_calculation_alone_creates_no_stock_movements(self):
        """10. Calculation alone creates no stock movements."""
        from sales.services import calculate_physical_reconciliation
        from sales.models import StockMovement

        count_before = StockMovement.objects.count()

        calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("500.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("450.000"),
            save_record=True,
        )

        count_after = StockMovement.objects.count()
        self.assertEqual(count_before, count_after)

    def test_11_approved_adjustment_creates_traceable_adjustment_movement(self):
        """11. Approved adjustment creates traceable adjustment movement(s)."""
        from sales.services import calculate_physical_reconciliation, approve_physical_reconciliation
        from sales.models import StockMovement, StockMovementType, StockMovementDirection

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("500.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("480.000"),  # 20 kg shortage
            save_record=True,
        )
        self.assertEqual(recon.discrepancy_kg, Decimal("20.000"))

        count_before = StockMovement.objects.count()
        approved_recon = approve_physical_reconciliation(
            recon,
            user=self.admin_user,
            apply_stock_adjustment=True,
        )
        count_after = StockMovement.objects.count()
        self.assertEqual(count_after, count_before + 1)

        adj_movement = approved_recon.adjustment_movement
        self.assertIsNotNone(adj_movement)
        self.assertEqual(adj_movement.movement_type, StockMovementType.ADJUSTMENT)
        self.assertEqual(adj_movement.direction, StockMovementDirection.OUT)  # Shortage reduces stock
        self.assertEqual(adj_movement.net_weight_kg, Decimal("20.000"))
        self.assertEqual(adj_movement.reference_document_number, recon.document_number)
        self.assertEqual(adj_movement.operator, self.admin_user)
        self.assertIn("کسری", adj_movement.remarks)

    def test_12_repeated_approval_idempotent_no_duplicate_movements(self):
        """12. Repeated approval of the same reconciliation is idempotent and creates no duplicate movements."""
        from sales.services import calculate_physical_reconciliation, approve_physical_reconciliation
        from sales.models import StockMovement

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("500.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("480.000"),
            save_record=True,
        )
        approve_physical_reconciliation(recon, user=self.admin_user, apply_stock_adjustment=True)
        count_after_first = StockMovement.objects.count()

        # Call approve again
        approve_physical_reconciliation(recon, user=self.admin_user, apply_stock_adjustment=True)
        count_after_second = StockMovement.objects.count()

        self.assertEqual(count_after_first, count_after_second)

    def test_13_approved_or_closed_reconciliation_cannot_be_silently_modified(self):
        """13. Approved or closed reconciliation cannot be silently modified or recalculated."""
        from django.core.exceptions import ValidationError
        from sales.services import (
            calculate_physical_reconciliation,
            approve_physical_reconciliation,
            close_physical_reconciliation,
            ReconciliationLockedError,
        )

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("500.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("500.000"),
            save_record=True,
        )
        recon = approve_physical_reconciliation(recon, user=self.admin_user)

        # Attempt to recalculate should raise ReconciliationLockedError
        with self.assertRaises(ReconciliationLockedError):
            calculate_physical_reconciliation(
                product=self.parent_chicken,
                reconciliation_instance=recon,
            )

        # Attempt to modify numbers and save should raise ValidationError
        recon.actual_physical_closing_stock_kg = Decimal("400.000")
        with self.assertRaises(ValidationError):
            recon.save()

    def test_14_unauthorized_users_cannot_approve_or_close(self):
        """14. Unauthorized users cannot approve or close reconciliation."""
        from sales.services import (
            calculate_physical_reconciliation,
            approve_physical_reconciliation,
            close_physical_reconciliation,
            UnauthorizedReconciliationError,
        )

        recon = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            opening_stock=Decimal("500.000"),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal("500.000"),
            save_record=True,
        )

        # Regular user without staff/perm
        with self.assertRaises(UnauthorizedReconciliationError):
            approve_physical_reconciliation(recon, user=self.regular_user)

        with self.assertRaises(UnauthorizedReconciliationError):
            close_physical_reconciliation(recon, user=self.regular_user)

        # Anonymous user
        with self.assertRaises(UnauthorizedReconciliationError):
            approve_physical_reconciliation(recon, user=None)


class Phase3InvoiceWorkflowTestCase(TestCase):
    """
    Comprehensive tests for Phase 3:
    - Ordinary sales invoice creation and line calculations
    - Product price_per_unit_rial fallback (fixing unit_price_rial bug)
    - Invoice generation from Goods Receipt (Purchase)
    - Invoice generation from Goods Issue (Sale)
    - Invoice totals, product prices, source-document relationships
    - Duplicate prevention, idempotency, and atomic rollbacks
    - Print/detail view rendering and empty optional fields resilience
    - Operator model compliance
    """

    def setUp(self):
        self.cat_chicken, _ = Category.objects.get_or_create(
            slug='chicken',
            defaults={'name': 'مرغ', 'display_order': 1, 'is_active': True}
        )
        self.product_breast = Product.objects.create(
            name="سینه مرغ",
            code="CHK-BRS-P3",
            category=self.cat_chicken,
            unit="kg",
            price_per_unit_rial=2500000,
            is_active=True,
        )
        self.product_wings = Product.objects.create(
            name="بال مرغ",
            code="CHK-WNG-P3",
            category=self.cat_chicken,
            unit="kg",
            price_per_unit_rial=1800000,
            is_active=True,
        )
        self.product_no_price = Product.objects.create(
            name="پای مرغ بدون قیمت",
            code="CHK-FT-P3",
            category=self.cat_chicken,
            unit="kg",
            price_per_unit_rial=None,
            is_active=True,
        )
        self.operator = Operator.objects.create(
            name="متصدی آزمایشی فاز ۳",
            display_order=1,
            is_active=True,
        )
        finalize_goods_receipt(
            document_number="REC-P3-SEED",
            supplier_name="کشتارگاه سپید بال",
            items_data=[
                {
                    'product': self.product_breast,
                    'gross_weight_kg': Decimal('500.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('500.000'),
                },
                {
                    'product': self.product_wings,
                    'gross_weight_kg': Decimal('500.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('500.000'),
                },
                {
                    'product': self.product_no_price,
                    'gross_weight_kg': Decimal('500.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('500.000'),
                },
            ],
        )

    def test_ordinary_sales_invoice_creation_and_totals(self):
        """1. Finalize ordinary invoice and verify line math and grand total."""
        items = [
            {
                'product': self.product_breast,
                'net_weight_kg': Decimal('10.500'),
                'quantity': 1,
                'unit_price_rial': 2500000,
            },
            {
                'product': self.product_wings,
                'net_weight_kg': Decimal('5.000'),
                'quantity': 1,
                'unit_price_rial': 1800000,
            },
        ]
        invoice = finalize_invoice(
            document_number="INV-TEST-001",
            goods_owner_name="واکا پروتئین",
            buyer_name="رستوران ترنج",
            items_data=items,
            driver_name="علی رضایی",
            operator_name=self.operator.name,
            document_date=date(2026, 10, 27),
            remarks="تحویل فوری",
        )
        self.assertEqual(invoice.status, DocumentStatus.FINALIZED)
        self.assertEqual(invoice.invoice_type, InvoiceType.SALE)
        self.assertEqual(invoice.items.count(), 2)

        # Line 1: 10.500 * 2,500,000 = 26,250,000
        # Line 2: 5.000 * 1,800,000 = 9,000,000
        # Grand Total: 35,250,000 Rials
        line1 = invoice.items.get(product=self.product_breast)
        self.assertEqual(line1.total_price_rial, 26250000)
        line2 = invoice.items.get(product=self.product_wings)
        self.assertEqual(line2.total_price_rial, 9000000)
        self.assertEqual(invoice.total_amount_rial, 35250000)

    def test_ordinary_sales_invoice_fallback_to_product_price_per_unit(self):
        """2. When unit_price_rial is omitted, falls back to product.price_per_unit_rial without AttributeError."""
        items = [
            {
                'product': self.product_breast,
                'net_weight_kg': Decimal('2.000'),
            }
        ]
        invoice = finalize_invoice(
            document_number="INV-FALLBACK-01",
            goods_owner_name="واکا پروتئین",
            buyer_name="مشتری یکتا",
            items_data=items,
        )
        item = invoice.items.first()
        self.assertEqual(item.unit_price_rial, 2500000)
        self.assertEqual(item.total_price_rial, 5000000)
        self.assertEqual(invoice.total_amount_rial, 5000000)

    def test_ordinary_sales_invoice_missing_price_raises_error(self):
        """3. When neither item nor product has price, raises BusinessLogicError."""
        items = [
            {
                'product': self.product_no_price,
                'net_weight_kg': Decimal('10.000'),
            }
        ]
        with self.assertRaises(BusinessLogicError) as ctx:
            finalize_invoice(
                document_number="INV-NO-PRICE",
                goods_owner_name="واکا پروتئین",
                buyer_name="مشتری",
                items_data=items,
            )
        self.assertIn("قیمت معتبر به ریال برای کالای", str(ctx.exception))

    def test_generate_sales_invoice_from_goods_issue_using_product_price(self):
        """4. Generates sales invoice from goods issue; correctly falls back to Product.price_per_unit_rial."""
        issue = finalize_goods_issue(
            document_number="ISS-P3-001",
            goods_owner_name="واکا پروتئین",
            recipient_name="رستوران سنتی",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[
                {
                    'product': self.product_breast,
                    'gross_weight_kg': Decimal('25.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('25.000'),
                    # No unit_price_rial provided in item!
                }
            ],
        )
        self.assertIsNone(issue.items.first().unit_price_rial)

        # Before generating invoice, record stock movement count
        initial_movements = StockMovement.objects.count()

        invoice = generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[issue.id],
        )
        self.assertEqual(invoice.invoice_type, InvoiceType.SALE)
        self.assertEqual(invoice.items.count(), 1)
        inv_item = invoice.items.first()
        # Price should be taken from self.product_breast.price_per_unit_rial = 2,500,000
        self.assertEqual(inv_item.unit_price_rial, 2500000)
        self.assertEqual(inv_item.total_price_rial, 62500000)  # 25 * 2,500,000
        self.assertEqual(invoice.total_amount_rial, 62500000)

        # Source issue must be locked to invoice
        issue.refresh_from_db()
        self.assertEqual(issue.invoice, invoice)
        self.assertTrue(issue.is_invoiced)

        # Invoicing MUST NOT create stock movements
        self.assertEqual(StockMovement.objects.count(), initial_movements)

    def test_generate_sales_invoice_with_price_override(self):
        """5. Override price takes precedence over document and product catalogue prices."""
        issue = finalize_goods_issue(
            document_number="ISS-P3-002",
            goods_owner_name="واکا پروتئین",
            recipient_name="فروشگاه هما",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[
                {
                    'product': self.product_wings,
                    'gross_weight_kg': Decimal('10.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('10.000'),
                }
            ],
        )
        issue_item = issue.items.first()
        override_price = 2100000  # Overrides catalogue 1,800,000

        invoice = generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[issue.id],
            prices_override={f"issue_item_{issue_item.id}": override_price},
        )
        inv_item = invoice.items.first()
        self.assertEqual(inv_item.unit_price_rial, 2100000)
        self.assertEqual(inv_item.total_price_rial, 21000000)
        self.assertEqual(invoice.total_amount_rial, 21000000)

    def test_generate_purchase_invoice_from_goods_receipt(self):
        """6. Generates purchase invoice from GoodsReceipt and records line relationships."""
        receipt = finalize_goods_receipt(
            document_number="REC-P3-001",
            supplier_name="کشتارگاه سپید بال",
            supplier_document_ref="REF-9988",
            items_data=[
                {
                    'product': self.product_breast,
                    'gross_weight_kg': Decimal('50.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('50.000'),
                }
            ],
        )
        rec_item = receipt.items.first()

        invoice = generate_invoice_from_source_documents(
            source_type='PURCHASE',
            document_ids=[receipt.id],
            prices_override={f"receipt_item_{rec_item.id}": 2200000},
        )
        self.assertEqual(invoice.invoice_type, InvoiceType.PURCHASE)
        self.assertEqual(invoice.items.count(), 1)
        inv_item = invoice.items.first()
        self.assertEqual(inv_item.source_receipt, receipt)
        self.assertEqual(inv_item.source_receipt_item, rec_item)
        self.assertEqual(inv_item.unit_price_rial, 2200000)
        self.assertEqual(inv_item.total_price_rial, 110000000)  # 50 * 2,200,000
        self.assertEqual(invoice.total_amount_rial, 110000000)

        receipt.refresh_from_db()
        self.assertEqual(receipt.invoice, invoice)
        self.assertTrue(receipt.is_invoiced)

    def test_prevent_re_invoicing_already_invoiced_source_document(self):
        """7. Attempting to invoice a document already linked to an invoice raises BusinessLogicError."""
        issue = finalize_goods_issue(
            document_number="ISS-P3-003",
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری الف",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[
                {
                    'product': self.product_breast,
                    'gross_weight_kg': Decimal('10.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('10.000'),
                }
            ],
        )
        inv1 = generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[issue.id],
        )
        self.assertIsNotNone(inv1)

        # Attempting again must fail
        with self.assertRaises(BusinessLogicError) as ctx:
            generate_invoice_from_source_documents(
                source_type='SALE',
                document_ids=[issue.id],
            )
        self.assertIn("قبلاً به فاکتور شماره", str(ctx.exception))

    def test_atomic_rollback_on_failure_during_generation(self):
        """8. If pricing fails for any item in batch, entire transaction rolls back."""
        issue_valid = finalize_goods_issue(
            document_number="ISS-P3-VAL",
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری معتبر",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[
                {
                    'product': self.product_breast,
                    'gross_weight_kg': Decimal('10.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('10.000'),
                }
            ],
        )
        issue_no_price = finalize_goods_issue(
            document_number="ISS-P3-NOPRICE",
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری بدون قیمت",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[
                {
                    'product': self.product_no_price,
                    'gross_weight_kg': Decimal('5.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('5.000'),
                }
            ],
        )

        initial_inv_count = Invoice.objects.count()
        with self.assertRaises(BusinessLogicError):
            generate_invoice_from_source_documents(
                source_type='SALE',
                document_ids=[issue_valid.id, issue_no_price.id],
            )

        # Verify atomic rollback: no new invoice created, issue_valid is NOT locked to any invoice
        self.assertEqual(Invoice.objects.count(), initial_inv_count)
        issue_valid.refresh_from_db()
        self.assertIsNone(issue_valid.invoice)
        self.assertFalse(issue_valid.is_invoiced)

    def test_invoice_detail_view_rendering_and_print_layout(self):
        """9. Invoice detail view returns 200 and renders Persian numbers, amounts, and A5 print layout."""
        items = [
            {
                'product': self.product_breast,
                'net_weight_kg': Decimal('12.000'),
                'unit_price_rial': 2500000,
            }
        ]
        invoice = finalize_invoice(
            document_number="INV-DETAIL-01",
            goods_owner_name="واکا پروتئین",
            buyer_name="رستوران نگین",
            items_data=items,
            remarks="تست نمایش فاکتور",
        )
        res = self.client.get(reverse('invoice_detail', kwargs={'pk': invoice.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "واکا پروتئین")
        self.assertContains(res, "رستوران نگین")
        self.assertContains(res, "سینه مرغ")
        self.assertContains(res, "INV-DETAIL-01")
        self.assertContains(res, "چاپ فاکتور (A5)")

    def test_invoice_detail_with_empty_optional_fields_no_crash(self):
        """10. Invoices with empty driver, operator, or remarks render cleanly without 500 error."""
        items = [
            {
                'product': self.product_wings,
                'net_weight_kg': Decimal('3.500'),
                'unit_price_rial': 1800000,
            }
        ]
        invoice = finalize_invoice(
            document_number="INV-OPTIONAL-01",
            goods_owner_name="",
            buyer_name="",
            items_data=items,
            driver_name="",
            operator_name="",
            remarks="",
        )
        res = self.client.get(reverse('invoice_detail', kwargs={'pk': invoice.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "INV-OPTIONAL-01")
        self.assertContains(res, "مشتری متفرقه")

    def test_invoice_cancel_view_releases_source_documents(self):
        """11. Cancelling an invoice releases linked source documents without deletion."""
        issue = finalize_goods_issue(
            document_number="ISS-CANCEL-01",
            goods_owner_name="واکا پروتئین",
            recipient_name="مشتری ابطال",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[
                {
                    'product': self.product_breast,
                    'gross_weight_kg': Decimal('15.000'),
                    'total_tare_weight_kg': Decimal('0.000'),
                    'net_weight_kg': Decimal('15.000'),
                }
            ],
        )
        invoice = generate_invoice_from_source_documents(
            source_type='SALE',
            document_ids=[issue.id],
        )
        issue.refresh_from_db()
        self.assertTrue(issue.is_invoiced)

        # Cancel through POST view
        cancel_url = reverse('invoice_cancel', kwargs={'pk': invoice.pk})
        res = self.client.post(cancel_url, {'cancellation_reason': 'اشتباه در وزن اقلام'})
        self.assertEqual(res.status_code, 302)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, DocumentStatus.CANCELLED)
        self.assertIn("اشتباه در وزن اقلام", invoice.remarks)

        # Linked issue must be released
        issue.refresh_from_db()
        self.assertIsNone(issue.invoice)
        self.assertFalse(issue.is_invoiced)


class Phase4ProductCatalogueAndOrderingTestCase(TestCase):
    def setUp(self):
        from django.test import Client
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
        self.child_wings, _ = Product.objects.get_or_create(
            category=self.cat_chicken,
            name="بال مرغ",
            defaults={"unit": "kg", "parent": self.parent_chicken, "is_active": True, "code": "CHK-01"}
        )
        self.child_breast, _ = Product.objects.get_or_create(
            category=self.cat_chicken,
            name="سینه مرغ",
            defaults={"unit": "kg", "parent": self.parent_chicken, "is_active": True, "code": "CHK-02"}
        )
        self.chicken_burger, _ = Product.objects.get_or_create(
            category=self.cat_chicken,
            name="چیکن برگر",
            defaults={"unit": "kg", "parent": self.parent_chicken, "is_active": True, "code": "CHK-03"}
        )

        self.parent_beef, _ = Product.objects.get_or_create(
            category=self.cat_beef,
            name="گوساله",
            defaults={"unit": "kg", "is_parent": True, "is_active": True}
        )
        self.child_beef_burger, _ = Product.objects.get_or_create(
            category=self.cat_beef,
            name="برگر ۱۵۰ ممتاز",
            defaults={"unit": "kg", "parent": self.parent_beef, "is_active": True, "code": "BEF-01"}
        )

    def test_goods_receipt_selector_parent_before_child(self):
        """Parent products appear before their child products in receipt product selector."""
        res = self.client.get(reverse('receipt_create'))
        self.assertEqual(res.status_code, 200)
        products = list(res.context['products'])

        # In chicken category: parent مرغ must appear before child cuts
        chicken_prods = [p for p in products if p.category_id == self.cat_chicken.id]
        self.assertTrue(len(chicken_prods) >= 3)
        self.assertEqual(chicken_prods[0].id, self.parent_chicken.id)
        self.assertTrue(chicken_prods[0].is_parent)

        # In beef category: parent گوساله must appear before child cuts
        beef_prods = [p for p in products if p.category_id == self.cat_beef.id]
        self.assertTrue(len(beef_prods) >= 2)
        self.assertEqual(beef_prods[0].id, self.parent_beef.id)
        self.assertTrue(beef_prods[0].is_parent)

    def test_goods_issue_selector_parent_before_child_within_category(self):
        """Parent products appear before child products in issue product selector within category."""
        res = self.client.get(reverse('issue_create'))
        self.assertEqual(res.status_code, 200)
        products_display = res.context['products_display']

        # Chicken items
        chicken_items = [item for item in products_display if item['product'].category_id == self.cat_chicken.id]
        self.assertTrue(len(chicken_items) >= 3)
        self.assertEqual(chicken_items[0]['product'].id, self.parent_chicken.id)
        self.assertTrue(chicken_items[0]['product'].is_parent)

        # Beef items
        beef_items = [item for item in products_display if item['product'].category_id == self.cat_beef.id]
        self.assertTrue(len(beef_items) >= 2)
        self.assertEqual(beef_items[0]['product'].id, self.parent_beef.id)
        self.assertTrue(beef_items[0]['product'].is_parent)

    def test_invoice_create_selector_parent_before_child(self):
        """Parent products appear before child products in invoice product selector."""
        res = self.client.get(reverse('invoice_create'))
        self.assertEqual(res.status_code, 200)
        products = list(res.context['products'])

        chicken_prods = [p for p in products if p.category_id == self.cat_chicken.id]
        self.assertEqual(chicken_prods[0].id, self.parent_chicken.id)

        beef_prods = [p for p in products if p.category_id == self.cat_beef.id]
        self.assertEqual(beef_prods[0].id, self.parent_beef.id)

    def test_inventory_overview_parent_before_child_and_digit_normalized_search(self):
        """Inventory overview displays parent first and supports digit-normalized search."""
        res = self.client.get(reverse('inventory_overview'))
        self.assertEqual(res.status_code, 200)
        stock_items = res.context['stock_items']

        chicken_stock = [item for item in stock_items if item['product'].category_id == self.cat_chicken.id]
        self.assertEqual(chicken_stock[0]['product'].id, self.parent_chicken.id)

        # Search with Persian digits for CHK-01 (should find child_wings)
        res_search_persian = self.client.get(reverse('inventory_overview') + '?q=CHK-۰۱')
        self.assertEqual(res_search_persian.status_code, 200)
        self.assertContains(res_search_persian, "بال مرغ")

        # Search with Latin digits
        res_search_latin = self.client.get(reverse('inventory_overview') + '?q=CHK-01')
        self.assertEqual(res_search_latin.status_code, 200)
        self.assertContains(res_search_latin, "بال مرغ")

    def test_independent_stock_vs_available_stock_presentation(self):
        """Receipt of 2,000 kg on parent does not inflate independent child stock; available stock is distinct."""
        finalize_goods_receipt(
            document_number="REC-P4-PARENT-01",
            supplier_name="کشتارگاه سپید",
            product=self.parent_chicken,
            gross_weight_kg=Decimal('2000.000'),
            tare_entries=[],
        )

        # Parent balance is 2000 kg
        self.assertEqual(get_product_stock_balance(self.parent_chicken), Decimal('2000.000'))

        # Child independent balance is 0 kg (not 2000 kg!)
        self.assertEqual(get_product_stock_balance(self.child_wings), Decimal('0.000'))
        self.assertEqual(get_product_stock_balance(self.chicken_burger), Decimal('0.000'))

        # Child available stock is 2000 kg (from parent fallback pool)
        self.assertEqual(get_product_available_stock(self.child_wings), Decimal('2000.000'))
        self.assertEqual(get_product_available_stock(self.chicken_burger), Decimal('2000.000'))

        # Check inventory overview UI renders both clearly
        res = self.client.get(reverse('inventory_overview'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "موجودی لاشه اصلی انبار")
        self.assertContains(res, "مستقل:")
        self.assertContains(res, "تخصیص‌پذیر از والد: 2000.000 kg")

    def test_chicken_burger_catalogue_integrity(self):
        """Chicken Burger exists, belongs to chicken category, has parent chicken, and is active."""
        burger = Product.objects.filter(name="چیکن برگر").first()
        self.assertIsNotNone(burger)
        self.assertEqual(burger.category.slug, "chicken")
        self.assertEqual(burger.get_parent(), self.parent_chicken)
        self.assertTrue(burger.is_active)

        # Check visibility in catalogue list
        res = self.client.get(reverse('product_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "چیکن برگر")

        # Check visibility under chicken category filter
        res_cat = self.client.get(reverse('product_list') + '?category=chicken')
        self.assertEqual(res_cat.status_code, 200)
        self.assertContains(res_cat, "چیکن برگر")


class Phase4DataSafetyPatchTestCase(TestCase):
    def setUp(self):
        from django.test import Client
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

    def test_1_existing_inactive_chicken_burger_remains_inactive(self):
        """1. Existing inactive chicken-burger products remain inactive."""
        from sales.services import safe_apply_catalogue_integrity
        # Ensure no preexisting chicken burger in chicken category for clean reassignment test
        Product.objects.filter(category=self.cat_chicken, name__in=['چیکن برگر', 'برگر مرغ']).delete()
        # Inactive chicken burger in beef category
        p_inactive = Product.objects.create(
            name="برگر مرغ",
            category=self.cat_beef,
            unit="kg",
            is_active=False,
            is_parent=False,
        )
        p_id = p_inactive.id
        results = safe_apply_catalogue_integrity()
        p_inactive.refresh_from_db()
        self.assertEqual(p_inactive.id, p_id)
        self.assertFalse(p_inactive.is_active, "Inactive product was unintentionally reactivated!")
        self.assertEqual(p_inactive.category, self.cat_chicken)

    def test_2_existing_active_product_retains_active_status(self):
        """2. Existing active products retain their active status."""
        from sales.services import safe_apply_catalogue_integrity
        p_active = Product.objects.create(
            name="برگر مرغ",
            category=self.cat_chicken,
            unit="kg",
            is_active=True,
            is_parent=False,
        )
        results = safe_apply_catalogue_integrity()
        p_active.refresh_from_db()
        self.assertTrue(p_active.is_active)

    def test_3_half_space_spelling_does_not_cause_duplicate_creation(self):
        """3. Half-space spelling (چیکن‌برگر with \\u200c) does not cause duplicate creation."""
        from sales.services import safe_apply_catalogue_integrity
        # Existing product with Persian ZWNJ
        p_zwnj = Product.objects.create(
            name="چیکن\u200cبرگر",
            category=self.cat_chicken,
            unit="kg",
            is_active=True,
        )
        initial_count = Product.objects.filter(category=self.cat_chicken).count()
        results = safe_apply_catalogue_integrity()
        new_count = Product.objects.filter(category=self.cat_chicken).count()
        self.assertEqual(initial_count, new_count, "A duplicate chicken burger was created despite half-space variant!")
        self.assertEqual(results['created_count'], 0)

    def test_4_alternate_known_spellings_do_not_cause_duplicate_creation(self):
        """4. Alternate known spellings (چیکنبرگر, برگر مرغ, برگر چیکن) do not cause duplicate creation."""
        from sales.services import is_equivalent_chicken_burger_name, safe_apply_catalogue_integrity
        variants = ["چیکن برگر", "چیکنبرگر", "برگر مرغ", "برگر چیکن", "چیکن\u200cبرگر", "  برگر   مرغ  "]
        for v in variants:
            self.assertTrue(is_equivalent_chicken_burger_name(v), f"Variant '{v}' was not recognized as equivalent!")

    def test_5_ambiguous_matches_are_not_silently_reassigned(self):
        """5. Ambiguous matches (e.g. seasoning or composite) are not silently reassigned."""
        from sales.services import safe_apply_catalogue_integrity
        p_ambiguous = Product.objects.create(
            name="چاشنی چیکن بیف ممتاز",
            category=self.cat_beef,
            unit="kg",
            is_active=True,
        )
        results = safe_apply_catalogue_integrity()
        p_ambiguous.refresh_from_db()
        # Must stay in beef, NOT reassigned to chicken!
        self.assertEqual(p_ambiguous.category, self.cat_beef)
        self.assertTrue(any(item[0] == p_ambiguous.id for item in results['ambiguous_skipped']))

    def test_6_existing_product_ids_and_historical_relationships_unchanged(self):
        """6. Existing product IDs and historical document relationships remain unchanged."""
        from sales.services import safe_apply_catalogue_integrity
        receipt = finalize_goods_receipt(
            document_number="REC-HIST-01",
            supplier_name="تأمین‌کننده تاریخی",
            product=self.parent_chicken,
            gross_weight_kg=Decimal('100.000'),
            tare_entries=[],
        )
        original_parent_id = self.parent_chicken.id
        results = safe_apply_catalogue_integrity()
        self.parent_chicken.refresh_from_db()
        self.assertEqual(self.parent_chicken.id, original_parent_id)
        receipt.refresh_from_db()
        self.assertEqual(receipt.product_id, original_parent_id)

    def test_7_parent_selection_is_deterministic(self):
        """7. Parent selection is deterministic with explicit order_by('id')."""
        from sales.services import resolve_canonical_parent_product
        # Add a second parent product in same category to simulate historical duplicate
        second_parent = Product.objects.create(
            category=self.cat_chicken,
            name="لاشه مرغ درجه دو",
            unit="kg",
            is_parent=True,
            is_active=True,
        )
        canonical, all_parents, has_ambiguity = resolve_canonical_parent_product(self.cat_chicken)
        self.assertTrue(has_ambiguity)
        self.assertEqual(canonical.id, min(self.parent_chicken.id, second_parent.id))

    def test_8_existing_correct_chicken_burger_not_duplicated(self):
        """8. Existing correct Chicken Burger products are not duplicated."""
        from sales.services import safe_apply_catalogue_integrity
        Product.objects.create(
            category=self.cat_chicken,
            name="چیکن برگر",
            unit="kg",
            parent=self.parent_chicken,
            is_active=True,
        )
        initial_count = Product.objects.count()
        results = safe_apply_catalogue_integrity()
        final_count = Product.objects.count()
        self.assertEqual(initial_count, final_count)
        self.assertEqual(results['created_count'], 0)

    def test_9_parent_child_inventory_behavior_preserved(self):
        """9. Parent-child inventory behavior from Phase 1 is preserved."""
        cut = Product.objects.create(
            name="فیله رژیمی مرغ",
            category=self.cat_chicken,
            parent=self.parent_chicken,
            unit="kg",
        )
        finalize_goods_receipt(
            document_number="REC-P1-CHECK-01",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal('500.000'),
            tare_entries=[],
        )
        self.assertEqual(get_product_stock_balance(cut), Decimal('0.000'))
        self.assertEqual(get_product_available_stock(cut), Decimal('500.000'))

    def test_10_physical_reconciliation_from_phase2_unaffected(self):
        """10. Physical reconciliation from Phase 2 is unaffected."""
        from sales.services import calculate_physical_reconciliation
        from django.utils import timezone
        recon_data = calculate_physical_reconciliation(
            product=self.parent_chicken,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            opening_stock=Decimal('50.000'),
            is_opening_verified=True,
            actual_physical_closing_stock=Decimal('20.000'),
        )
        self.assertIsNotNone(recon_data.expected_closing_stock_kg)
        self.assertIsNotNone(recon_data.discrepancy_kg)

    def test_11_invoice_workflows_from_phase3_unaffected(self):
        """11. Invoice workflows from Phase 3 are unaffected."""
        finalize_goods_receipt(
            document_number="REC-P3-PRE-01",
            supplier_name="کشتارگاه",
            product=self.parent_chicken,
            gross_weight_kg=Decimal('20.000'),
            tare_entries=[],
        )
        issue = finalize_goods_issue(
            document_number="ISS-P3-CHECK-01",
            goods_owner_name="واکا پروتئین",
            recipient_name="رستوران تستی",
            issue_reason=GoodsIssueReason.SALE,
            items_data=[{
                'product': self.parent_chicken,
                'gross_weight_kg': Decimal('10.000'),
                'total_tare_weight_kg': Decimal('0.000'),
                'net_weight_kg': Decimal('10.000'),
                'unit_price_rial': 2000000,
            }],
        )
        inv = generate_invoice_from_source_documents('SALE', [issue.id])
        self.assertEqual(inv.total_amount_rial, 20000000)

    def test_12_product_ordering_and_filtering_from_phase4_remain_correct(self):
        """12. Product ordering and filtering from Phase 4 remain correct."""
        res = self.client.get(reverse('receipt_create'))
        self.assertEqual(res.status_code, 200)
        prods = list(res.context['products'])
        chicken_prods = [p for p in prods if p.category_id == self.cat_chicken.id]
        self.assertEqual(chicken_prods[0].id, self.parent_chicken.id)
        self.assertTrue(chicken_prods[0].is_parent)


class Phase8InvoiceHistoryTestCase(TestCase):
    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.cat = get_test_category("مرغ", "chicken")
        self.product = Product.objects.create(
            name="سینه شنسل",
            code="101",
            category=self.cat,
            unit="kg",
            price_per_unit_rial=2200000,
        )

    def test_invoice_list_renders_empty_safely(self):
        from django.urls import reverse
        Invoice.objects.all().delete()
        res = self.client.get(reverse('invoice_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "هنوز فاکتوری صادر نشده است")

    def test_invoice_list_displays_persisted_invoices(self):
        from django.urls import reverse
        from sales.services import finalize_invoice

        # Create invoice
        inv = finalize_invoice(
            document_number='INV-HIST-001',
            goods_owner_name='مالک تستی',
            buyer_name='خریدار تستی',
            items_data=[{
                'product': self.product,
                'quantity': 1,
                'net_weight_kg': Decimal('10.000'),
                'unit_price_rial': 50000
            }]
        )

        res = self.client.get(reverse('invoice_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "INV-HIST-001")
        self.assertContains(res, "خریدار تستی")
        # Ensure viewing history doesn't create stock movements
        self.assertEqual(StockMovement.objects.filter(reference_document_number='INV-HIST-001').count(), 0)

    def test_invalid_invoice_id_returns_404(self):
        from django.urls import reverse
        res = self.client.get(reverse('invoice_detail', args=[99999]))
        self.assertEqual(res.status_code, 404)

    def test_historical_prices_are_preserved(self):
        from django.urls import reverse
        from sales.services import finalize_invoice

        # Create invoice with a specific price
        inv = finalize_invoice(
            document_number='INV-HIST-002',
            goods_owner_name='مالک تستی',
            buyer_name='خریدار تستی',
            items_data=[{
                'product': self.product,
                'quantity': 1,
                'net_weight_kg': Decimal('5.000'),
                'unit_price_rial': 2500000
            }]
        )

        # Mutate current product price to simulate time passing
        self.product.price_per_unit_rial = 9990000
        self.product.save()

        # Verify invoice detail retains the old historical price (2,500,000 Rial)
        # Using Toman presentation (250,000 Toman)
        res = self.client.get(reverse('invoice_detail', args=[inv.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "250,000 تومان")
        self.assertNotContains(res, "999,000 تومان")

    def test_export_csv_handles_invalid_dates_safely(self):
        from django.urls import reverse
        res = self.client.get(reverse('export_sales_csv') + '?start_date=invalid&end_date=1403/99/99')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8-sig')

    def test_export_sales_csv_empty_dataset(self):
        from django.urls import reverse
        Invoice.objects.all().delete()
        res = self.client.get(reverse('export_sales_csv'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        # Should just be headers
        self.assertIn('شماره فاکتور', content)
        # Should be exactly 1 line (headers)
        lines = [line for line in content.split('\r\n') if line.strip()]
        self.assertEqual(len(lines), 1)
