from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from products.models import Product


class Operator(models.Model):
    """Predefined operator / clerk (متصدی) selectable in weighing and invoice workflows."""
    name = models.CharField(max_length=64, unique=True, verbose_name="نام متصدی")
    display_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "متصدی"
        verbose_name_plural = "متصدیان"
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name


class TareType(models.Model):
    """Preset container tare types (e.g., Basket 1.5kg, Pallet 12.2kg, etc.)"""
    name = models.CharField(max_length=64, verbose_name="نام ظرف / پارسنگ")
    tare_weight_grams = models.PositiveIntegerField(verbose_name="وزن پارسنگ به گرم")
    is_custom = models.BooleanField(default=False, verbose_name="پارسنگ دستی (چرخ‌دستی / گاری)")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "نوع ظرف پارسنگ"
        verbose_name_plural = "انواع ظرف‌های پارسنگ"
        ordering = ['tare_weight_grams', 'id']

    def __str__(self):
        if self.is_custom:
            return f"{self.name} (متغیر)"
        kg_val = Decimal(self.tare_weight_grams) / Decimal(1000)
        return f"{self.name} ({kg_val:g} کیلوگرم)"

    @property
    def tare_weight_kg(self):
        return Decimal(self.tare_weight_grams) / Decimal(1000)


class DocumentStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'پیش‌نویس'
    FINALIZED = 'FINALIZED', 'نهایی شده'
    CANCELLED = 'CANCELLED', 'ابطال شده'


class GoodsReceipt(models.Model):
    """Standard Goods Receipt Document (رسید ورود کالا به انبار)."""
    document_number = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="شماره سند رسید"
    )
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کلید یکتایی درخواست"
    )
    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='source_receipts',
        verbose_name="فاکتور متناظر"
    )
    date_time = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ و زمان ورود")
    document_date = models.DateField(default=timezone.localdate, verbose_name="تاریخ سند ورود")
    supplier_name = models.CharField(max_length=128, verbose_name="نام تأمین‌کننده / مبدأ")
    supplier_document_ref = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="شماره بارنامه / فاکتور مبدأ"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='receipts',
        null=True,
        blank=True,
        verbose_name="کالای دریافتی (پیش‌فرض/تک‌قلمی)"
    )
    gross_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="وزن ناخالص باسکول (کیلوگرم)"
    )
    total_tare_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع وزن پارسنگ (کیلوگرم)"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="وزن خالص کالا (کیلوگرم)"
    )
    total_gross_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="مجموع وزن ناخالص (کیلوگرم)"
    )
    total_net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="مجموع وزن خالص (کیلوگرم)"
    )
    package_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="تعداد بسته / لاشه"
    )
    condition_notes = models.TextField(blank=True, verbose_name="وضعیت سلامت کالا و مغایرت‌ها")
    remarks = models.TextField(blank=True, verbose_name="ملاحظات عمومی")
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='receipts_handled',
        verbose_name="کاربر ثبت‌کننده"
    )
    operator_name = models.CharField(max_length=64, blank=True, verbose_name="نام متصدی")
    unit_price_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت واحد ورودی به ریال"
    )
    total_amount_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="مجموع مبلغ ورودی به ریال"
    )
    status = models.CharField(
        max_length=16,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
        verbose_name="وضعیت سند"
    )

    class Meta:
        verbose_name = "رسید ورود کالا"
        verbose_name_plural = "رسیدهای ورود کالا"
        ordering = ['-date_time', '-id']

    def __str__(self):
        return f"رسید {self.document_number} - {self.primary_product_name} ({self.aggregate_net_weight} کیلوگرم)"

    @property
    def is_invoiced(self):
        return self.invoice_id is not None

    @property
    def aggregate_gross_weight(self):
        if self.total_gross_weight_kg is not None:
            return self.total_gross_weight_kg
        if self.items.exists():
            from django.db.models import Sum
            return self.items.aggregate(total=Sum('gross_weight_kg'))['total'] or Decimal('0.000')
        return self.gross_weight_kg or Decimal('0.000')

    @property
    def aggregate_tare_weight(self):
        """
        Authoritative tare calculation:
        For receipts with GoodsReceiptItem rows, calculate aggregate tare from the sum
        of item-level total_tare_weight_kg values.
        Use legacy parent fields only when no child item rows exist.
        """
        if self.items.exists():
            from django.db.models import Sum
            return self.items.aggregate(total=Sum('total_tare_weight_kg'))['total'] or Decimal('0.000')
        if self.total_tare_weight_kg is not None:
            return self.total_tare_weight_kg
        if self.gross_weight_kg is not None and self.net_weight_kg is not None:
            return self.gross_weight_kg - self.net_weight_kg
        return Decimal('0.000')

    @property
    def aggregate_net_weight(self):
        if self.total_net_weight_kg is not None:
            return self.total_net_weight_kg
        if self.items.exists():
            from django.db.models import Sum
            return self.items.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')
        return self.net_weight_kg or Decimal('0.000')

    @property
    def is_multi_item(self):
        return self.items.exists()

    @property
    def items_count(self):
        count = self.items.count()
        if count > 0:
            return count
        return 1 if self.product_id else 0

    @property
    def primary_product_name(self):
        first_item = self.items.select_related('product').first()
        if first_item and first_item.product:
            return first_item.product.name
        if self.product:
            return self.product.name
        return "ثبت اولیه بدون کالا / ناقص"

    def clean(self):
        super().clean()
        if self.gross_weight_kg is not None and self.total_tare_weight_kg is not None:
            if self.gross_weight_kg < self.total_tare_weight_kg:
                raise ValidationError("وزن ناخالص نمی‌تواند کمتر از مجموع وزن پارسنگ ظروف باشد.")


