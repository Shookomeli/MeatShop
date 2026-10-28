from django.db import migrations
from django.db.models import Q


def restore_chicken_burger_and_category_integrity(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')

    cat_chicken = Category.objects.filter(slug='chicken').first()
    if not cat_chicken:
        cat_chicken = Category.objects.create(name='مرغ', slug='chicken', display_order=1, is_active=True)

    parent_chicken = Product.objects.filter(category=cat_chicken, is_parent=True).first()
    if not parent_chicken:
        parent_chicken = Product.objects.create(
            category=cat_chicken,
            name='مرغ',
            unit='kg',
            is_parent=True,
            is_active=True
        )

    # 1. Any existing chicken burger products (named with چیکن or برگر مرغ) mistakenly under beef or elsewhere
    misplaced = Product.objects.filter(
        Q(name__icontains='چیکن') | Q(name__icontains='برگر مرغ')
    ).exclude(category=cat_chicken)
    for p in misplaced:
        p.category = cat_chicken
        p.parent = parent_chicken
        p.is_active = True
        p.save(update_fields=['category', 'parent', 'is_active'])

    # 2. Ensure existing chicken burgers are active
    Product.objects.filter(
        category=cat_chicken,
        name__in=['چیکن برگر', 'برگر مرغ']
    ).update(is_active=True)

    # 3. If no chicken burger exists at all, restore the standard 'چیکن برگر' product
    chicken_burger_exists = Product.objects.filter(
        category=cat_chicken,
        name__in=['چیکن برگر', 'برگر مرغ']
    ).exists()

    if not chicken_burger_exists:
        Product.objects.create(
            category=cat_chicken,
            name='چیکن برگر',
            unit='kg',
            parent=parent_chicken,
            is_active=True,
            description='برگر تهیه شده از سینه و فیله مرغ'
        )

    # 4. Ensure all child products in all 4 canonical categories have parent set
    cat_lamb = Category.objects.filter(slug='lamb').first()
    cat_beef = Category.objects.filter(slug='beef').first()
    cat_turkey = Category.objects.filter(slug='turkey').first()

    parent_lamb = Product.objects.filter(category=cat_lamb, is_parent=True).first() if cat_lamb else None
    parent_beef = Product.objects.filter(category=cat_beef, is_parent=True).first() if cat_beef else None
    parent_turkey = Product.objects.filter(category=cat_turkey, is_parent=True).first() if cat_turkey else None

    if parent_chicken:
        Product.objects.filter(category=cat_chicken, parent__isnull=True).exclude(id=parent_chicken.id).update(parent=parent_chicken)
    if parent_lamb:
        Product.objects.filter(category=cat_lamb, parent__isnull=True).exclude(id=parent_lamb.id).update(parent=parent_lamb)
    if parent_beef:
        Product.objects.filter(category=cat_beef, parent__isnull=True).exclude(id=parent_beef.id).update(parent=parent_beef)
    if parent_turkey:
        Product.objects.filter(category=cat_turkey, parent__isnull=True).exclude(id=parent_turkey.id).update(parent=parent_turkey)


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0008_physicalinventoryreconciliation'),
    ]

    operations = [
        migrations.RunPython(restore_chicken_burger_and_category_integrity, reverse_migration),
    ]
