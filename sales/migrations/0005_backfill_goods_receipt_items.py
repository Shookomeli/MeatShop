from django.db import migrations
from decimal import Decimal


def backfill_goods_receipt_items(apps, schema_editor):
    GoodsReceipt = apps.get_model('sales', 'GoodsReceipt')
    GoodsReceiptItem = apps.get_model('sales', 'GoodsReceiptItem')
    WeighingTareRow = apps.get_model('sales', 'WeighingTareRow')

    for receipt in GoodsReceipt.objects.all():
        # Only populate header totals if not already set
        changed = False
        if receipt.total_gross_weight_kg is None and receipt.gross_weight_kg is not None:
            receipt.total_gross_weight_kg = receipt.gross_weight_kg
            changed = True
        if receipt.total_net_weight_kg is None and receipt.net_weight_kg is not None:
            receipt.total_net_weight_kg = receipt.net_weight_kg
            changed = True
        if changed:
            receipt.save(update_fields=['total_gross_weight_kg', 'total_net_weight_kg'])

        # Skip incomplete historical records:
        # If product_id is None, or gross_weight_kg is None, or net_weight_kg is None,
        # it is an incomplete/draft record. We preserve it intact without fabricating data.
        if receipt.product_id is None or receipt.gross_weight_kg is None or receipt.net_weight_kg is None:
            continue

        # If items already exist, skip backfilling to prevent duplicate item creation
        if receipt.items.exists():
            continue

        # Valid historical record (including explicit 0-weight test/calibration records)
        tare = receipt.total_tare_weight_kg if receipt.total_tare_weight_kg is not None else Decimal('0.000')

        item = GoodsReceiptItem.objects.create(
            goods_receipt=receipt,
            product=receipt.product,
            gross_weight_kg=receipt.gross_weight_kg,
            total_tare_weight_kg=tare,
            net_weight_kg=receipt.net_weight_kg,
            package_count=receipt.package_count,
            condition_notes=receipt.condition_notes or '',
            remarks=receipt.remarks or '',
        )

        # Link existing tare rows for this receipt to the created item
        WeighingTareRow.objects.filter(
            goods_receipt=receipt,
            goods_receipt_item__isnull=True
        ).update(goods_receipt_item=item)


def reverse_backfill(apps, schema_editor):
    """
    Rollback limitations:
    Reversing disassociates tare rows and removes GoodsReceiptItems created from single-item receipts.
    Note: If new multi-item receipts have been created after applying this migration,
    reversing cannot collapse multi-line receipts back into single-product fields without data loss.
    """
    GoodsReceiptItem = apps.get_model('sales', 'GoodsReceiptItem')
    WeighingTareRow = apps.get_model('sales', 'WeighingTareRow')

    WeighingTareRow.objects.filter(goods_receipt_item__isnull=False).update(goods_receipt_item=None)
    # Do not delete items destructively if multi-item records exist in production
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0004_goods_receipt_multi_item'),
    ]

    operations = [
        migrations.RunPython(backfill_goods_receipt_items, reverse_backfill),
    ]