class GoodsReceiptItem(models.Model):
    """Individual product line within a multi-item Goods Receipt document."""
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="رسید ورود مربوطه"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='receipt_items',
        verbose_name="کالای دریافتی"
    )
    gross_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن ناخالص باسکول (کیلوگرم)"
    )
    total_tare_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع وزن پارسنگ (کیلوگرم)"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن خالص کالا (کیلوگرم)"
    )
    package_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="تعداد بسته / لاشه"
    )
    condition_notes = models.CharField(max_length=256, blank=True, verbose_name="وضعیت سلامت کالا")
    unit_price_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت واحد به ریال"
    )
    line_total_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="مبلغ کل ردیف به ریال"
    )
    remarks = models.CharField(max_length=256, blank=True, verbose_name="ملاحظات سطر")

    class Meta:
        verbose_name = "سطر رسید ورود کالا"
        verbose_name_plural = "سطرهای رسید ورود کالا"
        ordering = ['id']

    def __str__(self):
        return f"{self.goods_receipt.document_number} - {self.product.name} ({self.net_weight_kg} kg)"

    def clean(self):
        super().clean()
        if self.gross_weight_kg is not None and self.total_tare_weight_kg is not None:
            if self.gross_weight_kg < self.total_tare_weight_kg:
                raise ValidationError("وزن ناخالص نمی‌تواند کمتر از مجموع وزن پارسنگ ظروف باشد.")


class GoodsIssueReason(models.TextChoices):
    SALE = 'SALE', 'فروش به مشتری'
    TRANSFER = 'TRANSFER', 'انتقال بین انبارها'
    PROCESSING = 'PROCESSING', 'تبدیل و قطعه‌بندی'
    WASTE = 'WASTE', 'ضایعات و افت مصوب'
    OTHER = 'OTHER', 'سایر موارد'


