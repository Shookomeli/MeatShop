from django.db import migrations


def setup_parent_categories_and_operators(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')
    Operator = apps.get_model('sales', 'Operator')
    StockMovement = apps.get_model('sales', 'StockMovement')
    GoodsReceipt = apps.get_model('sales', 'GoodsReceipt')
    GoodsIssue = apps.get_model('sales', 'GoodsIssue')

    # 1. Update / create the four parent categories
    # Chicken (مرغ)
    cat_chicken, _ = Category.objects.get_or_create(
        slug='chicken',
        defaults={'name': 'مرغ', 'display_order': 1, 'is_active': True}
    )
    if cat_chicken.name != 'مرغ':
        cat_chicken.name = 'مرغ'
        cat_chicken.display_order = 1
        cat_chicken.save(update_fields=['name', 'display_order'])

    # Lamb (گوسفندی)
    # Check if existing 'lamb' or 'گوشت گوسفندی' exists
    cat_lamb = Category.objects.filter(slug='lamb').first()
    if not cat_lamb:
        cat_lamb = Category.objects.filter(name__icontains='گوسفندی').first()
    if cat_lamb:
        cat_lamb.name = 'گوسفندی'
        cat_lamb.slug = 'lamb'
        cat_lamb.display_order = 2
        cat_lamb.is_active = True
        cat_lamb.save()
    else:
        cat_lamb = Category.objects.create(name='گوسفندی', slug='lamb', display_order=2, is_active=True)

    # Beef (گوساله)
    cat_beef = Category.objects.filter(slug='beef').first()
    if not cat_beef:
        cat_beef = Category.objects.filter(name__icontains='گاوی').first() or Category.objects.filter(name__icontains='گوساله').first()
    if cat_beef:
        cat_beef.name = 'گوساله'
        cat_beef.slug = 'beef'
        cat_beef.display_order = 3
        cat_beef.is_active = True
        cat_beef.save()
    else:
        cat_beef = Category.objects.create(name='گوساله', slug='beef', display_order=3, is_active=True)

    # Turkey (بوقلمون)
    cat_turkey, _ = Category.objects.get_or_create(
        slug='turkey',
        defaults={'name': 'بوقلمون', 'display_order': 4, 'is_active': True}
    )
    if cat_turkey.name != 'بوقلمون':
        cat_turkey.name = 'بوقلمون'
        cat_turkey.display_order = 4
        cat_turkey.save(update_fields=['name', 'display_order'])

    # Remove / deactivate standalone "گوشت" category
    cat_meat_general = Category.objects.filter(slug='meat-general').first() or Category.objects.filter(name='گوشت').first()
    if cat_meat_general:
        # Move any products in it to beef
        Product.objects.filter(category=cat_meat_general).update(category=cat_beef)
        cat_meat_general.delete()

    # Deactivate or migrate 'burger' category if present
    cat_burger = Category.objects.filter(slug='burger').first()
    if cat_burger:
        # Chicken burgers to chicken, others to beef
        Product.objects.filter(category=cat_burger, name__icontains='چیکن').update(category=cat_chicken)
        Product.objects.filter(category=cat_burger).update(category=cat_beef)
        cat_burger.delete()

    # 2. Ensure canonical parent products exist
    parent_chicken, _ = Product.objects.get_or_create(
        category=cat_chicken,
        name='مرغ',
        defaults={'unit': 'kg', 'is_parent': True, 'is_active': True}
    )
    if not parent_chicken.is_parent:
        parent_chicken.is_parent = True
        parent_chicken.save(update_fields=['is_parent'])

    parent_lamb, _ = Product.objects.get_or_create(
        category=cat_lamb,
        name='گوسفندی',
        defaults={'unit': 'kg', 'is_parent': True, 'is_active': True}
    )
    if not parent_lamb.is_parent:
        parent_lamb.is_parent = True
        parent_lamb.save(update_fields=['is_parent'])

    parent_beef, _ = Product.objects.get_or_create(
        category=cat_beef,
        name='گوساله',
        defaults={'unit': 'kg', 'is_parent': True, 'is_active': True}
    )
    if not parent_beef.is_parent:
        parent_beef.is_parent = True
        parent_beef.save(update_fields=['is_parent'])

    parent_turkey, _ = Product.objects.get_or_create(
        category=cat_turkey,
        name='بوقلمون',
        defaults={'unit': 'kg', 'is_parent': True, 'is_active': True}
    )
    if not parent_turkey.is_parent:
        parent_turkey.is_parent = True
        parent_turkey.save(update_fields=['is_parent'])

    # 3. Link child products to their parent product
    Product.objects.filter(category=cat_chicken).exclude(id=parent_chicken.id).update(parent=parent_chicken)
    Product.objects.filter(category=cat_lamb).exclude(id=parent_lamb.id).update(parent=parent_lamb)
    Product.objects.filter(category=cat_beef).exclude(id=parent_beef.id).update(parent=parent_beef)
    Product.objects.filter(category=cat_turkey).exclude(id=parent_turkey.id).update(parent=parent_turkey)

    # 4. Predefined Operators
    default_operators = [
        ('متصدی شماره ۱', 1),
        ('متصدی شماره ۲', 2),
        ('متصدی شماره ۳', 3),
    ]
    for op_name, order in default_operators:
        Operator.objects.get_or_create(
            name=op_name,
            defaults={'display_order': order, 'is_active': True}
        )

    # 5. Backfill StockMovements parent_product and document_date
    for sm in StockMovement.objects.all():
        updated_fields = []
        if sm.parent_product_id is None and sm.product:
            parent = sm.product.parent or (sm.product if sm.product.is_parent else None)
            if not parent:
                if sm.product.category_id == cat_chicken.id:
                    parent = parent_chicken
                elif sm.product.category_id == cat_lamb.id:
                    parent = parent_lamb
                elif sm.product.category_id == cat_beef.id:
                    parent = parent_beef
                elif sm.product.category_id == cat_turkey.id:
                    parent = parent_turkey
            if parent:
                sm.parent_product = parent
                updated_fields.append('parent_product')
        if sm.document_date is None and sm.timestamp:
            sm.document_date = sm.timestamp.date()
            updated_fields.append('document_date')
        if updated_fields:
            sm.save(update_fields=updated_fields)

    # 6. Backfill GoodsReceipt document_date
    for gr in GoodsReceipt.objects.filter(document_date__isnull=True):
        if gr.date_time:
            gr.document_date = gr.date_time.date()
            gr.save(update_fields=['document_date'])

    # 7. Backfill GoodsIssue document_date
    for gi in GoodsIssue.objects.filter(document_date__isnull=True):
        if gi.date_time:
            gi.document_date = gi.date_time.date()
            gi.save(update_fields=['document_date'])


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_product_is_parent_product_parent'),
        ('sales', '0006_operator_goodsissue_document_date_and_more'),
    ]

    operations = [
        migrations.RunPython(setup_parent_categories_and_operators, reverse_func),
    ]
