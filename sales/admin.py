from django.contrib import admin
from .models import (
    TareType,
    GoodsReceipt,
    GoodsIssue,
    GoodsIssueItem,
    WeighingTareRow,
    StockMovement,
    ProcessingRecord,
    ProcessingInputLine,
    ProcessingOutputLine,
    Invoice,
    InvoiceItem,
    PhysicalInventoryReconciliation,
    LOCKED_RECONCILIATION_STATUSES,
)


@admin.register(TareType)
class TareTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'tare_weight_grams', 'is_custom', 'is_active')
    list_filter = ('is_custom', 'is_active')
    search_fields = ('name',)


class WeighingTareRowInline(admin.TabularInline):
    model = WeighingTareRow
    extra = 1
    fields = ('tare_type', 'tare_name_snapshot', 'unit_tare_grams', 'quantity', 'subtotal_tare_kg')
    readonly_fields = ('subtotal_tare_kg',)


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = (
        'document_number',
        'date_time',
        'supplier_name',
        'product',
        'gross_weight_kg',
        'total_tare_weight_kg',
        'net_weight_kg',
        'status',
    )
    list_filter = ('status', 'product__category')
    search_fields = ('document_number', 'supplier_name', 'product__name')
    inlines = [WeighingTareRowInline]


class GoodsIssueItemInline(admin.TabularInline):
    model = GoodsIssueItem
    extra = 1
    fields = ('product', 'gross_weight_kg', 'total_tare_weight_kg', 'net_weight_kg', 'unit_price_rial', 'line_total_rial')


@admin.register(GoodsIssue)
class GoodsIssueAdmin(admin.ModelAdmin):
    list_display = (
        'document_number',
        'date_time',
        'recipient_name',
        'product',
        'aggregate_net_weight',
        'issue_reason',
        'status',
    )
    list_filter = ('status', 'issue_reason', 'product__category')
    search_fields = ('document_number', 'recipient_name', 'goods_owner_name', 'product__name')
    inlines = [GoodsIssueItemInline, WeighingTareRowInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'product',
        'direction',
        'movement_type',
        'net_weight_kg',
        'reference_document_number',
        'operator',
    )
    list_filter = ('direction', 'movement_type', 'product__category')
    search_fields = ('product__name', 'reference_document_number')
    readonly_fields = (
        'product',
        'direction',
        'movement_type',
        'net_weight_kg',
        'reference_document_number',
        'timestamp',
        'operator',
        'remarks',
    )

    def has_delete_permission(self, request, obj=None):
        # Immutable ledger: prevent silent deletion of stock movements
        return False


class ProcessingInputLineInline(admin.TabularInline):
    model = ProcessingInputLine
    extra = 1


class ProcessingOutputLineInline(admin.TabularInline):
    model = ProcessingOutputLine
    extra = 2


@admin.register(ProcessingRecord)
class ProcessingRecordAdmin(admin.ModelAdmin):
    list_display = (
        'document_number',
        'date_time',
        'total_input_weight_kg',
        'total_output_weight_kg',
        'unexplained_variance_kg',
        'yield_percentage',
        'reconciliation_status',
        'status',
    )
    list_filter = ('status', 'reconciliation_status')
    search_fields = ('document_number',)
    inlines = [ProcessingInputLineInline, ProcessingOutputLineInline]


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = (
        'product',
        'product_name_snapshot',
        'quantity',
        'net_weight_kg',
        'unit_price_rial',
        'total_price_rial',
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'document_number',
        'date',
        'buyer_name',
        'goods_owner_name',
        'total_amount_display',
        'status',
    )
    list_filter = ('status',)
    search_fields = ('document_number', 'buyer_name', 'goods_owner_name')
    inlines = [InvoiceItemInline]


@admin.register(PhysicalInventoryReconciliation)
class PhysicalInventoryReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        'document_number',
        'product',
        'period_start_date',
        'period_end_date',
        'opening_stock_kg',
        'period_receipts_kg',
        'period_issues_kg',
        'expected_closing_stock_kg',
        'actual_physical_closing_stock_kg',
        'discrepancy_kg',
        'status',
    )
    list_filter = ('status', 'is_parent_pool', 'product__category')
    search_fields = ('document_number', 'product__name', 'notes')
    readonly_fields = ('created_at', 'approved_at')

    @staticmethod
    def _is_locked(obj):
        if obj is None or not obj.pk:
            return False
        stored_status = PhysicalInventoryReconciliation.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        return stored_status in LOCKED_RECONCILIATION_STATUSES

    def get_readonly_fields(self, request, obj=None):
        # Approved / closed records are immutable; the model and queryset also enforce this
        if self._is_locked(obj):
            return [f.name for f in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._is_locked(obj):
            return False
        return super().has_delete_permission(request, obj)