class GoodsIssue(models.Model):
    """Standard Goods Issue / Dispatch Document (حواله خروج کالا از انبار)."""
    document_number = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="شماره سند خروج"
    )
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کلید یکتایی درخواست"
    )
    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='source_issues',
        verbose_name="فاکتور متناظر"
    )
    date_time = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ و زمان خروج")
    document_date = models.DateField(default=timezone.localdate, verbose_name="تاریخ سند خروج")
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='issues',
        null=True,
        blank=True,
        verbose_name="کالای خروجی (پیش‌فرض/تک‌قلمی)"
    )
    gross_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="وزن ناخالص باسکول (کیلوگرم)"
    )
    total_tare_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع وزن پارسنگ (کیلوگرم)"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="وزن خالص کالا (کیلوگرم)"
    )
    total_gross_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="مجموع وزن ناخالص (کیلوگرم)"
    )
    total_net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="مجموع وزن خالص (کیلوگرم)"
    )
    total_amount_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="مجموع مبلغ کل به ریال"
    )
    goods_owner_name = models.CharField(max_length=128, verbose_name="نام صاحب کالا")
    recipient_name = models.CharField(max_length=128, verbose_name="نام خریدار / تحویل‌گیرنده")
    driver_name = models.CharField(max_length=128, blank=True, verbose_name="نام راننده / حمل‌کننده")
    destination_address = models.CharField(max_length=256, blank=True, verbose_name="مقصد / نشانی")
    issue_reason = models.CharField(
        max_length=16,
        choices=GoodsIssueReason.choices,
        default=GoodsIssueReason.SALE,
        verbose_name="علت خروج"
    )
    unit_price_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت واحد به ریال (در صورت معامله مالی)"
    )
    line_total_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="مبلغ کل خروج به ریال"
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issues_handled',
        verbose_name="کاربر ثبت‌کننده"
    )
    operator_name = models.CharField(max_length=64, blank=True, verbose_name="نام متصدی")
    remarks = models.TextField(blank=True, verbose_name="ملاحظات")
    status = models.CharField(
        max_length=16,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
        verbose_name="وضعیت سند"
    )

    class Meta:
        verbose_name = "حواله خروج کالا"
        verbose_name_plural = "حواله‌های خروج کالا"
        ordering = ['-date_time', '-id']

    def __str__(self):
        if self.product:
            return f"حواله {self.document_number} - {self.product.name} ({self.aggregate_net_weight} کیلوگرم)"
        return f"حواله {self.document_number} ({self.aggregate_net_weight} کیلوگرم)"

    @property
    def is_invoiced(self):
        return self.invoice_id is not None

    @property
    def aggregate_gross_weight(self):
        if self.total_gross_weight_kg is not None:
            return self.total_gross_weight_kg
        return self.gross_weight_kg or Decimal('0.000')

    @property
    def aggregate_net_weight(self):
        if self.total_net_weight_kg is not None:
            return self.total_net_weight_kg
        return self.net_weight_kg or Decimal('0.000')

    @property
    def aggregate_total_amount(self):
        if self.total_amount_rial is not None:
            return self.total_amount_rial
        return self.line_total_rial or 0

    @property
    def effective_total_amount_rial(self):
        return self.aggregate_total_amount

    @property
    def is_multi_item(self):
        return self.items.exists()

    @property
    def items_count(self):
        count = self.items.count()
        if count > 0:
            return count
        return 1 if self.product_id else 0

    @property
    def primary_product_name(self):
        first_item = self.items.select_related('product').first()
        if first_item and first_item.product:
            return first_item.product.name
        if self.product:
            return self.product.name
        return "بدون کالا"

    def clean(self):
        super().clean()
        if self.gross_weight_kg is not None and self.total_tare_weight_kg is not None:
            if self.gross_weight_kg < self.total_tare_weight_kg:
                raise ValidationError("وزن ناخالص نمی‌تواند کمتر از مجموع وزن پارسنگ ظروف باشد.")


class GoodsIssueItem(models.Model):
    """Individual product line within a multi-item Goods Issue document."""
    goods_issue = models.ForeignKey(
        GoodsIssue,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="حواله خروج مربوطه"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='issue_items',
        verbose_name="کالای خروجی"
    )
    gross_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن ناخالص باسکول (کیلوگرم)"
    )
    total_tare_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع وزن پارسنگ (کیلوگرم)"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن خالص کالا (کیلوگرم)"
    )
    unit_price_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت واحد به ریال"
    )
    line_total_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="مبلغ کل ردیف به ریال"
    )
    remarks = models.CharField(
        max_length=256,
        blank=True,
        verbose_name="ملاحظات سطر"
    )

    class Meta:
        verbose_name = "سطر حواله خروج کالا"
        verbose_name_plural = "سطرهای حواله خروج کالا"
        ordering = ['id']

    def __str__(self):
        return f"{self.goods_issue.document_number} - {self.product.name} ({self.net_weight_kg} kg)"

    def clean(self):
        super().clean()
        if self.gross_weight_kg is not None and self.total_tare_weight_kg is not None:
            if self.gross_weight_kg < self.total_tare_weight_kg:
                raise ValidationError("وزن ناخالص نمی‌تواند کمتر از مجموع وزن پارسنگ ظروف باشد.")


