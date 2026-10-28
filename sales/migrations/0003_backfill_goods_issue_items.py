from django.db import migrations
from decimal import Decimal


def backfill_goods_issue_items(apps, schema_editor):
    GoodsIssue = apps.get_model('sales', 'GoodsIssue')
    GoodsIssueItem = apps.get_model('sales', 'GoodsIssueItem')
    WeighingTareRow = apps.get_model('sales', 'WeighingTareRow')

    for issue in GoodsIssue.objects.all():
        # Only populate header totals if not already set
        changed = False
        if issue.total_gross_weight_kg is None and issue.gross_weight_kg is not None:
            issue.total_gross_weight_kg = issue.gross_weight_kg
            changed = True
        if issue.total_net_weight_kg is None and issue.net_weight_kg is not None:
            issue.total_net_weight_kg = issue.net_weight_kg
            changed = True
        if issue.total_amount_rial is None and issue.line_total_rial is not None:
            issue.total_amount_rial = issue.line_total_rial
            changed = True
        if changed:
            issue.save(update_fields=['total_gross_weight_kg', 'total_net_weight_kg', 'total_amount_rial'])

        # Only create a GoodsIssueItem if no items currently exist and a product is present
        if not issue.items.exists() and issue.product_id is not None:
            gross = issue.gross_weight_kg if issue.gross_weight_kg is not None else (issue.net_weight_kg or Decimal('0.000'))
            tare = issue.total_tare_weight_kg if issue.total_tare_weight_kg is not None else Decimal('0.000')
            net = issue.net_weight_kg if issue.net_weight_kg is not None else Decimal('0.000')

            item = GoodsIssueItem.objects.create(
                goods_issue=issue,
                product=issue.product,
                gross_weight_kg=gross,
                total_tare_weight_kg=tare,
                net_weight_kg=net,
                unit_price_rial=issue.unit_price_rial,
                line_total_rial=issue.line_total_rial,
                remarks=issue.remarks or '',
            )

            # Link existing tare rows for this issue to the item
            WeighingTareRow.objects.filter(
                goods_issue=issue,
                goods_issue_item__isnull=True
            ).update(goods_issue_item=item)


def reverse_backfill(apps, schema_editor):
    # Reversing data migration: do not delete items destructively
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_goods_issue_multi_item_and_invoice_sources'),
    ]

    operations = [
        migrations.RunPython(backfill_goods_issue_items, reverse_backfill),
    ]