class WeighingTareRow(models.Model):
    """Line-by-line container tare snapshot attached to a weighing document."""
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tare_rows',
        verbose_name="رسید مربوطه"
    )
    goods_receipt_item = models.ForeignKey(
        GoodsReceiptItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tare_rows',
        verbose_name="ردیف رسید ورود"
    )
    goods_issue = models.ForeignKey(
        GoodsIssue,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tare_rows',
        verbose_name="حواله مربوطه"
    )
    goods_issue_item = models.ForeignKey(
        GoodsIssueItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tare_rows',
        verbose_name="ردیف حواله خروج"
    )
    tare_type = models.ForeignKey(
        TareType,
        on_delete=models.PROTECT,
        verbose_name="نوع ظرف"
    )
    tare_name_snapshot = models.CharField(max_length=64, verbose_name="نام ظرف در زمان توزین")
    unit_tare_grams = models.PositiveIntegerField(verbose_name="وزن هر ظرف به گرم")
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد ظرف")
    subtotal_tare_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="جمع وزن پارسنگ این سطر (کیلوگرم)"
    )

    class Meta:
        verbose_name = "سطر پارسنگ توزین"
        verbose_name_plural = "سطرهای پارسنگ توزین"

    def __str__(self):
        return f"{self.quantity} عدد {self.tare_name_snapshot} ({self.subtotal_tare_kg} کیلوگرم)"

    def save(self, *args, **kwargs):
        calc_subtotal = (Decimal(self.unit_tare_grams) * Decimal(self.quantity)) / Decimal(1000)
        self.subtotal_tare_kg = calc_subtotal
        super().save(*args, **kwargs)


class StockMovementDirection(models.TextChoices):
    IN = 'IN', 'ورود (افزایش موجودی)'
    OUT = 'OUT', 'خروج (کاهش موجودی)'


class StockMovementType(models.TextChoices):
    RECEIPT = 'RECEIPT', 'رسید ورود کالا'
    ISSUE = 'ISSUE', 'حواله خروج کالا'
    PROCESSING_INPUT = 'PROCESSING_INPUT', 'مصرف در فرآوری/تبدیل'
    PROCESSING_OUTPUT = 'PROCESSING_OUTPUT', 'استحصال از فرآوری/تبدیل'
    ADJUSTMENT = 'ADJUSTMENT', 'تعدیل انبارگردانی مصوب'


class StockMovement(models.Model):
    """Immutable stock ledger entry tracking all inventory changes."""
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name="کالا"
    )
    parent_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='parent_stock_movements',
        null=True,
        blank=True,
        verbose_name="کالای والد"
    )
    direction = models.CharField(
        max_length=4,
        choices=StockMovementDirection.choices,
        verbose_name="جهت گردش"
    )
    movement_type = models.CharField(
        max_length=24,
        choices=StockMovementType.choices,
        verbose_name="نوع رویداد انبار"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن خالص گردش (کیلوگرم)"
    )
    reference_document_number = models.CharField(
        max_length=64,
        verbose_name="شماره سند مرجع"
    )
    document_date = models.DateField(default=timezone.localdate, verbose_name="تاریخ رویداد")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ و ساعت ثبت گردش")
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements_authorized',
        verbose_name="کاربر مسئول"
    )
    operator_name = models.CharField(max_length=64, blank=True, verbose_name="نام متصدی")
    remarks = models.TextField(blank=True, verbose_name="توضیحات گردش")

    class Meta:
        verbose_name = "گردش انبار"
        verbose_name_plural = "دفتر گردش انبار (کاردکس)"
        ordering = ['-timestamp', '-id']

    def save(self, *args, **kwargs):
        if not self.parent_product and self.product:
            self.parent_product = self.product.get_parent() or self.product
        super().save(*args, **kwargs)

    def __str__(self):
        sign = "+" if self.direction == StockMovementDirection.IN else "-"
        return f"{self.product.name}: {sign}{self.net_weight_kg} kg ({self.reference_document_number})"


class ReconciliationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'پیش‌نویس'
    CALCULATED = 'CALCULATED', 'محاسبه‌شده'
    APPROVED = 'APPROVED', 'تایید و تصویب‌شده'
    CLOSED = 'CLOSED', 'بسته‌شده / قطعی'


class PhysicalInventoryReconciliation(models.Model):
    """
    Physical Inventory Count and Loss Reconciliation record.
    Authoritative balance formula:
        expected_closing_stock = opening_stock + period_receipts - period_issues
        discrepancy = expected_closing_stock - actual_physical_closing_stock
        (Positive discrepancy = shortage/کسری, Negative discrepancy = surplus/مازاد, Zero = reconciled/تراز)
    """
    document_number = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="شماره سند انبارگردانی"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='physical_reconciliations',
        verbose_name="کالای مورد انبارگردانی"
    )
    is_parent_pool = models.BooleanField(
        default=False,
        verbose_name="شامل کل سهمیه و برش‌های والد"
    )
    period_start_date = models.DateField(
        verbose_name="تاریخ شروع دوره"
    )
    period_end_date = models.DateField(
        verbose_name="تاریخ پایان دوره"
    )
    opening_stock_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="موجودی اول دوره (کیلوگرم)"
    )
    is_opening_verified = models.BooleanField(
        default=False,
        verbose_name="موجودی اول دوره تایید و معتبر است"
    )
    period_receipts_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع ورودی‌های دوره (کیلوگرم)"
    )
    period_issues_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع خروجی‌های دوره (کیلوگرم)"
    )
    expected_closing_stock_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="موجودی عینی مورد انتظار پایان دوره (کیلوگرم)"
    )
    actual_physical_closing_stock_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="موجودی عینی فیزیکی شمارش‌شده (کیلوگرم)"
    )
    discrepancy_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="مغایرت انبارگردانی (کسری / مازاد) (کیلوگرم)"
    )
    discrepancy_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="درصد مغایرت نسبت به موجودی مورد انتظار"
    )
    status = models.CharField(
        max_length=16,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.DRAFT,
        verbose_name="وضعیت انبارگردانی"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciliations_created',
        verbose_name="کاربر ایجادکننده"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciliations_approved',
        verbose_name="کاربر تصویب‌کننده"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان تصویب"
    )
    adjustment_movement = models.ForeignKey(
        StockMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciliation_adjustments',
        verbose_name="گردش تعدیل انبار صادرشده"
    )
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کلید یکتایی"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="یادداشت‌ها و مشاهدات شمارش فیزیکی"
    )

    class Meta:
        verbose_name = "انبارگردانی و مغایرت‌گیری فیزیکی"
        verbose_name_plural = "اسناد انبارگردانی و مغایرت‌گیری فیزیکی"
        ordering = ['-period_end_date', '-id']

    def __str__(self):
        return f"{self.document_number} - {self.product.name} ({self.get_status_display()})"

    @property
    def is_complete(self):
        return (
            self.actual_physical_closing_stock_kg is not None
            and self.opening_stock_kg is not None
            and self.is_opening_verified
        )

    @property
    def discrepancy_type(self):
        if not self.is_complete or self.discrepancy_kg is None:
            return 'INCOMPLETE'
        if self.discrepancy_kg > Decimal('0.000'):
            return 'SHORTAGE'  # کسری
        if self.discrepancy_kg < Decimal('0.000'):
            return 'SURPLUS'   # مازاد
        return 'RECONCILED'    # تراز

    @property
    def discrepancy_type_display(self):
        labels = {
            'INCOMPLETE': 'ناقص / در انتظار شمارش یا تایید اول دوره',
            'SHORTAGE': 'کسری انبار',
            'SURPLUS': 'مازاد انبار',
            'RECONCILED': 'تراز کامل (بدون مغایرت)',
        }
        return labels.get(self.discrepancy_type, '')

    @property
    def discrepancy_percentage_display(self):
        if self.discrepancy_percentage is not None:
            return f"{self.discrepancy_percentage}%"
        return "N/A"

    def clean(self):
        super().clean()
        if self.pk:
            orig = PhysicalInventoryReconciliation.objects.filter(pk=self.pk).first()
            if orig and orig.status in [ReconciliationStatus.APPROVED, ReconciliationStatus.CLOSED]:
                if self.status not in [ReconciliationStatus.APPROVED, ReconciliationStatus.CLOSED]:
                    raise ValidationError("امکان تغییر وضعیت سند انبارگردانی تاییدشده یا بسته‌شده به پیش‌نویس وجود ندارد.")
                if (
                    orig.opening_stock_kg != self.opening_stock_kg
                    or orig.actual_physical_closing_stock_kg != self.actual_physical_closing_stock_kg
                    or orig.expected_closing_stock_kg != self.expected_closing_stock_kg
                    or orig.discrepancy_kg != self.discrepancy_kg
                    or orig.period_start_date != self.period_start_date
                    or orig.period_end_date != self.period_end_date
                    or orig.product_id != self.product_id
                ):
                    raise ValidationError("سند انبارگردانی تاییدشده یا بسته‌شده غیرقابل تغییر و بازنویسی است.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ProcessingReconciliationStatus(models.TextChoices):
    RECONCILED = 'RECONCILED', 'تراز کامل (بدون مغایرت)'
    UNEXPLAINED_LOSS = 'UNEXPLAINED_LOSS', 'کسری / افت تبیین نشده'
    NEGATIVE_VARIANCE_FLAGGED = 'NEGATIVE_VARIANCE_FLAGGED', 'مازاد غیرعادی خروجی (نیازمند بررسی)'


class ProcessingRecord(models.Model):
    """Transformation / Processing Record (تبدیل لاشه یا مرغ کامل به برش‌های sellable)."""
    document_number = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="شماره سند فرآوری"
    )
    date_time = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ و زمان فرآوری")
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processing_handled',
        verbose_name="کاربر مجری فرآوری"
    )
    total_input_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع وزن خالص ورودی (کیلوگرم)"
    )
    total_output_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مجموع وزن خالص خروجی‌های حساب‌شده (کیلوگرم)"
    )
    unexplained_variance_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مغایرت تبیین‌نشده / افت خالص (کیلوگرم)"
    )
    yield_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="درصد راندمان / بازدهی"
    )
    reconciliation_status = models.CharField(
        max_length=32,
        choices=ProcessingReconciliationStatus.choices,
        default=ProcessingReconciliationStatus.RECONCILED,
        verbose_name="وضعیت تراز"
    )
    remarks = models.TextField(blank=True, verbose_name="توضیحات فرآوری")
    status = models.CharField(
        max_length=16,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
        verbose_name="وضعیت سند"
    )

    class Meta:
        verbose_name = "سند تبدیل و فرآوری"
        verbose_name_plural = "اسناد تبدیل و فرآوری"
        ordering = ['-date_time', '-id']

    def __str__(self):
        return f"فرآوری {self.document_number} (ورودی: {self.total_input_weight_kg} kg | خروجی: {self.total_output_weight_kg} kg)"


class ProcessingInputLine(models.Model):
    """Raw material consumed in a processing record."""
    processing_record = models.ForeignKey(
        ProcessingRecord,
        on_delete=models.CASCADE,
        related_name='input_lines',
        verbose_name="سند فرآوری"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="ماده اولیه ورودی"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن خالص مصرفی (کیلوگرم)"
    )

    class Meta:
        verbose_name = "سطر ورودی فرآوری"
        verbose_name_plural = "سطرهای ورودی فرآوری"


class ProcessingOutputLine(models.Model):
    """Sellable cuts or documented waste/by-products produced from a processing record."""
    processing_record = models.ForeignKey(
        ProcessingRecord,
        on_delete=models.CASCADE,
        related_name='output_lines',
        verbose_name="سند فرآوری"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="محصول یا قطعه خروجی"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن خالص حاصله (کیلوگرم)"
    )
    is_byproduct_or_waste = models.BooleanField(
        default=False,
        verbose_name="ضایعات یا ضمیمه فرآوری (استخوان، پوست، چربی)"
    )

    class Meta:
        verbose_name = "سطر خروجی فرآوری"
        verbose_name_plural = "سطرهای خروجی فرآوری"


class InvoiceType(models.TextChoices):
    SALE = 'SALE', 'فاکتور فروش'
    PURCHASE = 'PURCHASE', 'فاکتور خرید'


class Invoice(models.Model):
    """Authoritative printable Invoice / Dispatch document."""
    document_number = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="شماره فاکتور / سریال"
    )
    invoice_type = models.CharField(
        max_length=16,
        choices=InvoiceType.choices,
        default=InvoiceType.SALE,
        verbose_name="نوع فاکتور"
    )
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کلید یکتایی درخواست"
    )
    date = models.DateField(default=timezone.localdate, verbose_name="تاریخ فاکتور")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="زمان ثبت")
    goods_owner_name = models.CharField(max_length=128, verbose_name="نام صاحب کالا")
    buyer_name = models.CharField(max_length=128, verbose_name="نام خریدار / مشتری / طرف حساب")
    driver_name = models.CharField(max_length=128, blank=True, verbose_name="نام راننده")
    total_amount_rial = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مبلغ کل فاکتور به ریال"
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_issued',
        verbose_name="صادرکننده فاکتور"
    )
    operator_name = models.CharField(max_length=64, blank=True, verbose_name="نام متصدی")
    remarks = models.TextField(blank=True, verbose_name="توضیحات فاکتور")
    status = models.CharField(
        max_length=16,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
        verbose_name="وضعیت فاکتور"
    )

    class Meta:
        verbose_name = "فاکتور"
        verbose_name_plural = "فاکتورها"
        ordering = ['-date', '-id']

    def __str__(self):
        type_label = self.get_invoice_type_display()
        return f"{type_label} {self.document_number} - {self.buyer_name} ({self.total_amount_display})"

    @property
    def total_amount_display(self):
        display_unit = getattr(settings, 'CURRENCY_DISPLAY_UNIT', 'TOMAN')
        if display_unit == 'TOMAN':
            toman_val = self.total_amount_rial // 10
            return f"{toman_val:,} تومان"
        return f"{self.total_amount_rial:,} ریال"


class InvoiceItem(models.Model):
    """Line item on an Invoice with historical snapshots of cut name, price, and weight."""
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="فاکتور مربوطه"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="کالای خریداری‌شده"
    )
    source_issue_item = models.ForeignKey(
        GoodsIssueItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoice_items',
        verbose_name="سطر حواله خروج مرجع"
    )
    source_receipt = models.ForeignKey(
        GoodsReceipt,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoice_items',
        verbose_name="رسید ورود مرجع"
    )
    source_receipt_item = models.ForeignKey(
        GoodsReceiptItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoice_items',
        verbose_name="سطر رسید ورود مرجع"
    )
    product_name_snapshot = models.CharField(
        max_length=128,
        verbose_name="نام کالا در زمان صدور"
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="تعداد بسته / لاشه"
    )
    net_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="وزن خالص (کیلوگرم)"
    )
    unit_price_rial = models.PositiveBigIntegerField(
        verbose_name="قیمت واحد به ریال در زمان صدور"
    )
    total_price_rial = models.PositiveBigIntegerField(
        verbose_name="مبلغ سطر به ریال"
    )

    class Meta:
        verbose_name = "سطر فاکتور"
        verbose_name_plural = "سطرهای فاکتور"

    def __str__(self):
        return f"{self.product_name_snapshot}: {self.net_weight_kg} kg @ {self.unit_price_rial:,} Rials"

    @property
    def unit_price_display(self):
        display_unit = getattr(settings, 'CURRENCY_DISPLAY_UNIT', 'TOMAN')
        if display_unit == 'TOMAN':
            return f"{self.unit_price_rial // 10:,} تومان"
        return f"{self.unit_price_rial:,} ریال"

    @property
    def total_price_display(self):
        display_unit = getattr(settings, 'CURRENCY_DISPLAY_UNIT', 'TOMAN')
        if display_unit == 'TOMAN':
            return f"{self.total_price_rial // 10:,} تومان"
        return f"{self.total_price_rial:,} ریال"

