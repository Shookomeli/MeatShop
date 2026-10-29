from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_EVEN
from django.db import transaction, IntegrityError
from django.db.models import Sum, Q
from django.utils import timezone
from products.models import Product, Category
from .models import (
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
    DocumentStatus,
    GoodsIssueReason,
    ReconciliationStatus,
    PhysicalInventoryReconciliation,
)


class BusinessLogicError(Exception):
    """Base exception for domain and business logic errors."""
    pass


class UnauthorizedReconciliationError(BusinessLogicError):
    """Raised when an unauthorized user attempts to approve or close a reconciliation."""
    pass


class ReconciliationLockedError(BusinessLogicError):
    """Raised when attempting to modify or recalculate an approved or closed reconciliation."""
    pass


class IncompleteReconciliationError(BusinessLogicError):
    """Raised when critical physical count data is missing."""
    pass


class InvalidTareWeightError(BusinessLogicError):
    """Raised when tare weight exceeds or equals gross weight."""
    pass


class InsufficientStockError(BusinessLogicError):
    """Raised when an operation would drive inventory into negative numbers."""
    pass


WEIGHT_QUANTUM = Decimal('0.001')


def normalize_weight_kg(value) -> Decimal:
    """
    Normalizes an invoice weight to the 0.001 kg storage precision.
    Uses ROUND_HALF_EVEN, the same rule Django's DecimalField applies when reading the
    value back, so the persisted weight, the displayed weight and the line total all agree.
    """
    try:
        return Decimal(str(value)).quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError, TypeError):
        raise BusinessLogicError(f"وزن واردشده نامعتبر است: {value}")


def calculate_line_total_rial(amount: Decimal, unit_price_rial: int) -> int:
    """
    Authoritative invoice line total in whole Rial: amount (kg or count) × unit price.
    Fractional Rial are truncated (ROUND_DOWN), identical to the historical int() behaviour.
    """
    total = Decimal(str(amount)) * Decimal(int(unit_price_rial))
    return int(total.to_integral_value(rounding=ROUND_DOWN))


def calculate_tare_and_net(gross_weight_kg: Decimal, tare_entries: list) -> dict:
    """
    Calculates total tare and net weight for single or multiple container types.
    
    tare_entries: list of dicts:
        [{'tare_type': TareType_obj, 'quantity': int, 'custom_tare_grams': optional int}]
    """
    gross = Decimal(str(gross_weight_kg))
    if gross <= Decimal('0.000'):
        raise InvalidTareWeightError("وزن ناخالص باسکول باید عددی مثبت و بزرگتر از صفر باشد.")

    total_tare_grams = 0
    calculated_rows = []

    for entry in tare_entries:
        tare_type = entry['tare_type']
        qty = int(entry.get('quantity', 1))
        if qty <= 0:
            continue

        if tare_type.is_custom:
            unit_grams = int(entry.get('custom_tare_grams', 0))
        else:
            unit_grams = tare_type.tare_weight_grams

        subtotal_kg = (Decimal(unit_grams) * Decimal(qty)) / Decimal(1000)
        total_tare_grams += (unit_grams * qty)

        calculated_rows.append({
            'tare_type': tare_type,
            'tare_name_snapshot': tare_type.name,
            'unit_tare_grams': unit_grams,
            'quantity': qty,
            'subtotal_tare_kg': subtotal_kg,
        })

    total_tare_kg = Decimal(total_tare_grams) / Decimal(1000)
    net_weight_kg = gross - total_tare_kg

    if net_weight_kg <= Decimal('0.000'):
        raise InvalidTareWeightError(
            f"وزن ناخالص ({gross} کیلوگرم) نمی‌تواند کمتر یا مساوی مجموع وزن پارسنگ ظروف ({total_tare_kg} کیلوگرم) باشد."
        )

    return {
        'gross_weight_kg': gross,
        'total_tare_weight_kg': total_tare_kg,
        'net_weight_kg': net_weight_kg,
        'tare_rows': calculated_rows,
    }


PARENT_FALLBACK_PREFIX = "خروج از سهمیه والد"
INDEPENDENT_ISSUE_PREFIX = "خروج از موجودی مستقل"


def get_product_independent_stock(product: Product) -> Decimal:
    """
    Computes the independent stock balance physically held for a specific product
    from the immutable StockMovement ledger.
    - If the product is a parent carcass: balance is its own physical inventory minus
      all issues and conversions drawn from it.
    - If the product is a child cut: balance is Sum(IN for product) - Sum(OUT drawn from child's own stock).
    """
    if not product:
        return Decimal('0.000')

    if product.is_parent:
        return get_parent_stock_balance(product)

    in_sum = StockMovement.objects.filter(
        product=product,
        direction=StockMovementDirection.IN
    ).aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')

    # OUT from child's own independent stock excludes parent fallback deductions
    out_sum = StockMovement.objects.filter(
        product=product,
        direction=StockMovementDirection.OUT
    ).exclude(
        remarks__startswith=PARENT_FALLBACK_PREFIX
    ).aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')

    return in_sum - out_sum


def get_parent_stock_balance(parent_product: Product) -> Decimal:
    """
    Computes current stock balance for a parent product (carcass / raw whole meat)
    from the immutable StockMovement ledger.
    Parent balance = Sum(IN of parent) - Sum(OUT drawn from parent carcass).
    """
    if not parent_product:
        return Decimal('0.000')
    canonical_parent = parent_product.get_parent() or parent_product

    # Receipts and processing outputs of the parent carcass
    in_sum = StockMovement.objects.filter(
        product=canonical_parent,
        direction=StockMovementDirection.IN
    ).aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')

    # OUT movements: issues of the parent itself OR child cuts drawn from parent stock
    out_sum = StockMovement.objects.filter(
        direction=StockMovementDirection.OUT
    ).filter(
        Q(product=canonical_parent) | Q(parent_product=canonical_parent, remarks__startswith=PARENT_FALLBACK_PREFIX)
    ).aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')

    return in_sum - out_sum


def get_product_stock_balance(product: Product) -> Decimal:
    """
    Computes current independent stock balance for a product:
    Each product reflects its own physical stock derived from movements on that product.
    """
    if not product:
        return Decimal('0.000')
    return get_product_independent_stock(product)


def get_product_available_stock(product: Product) -> Decimal:
    """
    Computes total stock available for dispatch/issue for a product:
    - If the product is a parent (or has no parent): returns its own stock balance.
    - If the product is a child cut: returns child's own independent stock PLUS
      any available parent stock that can be consumed.
    """
    if not product:
        return Decimal('0.000')
    own_stock = get_product_independent_stock(product)
    if product.is_parent or not product.parent:
        return own_stock

    parent = product.get_parent()
    if not parent or parent == product:
        return own_stock

    parent_stock = max(Decimal('0.000'), get_parent_stock_balance(parent))
    return max(Decimal('0.000'), own_stock) + parent_stock


def get_all_stock_balances() -> list:
    """
    Returns stock balances for the primary parent meat categories:
    Chicken (مرغ), Lamb (گوسفندی), Beef (گوساله), Turkey (بوقلمون).
    """
    parent_products = Product.objects.filter(
        is_parent=True,
        is_active=True
    ).select_related('category').order_by('category__display_order', 'id')

    balances = []
    for parent in parent_products:
        bal = get_parent_stock_balance(parent)
        balances.append({
            'product': parent,
            'balance_kg': bal,
        })
    return balances


def finalize_goods_receipt(
    document_number: str,
    supplier_name: str,
    supplier_document_ref: str = "",
    operator=None,
    operator_name: str = "",
    document_date=None,
    remarks: str = "",
    items_data: list = None,
    # Legacy parameters for backward compatibility
    product: Product = None,
    gross_weight_kg: Decimal = None,
    tare_entries: list = None,
    package_count: int = None,
    condition_notes: str = "",
    unit_price_rial: int = None,
    idempotency_key: str = None,
) -> GoodsReceipt:
    """
    Atomic transaction:
    1. Checks idempotency_key to prevent duplicate submissions.
    2. Validates weights and multi-row tare for every line item.
    3. Resolves the parent product for each incoming line (normal parent product or exceptional incoming cut).
       Rejects transactions where the child product has no configured parent.
    4. Validates unit prices (non-negative integer).
    5. Creates finalized GoodsReceipt with aggregate totals, document date, and operator.
    6. Creates GoodsReceiptItem and WeighingTareRows for each line with price snapshots.
    7. Posts StockMovement (IN) crediting the parent product inventory.
    """
    if idempotency_key:
        existing = GoodsReceipt.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    # Standardize input lines: support both multi-item list and legacy single-product arguments
    if items_data is None:
        if product is None:
            raise BusinessLogicError("رسید ورود کالا باید دارای حداقل یک قلم کالا باشد.")
        items_data = [{
            'product': product,
            'gross_weight_kg': gross_weight_kg,
            'tare_entries': tare_entries or [],
            'package_count': package_count,
            'condition_notes': condition_notes,
            'unit_price_rial': unit_price_rial,
            'remarks': '',
        }]

    if not items_data:
        raise BusinessLogicError("رسید ورود کالا باید دارای حداقل یک قلم کالا باشد.")

    # Process and validate document date
    if document_date is None:
        doc_date = timezone.localdate()
    elif isinstance(document_date, str):
        from sales.date_utils import parse_jalali_or_gregorian_date
        try:
            doc_date = parse_jalali_or_gregorian_date(document_date) or timezone.localdate()
        except ValueError as e:
            raise BusinessLogicError(f"تاریخ سند نامعتبر است: {str(e)}")
    else:
        doc_date = document_date

    # Resolve operator name
    op_name = operator_name.strip() if operator_name else ""
    if not op_name and operator:
        op_name = getattr(operator, 'get_full_name', lambda: '')() or getattr(operator, 'username', '')

    parsed_items = []
    for item in items_data:
        prod = item['product']
        parent = prod.get_parent() or prod

        gross = Decimal(str(item['gross_weight_kg']))
        tares = item.get('tare_entries', [])
        weighing = calculate_tare_and_net(gross, tares)
        net = weighing['net_weight_kg']

        # Unit price validation
        u_price = item.get('unit_price_rial')
        line_total = None
        if u_price is not None:
            u_price = int(u_price)
            if u_price < 0:
                raise BusinessLogicError(f"قیمت واحد کالای «{prod.name}» نمی‌تواند منفی باشد.")
            line_total = calculate_line_total_rial(net, u_price)

        parsed_items.append({
            'product': prod,
            'parent_product': parent,
            'gross_weight_kg': weighing['gross_weight_kg'],
            'total_tare_weight_kg': weighing['total_tare_weight_kg'],
            'net_weight_kg': net,
            'unit_price_rial': u_price,
            'line_total_rial': line_total,
            'package_count': item.get('package_count'),
            'condition_notes': item.get('condition_notes', ''),
            'remarks': item.get('remarks', ''),
            'tare_rows': weighing['tare_rows'],
        })

    total_gross = sum((item['gross_weight_kg'] for item in parsed_items), Decimal('0.000'))
    total_tare = sum((item['total_tare_weight_kg'] for item in parsed_items), Decimal('0.000'))
    total_net = sum((item['net_weight_kg'] for item in parsed_items), Decimal('0.000'))
    has_prices = any(item['line_total_rial'] is not None for item in parsed_items)
    total_amount = sum((item['line_total_rial'] or 0 for item in parsed_items)) if has_prices else None

    # Populate legacy fields for single-item receipts for backward compatibility
    first_item = parsed_items[0]
    legacy_product = first_item['product'] if len(parsed_items) == 1 else None
    legacy_gross = first_item['gross_weight_kg'] if len(parsed_items) == 1 else total_gross
    legacy_tare = first_item['total_tare_weight_kg'] if len(parsed_items) == 1 else total_tare
    legacy_net = first_item['net_weight_kg'] if len(parsed_items) == 1 else total_net
    legacy_package_count = first_item['package_count'] if len(parsed_items) == 1 else None
    legacy_condition = first_item['condition_notes'] if len(parsed_items) == 1 else ""
    legacy_unit_price = first_item['unit_price_rial'] if len(parsed_items) == 1 else None

    try:
        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(
                document_number=document_number,
                idempotency_key=idempotency_key,
                supplier_name=supplier_name,
                supplier_document_ref=supplier_document_ref,
                document_date=doc_date,
                product=legacy_product,
                gross_weight_kg=legacy_gross,
                total_tare_weight_kg=legacy_tare,
                net_weight_kg=legacy_net,
                total_gross_weight_kg=total_gross,
                total_net_weight_kg=total_net,
                unit_price_rial=legacy_unit_price,
                total_amount_rial=total_amount,
                package_count=legacy_package_count,
                condition_notes=legacy_condition,
                remarks=remarks,
                operator=operator,
                operator_name=op_name,
                status=DocumentStatus.FINALIZED,
            )

            for item in parsed_items:
                receipt_item = GoodsReceiptItem.objects.create(
                    goods_receipt=receipt,
                    product=item['product'],
                    gross_weight_kg=item['gross_weight_kg'],
                    total_tare_weight_kg=item['total_tare_weight_kg'],
                    net_weight_kg=item['net_weight_kg'],
                    unit_price_rial=item['unit_price_rial'],
                    line_total_rial=item['line_total_rial'],
                    package_count=item['package_count'],
                    condition_notes=item['condition_notes'],
                    remarks=item['remarks'],
                )

                for row in item['tare_rows']:
                    WeighingTareRow.objects.create(
                        goods_receipt=receipt,
                        goods_receipt_item=receipt_item,
                        tare_type=row['tare_type'],
                        tare_name_snapshot=row['tare_name_snapshot'],
                        unit_tare_grams=row['unit_tare_grams'],
                        quantity=row['quantity'],
                    )

                # Post inventory ledger movement (IN) credited to parent product
                StockMovement.objects.create(
                    product=item['product'],
                    parent_product=item['parent_product'],
                    direction=StockMovementDirection.IN,
                    movement_type=StockMovementType.RECEIPT,
                    net_weight_kg=item['net_weight_kg'],
                    reference_document_number=document_number,
                    document_date=doc_date,
                    operator=operator,
                    operator_name=op_name,
                    remarks=f"ورود کالا از {supplier_name} - رسید {document_number}",
                )

            return receipt
    except IntegrityError:
        if idempotency_key:
            committed_doc = GoodsReceipt.objects.filter(idempotency_key=idempotency_key).first()
            if committed_doc:
                return committed_doc
        raise


@transaction.atomic
def finalize_goods_issue(
    document_number: str,
    goods_owner_name: str,
    recipient_name: str,
    driver_name: str = "",
    destination_address: str = "",
    issue_reason: str = GoodsIssueReason.SALE,
    operator=None,
    operator_name: str = "",
    document_date=None,
    remarks: str = "",
    items_data: list = None,
    # Legacy parameters for backward compatibility
    product: Product = None,
    gross_weight_kg: Decimal = None,
    tare_entries: list = None,
    unit_price_rial: int = None,
    idempotency_key: str = None,
) -> GoodsIssue:
    """
    Atomic transaction:
    1. Checks idempotency_key to prevent duplicate submissions.
    2. Validates weights and multi-row tare for every line item.
    3. Resolves the parent product for each outgoing line and aggregates demand per parent.
    4. Verifies available parent stock balances atomically. Child cuts draw directly from parent stock.
    5. Creates finalized GoodsIssue header with aggregate totals, document date, and operator.
    6. Creates GoodsIssueItem and WeighingTareRows for each cut.
    7. Posts StockMovement (OUT) crediting against the parent product to deduct inventory.
    """
    if idempotency_key:
        existing = GoodsIssue.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    # Standardize input lines: support both multi-item list and legacy single-product arguments
    if items_data is None:
        if product is None:
            raise BusinessLogicError("حواله خروج باید دارای حداقل یک قلم کالا باشد.")
        items_data = [{
            'product': product,
            'gross_weight_kg': gross_weight_kg,
            'tare_entries': tare_entries or [],
            'unit_price_rial': unit_price_rial,
            'remarks': '',
        }]

    if not items_data:
        raise BusinessLogicError("حواله خروج باید دارای حداقل یک قلم کالا باشد.")

    # Process and validate document date
    if document_date is None:
        doc_date = timezone.localdate()
    elif isinstance(document_date, str):
        from sales.date_utils import parse_jalali_or_gregorian_date
        try:
            doc_date = parse_jalali_or_gregorian_date(document_date) or timezone.localdate()
        except ValueError as e:
            raise BusinessLogicError(f"تاریخ سند نامعتبر است: {str(e)}")
    else:
        doc_date = document_date

    # Resolve operator name
    op_name = operator_name.strip() if operator_name else ""
    if not op_name and operator:
        op_name = getattr(operator, 'get_full_name', lambda: '')() or getattr(operator, 'username', '')

    parsed_items = []
    parent_demands = {}

    for item in items_data:
        prod = item['product']
        parent = prod.get_parent() or prod

        gross = Decimal(str(item['gross_weight_kg']))
        tares = item.get('tare_entries', [])
        weighing = calculate_tare_and_net(gross, tares)
        net = weighing['net_weight_kg']
        u_price = item.get('unit_price_rial')
        line_total = None
        if u_price is not None:
            u_price = int(u_price)
            if u_price < 0:
                raise BusinessLogicError(f"قیمت واحد کالای «{prod.name}» نمی‌تواند منفی باشد.")
            line_total = calculate_line_total_rial(net, u_price)

        parsed_items.append({
            'product': prod,
            'parent_product': parent,
            'gross_weight_kg': weighing['gross_weight_kg'],
            'total_tare_weight_kg': weighing['total_tare_weight_kg'],
            'net_weight_kg': net,
            'unit_price_rial': u_price,
            'line_total_rial': line_total,
            'remarks': item.get('remarks', ''),
            'tare_rows': weighing['tare_rows'],
        })
        parent_demands[parent.id] = parent_demands.get(parent.id, Decimal('0.000')) + net

    # Simulate stock availability across all lines using Child-First consumption with Parent fallback
    simulated_stock = {}
    for item in parsed_items:
        prod = item['product']
        if prod.id not in simulated_stock:
            simulated_stock[prod.id] = get_product_independent_stock(prod)
        parent = item['parent_product']
        if parent and parent.id not in simulated_stock:
            simulated_stock[parent.id] = get_product_independent_stock(parent)

    allocations = []
    for item in parsed_items:
        prod = item['product']
        parent = item['parent_product']
        net = item['net_weight_kg']

        if prod.is_parent or not parent or parent.id == prod.id:
            # Standalone or Parent product: must be fulfilled entirely from its own stock
            current_avail = simulated_stock.get(prod.id, Decimal('0.000'))
            if net > current_avail:
                raise InsufficientStockError(
                    f"موجودی کالای «{prod.name}» کافی نیست (موجودی فعلی: {current_avail} کیلوگرم، درخواستی: {net} کیلوگرم)."
                )
            simulated_stock[prod.id] -= net
            allocations.append({
                'child_deduction': net,
                'parent_deduction': Decimal('0.000'),
            })
        else:
            # Child product: consume child's own independent stock first, then parent fallback
            child_avail = max(Decimal('0.000'), simulated_stock.get(prod.id, Decimal('0.000')))
            child_deduct = min(child_avail, net)
            parent_needed = net - child_deduct

            parent_avail = max(Decimal('0.000'), simulated_stock.get(parent.id, Decimal('0.000')))
            if parent_needed > parent_avail:
                total_child_avail = child_avail + parent_avail
                raise InsufficientStockError(
                    f"موجودی کالای «{prod.name}» و والد آن «{parent.name}» کافی نیست (موجودی کل قابل تخصیص: {total_child_avail} کیلوگرم، درخواستی: {net} کیلوگرم)."
                )
            simulated_stock[prod.id] -= child_deduct
            simulated_stock[parent.id] -= parent_needed
            allocations.append({
                'child_deduction': child_deduct,
                'parent_deduction': parent_needed,
            })

    total_gross = sum((item['gross_weight_kg'] for item in parsed_items), Decimal('0.000'))
    total_tare = sum((item['total_tare_weight_kg'] for item in parsed_items), Decimal('0.000'))
    total_net = sum((item['net_weight_kg'] for item in parsed_items), Decimal('0.000'))
    has_prices = any(item['line_total_rial'] is not None for item in parsed_items)
    total_amount = sum((item['line_total_rial'] or 0 for item in parsed_items)) if has_prices else None

    # Populate legacy fields for single-item issues or first product for backward compatibility
    first_item = parsed_items[0]
    legacy_product = first_item['product'] if len(parsed_items) == 1 else None
    legacy_gross = first_item['gross_weight_kg'] if len(parsed_items) == 1 else total_gross
    legacy_tare = first_item['total_tare_weight_kg'] if len(parsed_items) == 1 else total_tare
    legacy_net = first_item['net_weight_kg'] if len(parsed_items) == 1 else total_net
    legacy_unit_price = first_item['unit_price_rial'] if len(parsed_items) == 1 else None
    legacy_line_total = first_item['line_total_rial'] if len(parsed_items) == 1 else total_amount

    try:
        with transaction.atomic():
            issue = GoodsIssue.objects.create(
                document_number=document_number,
                idempotency_key=idempotency_key,
                goods_owner_name=goods_owner_name,
                recipient_name=recipient_name,
                driver_name=driver_name,
                destination_address=destination_address,
                issue_reason=issue_reason,
                document_date=doc_date,
                product=legacy_product,
                gross_weight_kg=legacy_gross,
                total_tare_weight_kg=legacy_tare,
                net_weight_kg=legacy_net,
                unit_price_rial=legacy_unit_price,
                line_total_rial=legacy_line_total,
                total_gross_weight_kg=total_gross,
                total_net_weight_kg=total_net,
                total_amount_rial=total_amount,
                operator=operator,
                operator_name=op_name,
                remarks=remarks,
                status=DocumentStatus.FINALIZED,
            )

            for item, alloc in zip(parsed_items, allocations):
                issue_item = GoodsIssueItem.objects.create(
                    goods_issue=issue,
                    product=item['product'],
                    gross_weight_kg=item['gross_weight_kg'],
                    total_tare_weight_kg=item['total_tare_weight_kg'],
                    net_weight_kg=item['net_weight_kg'],
                    unit_price_rial=item['unit_price_rial'],
                    line_total_rial=item['line_total_rial'],
                    remarks=item['remarks'],
                )
                for row in item['tare_rows']:
                    WeighingTareRow.objects.create(
                        goods_issue=issue,
                        goods_issue_item=issue_item,
                        tare_type=row['tare_type'],
                        tare_name_snapshot=row['tare_name_snapshot'],
                        unit_tare_grams=row['unit_tare_grams'],
                        quantity=row['quantity'],
                    )

                # Record stock movements according to child-first and parent fallback allocation
                child_deduct = alloc['child_deduction']
                parent_deduct = alloc['parent_deduction']

                if child_deduct > Decimal('0.000'):
                    StockMovement.objects.create(
                        product=item['product'],
                        parent_product=None,
                        direction=StockMovementDirection.OUT,
                        movement_type=StockMovementType.ISSUE,
                        net_weight_kg=child_deduct,
                        reference_document_number=document_number,
                        document_date=doc_date,
                        operator=operator,
                        operator_name=op_name,
                        remarks=f"خروج از موجودی مستقل {item['product'].name} برای {recipient_name} - حواله {document_number}",
                    )

                if parent_deduct > Decimal('0.000'):
                    parent_prod = item['parent_product']
                    StockMovement.objects.create(
                        product=item['product'],
                        parent_product=parent_prod,
                        direction=StockMovementDirection.OUT,
                        movement_type=StockMovementType.ISSUE,
                        net_weight_kg=parent_deduct,
                        reference_document_number=document_number,
                        document_date=doc_date,
                        operator=operator,
                        operator_name=op_name,
                        remarks=f"خروج از سهمیه والد ({parent_prod.name}) جهت {item['product'].name} برای {recipient_name} - حواله {document_number}",
                    )

            return issue
    except IntegrityError:
        if idempotency_key:
            committed_doc = GoodsIssue.objects.filter(idempotency_key=idempotency_key).first()
            if committed_doc:
                return committed_doc
        raise


@transaction.atomic
def finalize_invoice(
    document_number: str,
    goods_owner_name: str,
    buyer_name: str,
    items_data: list,
    driver_name: str = "",
    operator=None,
    operator_name: str = "",
    document_date=None,
    remarks: str = "",
    invoice_type: str = InvoiceType.SALE,
    idempotency_key: str = None,
) -> Invoice:
    """
    Atomic transaction:
    1. Checks idempotency_key to prevent duplicate submissions.
    2. Creates Invoice header with document_date and operator_name.
    3. Snapshots each product item: name, net_weight, unit_price_rial, line_total_rial.
    4. Computes authoritative total amount in Rial.
    """
    if idempotency_key:
        existing = Invoice.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    if not items_data:
        raise BusinessLogicError("فاکتور باید دارای حداقل یک سطر کالا باشد.")

    if document_date is None:
        doc_date = timezone.localdate()
    elif isinstance(document_date, str):
        from sales.date_utils import parse_jalali_or_gregorian_date
        try:
            doc_date = parse_jalali_or_gregorian_date(document_date) or timezone.localdate()
        except ValueError as e:
            raise BusinessLogicError(f"تاریخ سند نامعتبر است: {str(e)}")
    else:
        doc_date = document_date

    op_name = operator_name.strip() if operator_name else ""
    if not op_name and operator:
        op_name = getattr(operator, 'get_full_name', lambda: '')() or getattr(operator, 'username', '')

    invoice = Invoice.objects.create(
        document_number=document_number,
        invoice_type=invoice_type,
        idempotency_key=idempotency_key,
        date=doc_date,
        goods_owner_name=goods_owner_name,
        buyer_name=buyer_name,
        driver_name=driver_name,
        total_amount_rial=0,
        operator=operator,
        operator_name=op_name,
        remarks=remarks,
        status=DocumentStatus.FINALIZED,
    )

    total_rial = 0
    for item in items_data:
        product = item['product']
        if not product.is_active:
            raise BusinessLogicError(f"کالای «{product.name}» غیرفعال است و قابل فروش نیست.")
        net_weight = normalize_weight_kg(item.get('net_weight_kg', '1.000'))
        try:
            qty = int(item.get('quantity', 1))
        except (TypeError, ValueError):
            raise BusinessLogicError(f"تعداد کالای «{product.name}» نامعتبر است.")
        if qty < 1:
            raise BusinessLogicError(f"تعداد کالای «{product.name}» باید حداقل ۱ باشد.")
        if net_weight < Decimal('0.000') or (product.unit == 'kg' and net_weight == Decimal('0.000')):
            raise BusinessLogicError(f"وزن خالص کالای «{product.name}» باید بزرگتر از صفر باشد.")
        raw_price = item.get('unit_price_rial')
        if raw_price is None or raw_price == '':
            raw_price = getattr(product, 'price_per_unit_rial', None) or 0
        price_rial = int(raw_price)
        if price_rial <= 0:
            raise BusinessLogicError(f"قیمت معتبر به ریال برای کالای «{product.name}» تعیین نشده است.")

        if product.unit == 'kg':
            line_total = calculate_line_total_rial(net_weight, price_rial)
        else:
            line_total = calculate_line_total_rial(Decimal(qty), price_rial)

        InvoiceItem.objects.create(
            invoice=invoice,
            product=product,
            product_name_snapshot=product.name,
            quantity=qty,
            net_weight_kg=net_weight,
            unit_price_rial=price_rial,
            total_price_rial=line_total,
        )
        total_rial += line_total

    invoice.total_amount_rial = total_rial
    invoice.save(update_fields=['total_amount_rial'])
    return invoice


@transaction.atomic
def generate_invoice_from_source_documents(
    source_type: str,  # 'SALE' or 'PURCHASE'
    document_ids: list,
    buyer_or_supplier_name: str = "",
    goods_owner_name: str = "",
    driver_name: str = "",
    remarks: str = "",
    operator=None,
    operator_name: str = "",
    document_date=None,
    prices_override: dict = None,
    idempotency_key: str = None,
) -> Invoice:
    """
    Generates an authoritative Invoice linked to existing GoodsIssue or GoodsReceipt documents:
    - Atomically verifies that documents have not already been invoiced.
    - Captures line item snapshots with exact traceability.
    - Locks source documents to the new invoice (invoice=invoice).
    - NEVER creates new StockMovement records, preventing double-deduction or double-addition.
    """
    if idempotency_key:
        existing = Invoice.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    if not document_ids:
        raise BusinessLogicError("حداقل یک سند مبدأ برای صدور فاکتور الزامی است.")

    document_ids = list(dict.fromkeys(document_ids))

    # Process and validate document date
    if document_date is None:
        doc_date = timezone.localdate()
    elif isinstance(document_date, str):
        from sales.date_utils import parse_jalali_or_gregorian_date
        try:
            doc_date = parse_jalali_or_gregorian_date(document_date) or timezone.localdate()
        except ValueError as e:
            raise BusinessLogicError(f"تاریخ سند نامعتبر است: {str(e)}")
    else:
        doc_date = document_date

    op_name = operator_name.strip() if operator_name else ""
    if not op_name and operator:
        op_name = getattr(operator, 'get_full_name', lambda: '')() or getattr(operator, 'username', '')

    prices_override = prices_override or {}

    date_prefix = timezone.now().strftime('%Y%m%d')
    count = Invoice.objects.count() + 1
    doc_prefix = "INV-S" if source_type == 'SALE' else "INV-P"
    doc_num = f"{doc_prefix}-{date_prefix}-{count:04d}"

    invoice_type_val = InvoiceType.SALE if source_type == 'SALE' else InvoiceType.PURCHASE

    if source_type == 'SALE':
        issues = list(GoodsIssue.objects.filter(id__in=document_ids).prefetch_related('items', 'items__product').select_related('product'))
        if len(issues) != len(document_ids):
            raise BusinessLogicError("یک یا چند حواله خروج مشخص شده یافت نشدند.")

        for iss in issues:
            if iss.invoice_id is not None:
                raise BusinessLogicError(f"حواله خروج «{iss.document_number}» قبلاً به فاکتور شماره {iss.invoice.document_number} متصل شده است.")
            if iss.status != DocumentStatus.FINALIZED:
                raise BusinessLogicError(f"حواله خروج «{iss.document_number}» در وضعیت نهایی نیست.")

        invoice = Invoice.objects.create(
            document_number=doc_num,
            invoice_type=invoice_type_val,
            idempotency_key=idempotency_key,
            date=doc_date,
            goods_owner_name=goods_owner_name or (issues[0].goods_owner_name if issues else "فروشگاه پروتئینی"),
            buyer_name=buyer_or_supplier_name or (issues[0].recipient_name if issues else ""),
            driver_name=driver_name or (issues[0].driver_name if issues else ""),
            total_amount_rial=0,
            operator=operator,
            operator_name=op_name,
            remarks=remarks,
            status=DocumentStatus.FINALIZED,
        )

        total_rial = 0
        for iss in issues:
            iss_items = list(iss.items.all())
            if iss_items:
                for item in iss_items:
                    price_key = f"issue_item_{item.id}"
                    price = (
                        prices_override.get(price_key)
                        or prices_override.get(f"issue_{iss.id}")
                        or prices_override.get(str(item.id))
                        or prices_override.get(str(iss.id))
                        or item.unit_price_rial
                        or getattr(iss, 'unit_price_rial', None)
                        or getattr(item.product, 'price_per_unit_rial', None)
                    )
                    if price is None or int(price) <= 0:
                        raise BusinessLogicError(
                            f"قیمت فروش معتبر به ریال برای ردیف «{item.product.name}» حواله خروج «{iss.document_number}» تعیین نشده است."
                        )
                    price = int(price)
                    net_wt = item.net_weight_kg
                    line_total = calculate_line_total_rial(net_wt, price)
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=item.product,
                        source_issue_item=item,
                        product_name_snapshot=item.product.name,
                        quantity=1,
                        net_weight_kg=net_wt,
                        unit_price_rial=price,
                        total_price_rial=line_total,
                    )
                    total_rial += line_total
            elif iss.product:
                price_key = f"issue_{iss.id}"
                price = (
                    prices_override.get(price_key)
                    or prices_override.get(str(iss.id))
                    or getattr(iss, 'unit_price_rial', None)
                    or getattr(iss.product, 'price_per_unit_rial', None)
                )
                if price is None or int(price) <= 0:
                    raise BusinessLogicError(
                        f"قیمت فروش معتبر به ریال برای حواله خروج «{iss.document_number}» تعیین نشده است."
                    )
                price = int(price)
                net_wt = iss.aggregate_net_weight
                line_total = calculate_line_total_rial(net_wt, price)
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=iss.product,
                    product_name_snapshot=iss.product.name,
                    quantity=1,
                    net_weight_kg=net_wt,
                    unit_price_rial=price,
                    total_price_rial=line_total,
                )
                total_rial += line_total

            iss.invoice = invoice
            iss.save(update_fields=['invoice'])

        if not invoice.items.exists():
            raise BusinessLogicError("هیچ سطر کالایی برای صدور فاکتور از حواله‌های انتخابی یافت نشد.")

        invoice.total_amount_rial = total_rial
        invoice.save(update_fields=['total_amount_rial'])
        return invoice

    elif source_type == 'PURCHASE':
        receipts = list(GoodsReceipt.objects.filter(id__in=document_ids).prefetch_related('items', 'items__product').select_related('product'))
        if len(receipts) != len(document_ids):
            raise BusinessLogicError("یک یا چند رسید ورود مشخص شده یافت نشدند.")

        for rec in receipts:
            if rec.invoice_id is not None:
                raise BusinessLogicError(f"رسید ورود «{rec.document_number}» قبلاً به فاکتور خرید متصل شده است.")
            if rec.status != DocumentStatus.FINALIZED:
                raise BusinessLogicError(f"رسید ورود «{rec.document_number}» در وضعیت نهایی نیست.")

        invoice = Invoice.objects.create(
            document_number=doc_num,
            invoice_type=invoice_type_val,
            idempotency_key=idempotency_key,
            date=doc_date,
            goods_owner_name=goods_owner_name or "فروشگاه پروتئینی",
            buyer_name=buyer_or_supplier_name or (receipts[0].supplier_name if receipts else ""),
            driver_name=driver_name,
            total_amount_rial=0,
            operator=operator,
            operator_name=op_name,
            remarks=remarks,
            status=DocumentStatus.FINALIZED,
        )

        total_rial = 0
        for rec in receipts:
            rec_items = list(rec.items.all())
            if rec_items:
                for item in rec_items:
                    price_key = f"receipt_item_{item.id}"
                    price = (
                        prices_override.get(price_key)
                        or prices_override.get(f"receipt_{rec.id}")
                        or prices_override.get(str(item.id))
                        or prices_override.get(str(rec.id))
                        or getattr(item, 'unit_price_rial', None)
                        or getattr(rec, 'unit_price_rial', None)
                    )
                    if price is None or int(price) <= 0:
                        raise BusinessLogicError(
                            f"قیمت خرید معتبر به ریال برای ردیف «{item.product.name}» رسید ورود «{rec.document_number}» تعیین نشده است."
                        )
                    price = int(price)
                    net_wt = item.net_weight_kg
                    qty = item.package_count or 1
                    line_total = calculate_line_total_rial(net_wt, price)
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=item.product,
                        source_receipt=rec,
                        source_receipt_item=item,
                        product_name_snapshot=item.product.name,
                        quantity=qty,
                        net_weight_kg=net_wt,
                        unit_price_rial=price,
                        total_price_rial=line_total,
                    )
                    total_rial += line_total
            elif rec.product and (rec.aggregate_net_weight > Decimal('0.000') or rec.net_weight_kg is not None):
                price_key = f"receipt_{rec.id}"
                price = (
                    prices_override.get(price_key)
                    or prices_override.get(str(rec.id))
                    or getattr(rec, 'unit_price_rial', None)
                )
                if price is None or int(price) <= 0:
                    raise BusinessLogicError(
                        f"قیمت خرید معتبر به ریال برای رسید ورود «{rec.document_number}» تعیین نشده است."
                    )
                price = int(price)
                net_wt = rec.aggregate_net_weight
                qty = rec.package_count or 1
                line_total = calculate_line_total_rial(net_wt, price)
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=rec.product,
                    source_receipt=rec,
                    product_name_snapshot=rec.product.name,
                    quantity=qty,
                    net_weight_kg=net_wt,
                    unit_price_rial=price,
                    total_price_rial=line_total,
                )
                total_rial += line_total
            else:
                # Incomplete historical record: safely skip
                pass

            rec.invoice = invoice
            rec.save(update_fields=['invoice'])

        if not invoice.items.exists():
            raise BusinessLogicError("هیچ سطر کالایی برای صدور فاکتور از رسیدهای انتخابی یافت نشد.")

        invoice.total_amount_rial = total_rial
        invoice.save(update_fields=['total_amount_rial'])
        return invoice
    else:
        raise BusinessLogicError(f"نوع مبدأ نامعتبر است: {source_type}")


@transaction.atomic
def cancel_invoice(invoice: Invoice, operator=None, cancellation_reason: str = "") -> Invoice:
    """
    Safely cancels an invoice:
    - Disassociates linked source issues (sets invoice=None).
    - Disassociates linked source receipts (sets invoice=None).
    - Sets invoice status to CANCELLED.
    - Appends cancellation details to remarks.
    Does NOT delete the invoice record, ensuring full financial traceability.
    Repeated cancellation is a no-op: an already-cancelled invoice is returned unchanged.
    """
    # Re-read the persisted state so a stale object or a retried request cannot cancel twice
    invoice.refresh_from_db()
    if invoice.status == DocumentStatus.CANCELLED:
        return invoice

    invoice.source_issues.update(invoice=None)
    invoice.source_receipts.update(invoice=None)
    invoice.status = DocumentStatus.CANCELLED
    reason_note = f"ابطال توسط {operator.username if operator else 'کاربر'}: {cancellation_reason}".strip()
    if invoice.remarks:
        invoice.remarks = f"{invoice.remarks}\n[{reason_note}]"
    else:
        invoice.remarks = f"[{reason_note}]"
    invoice.save(update_fields=['status', 'remarks'])
    return invoice


@transaction.atomic
def finalize_processing_record(
    document_number: str,
    input_items: list,
    output_items: list,
    operator=None,
    remarks: str = "",
) -> ProcessingRecord:
    """
    Atomic transaction for product transformation/cutting:
    1. Validates inputs exist in inventory.
    2. Deducts inputs from stock (StockMovement OUT, PROCESSING_INPUT).
    3. Adds outputs to stock (StockMovement IN, PROCESSING_OUTPUT).
    4. Computes yield percentage and unexplained variance.
    """
    if not input_items:
        raise BusinessLogicError("عملیات تبدیل باید حداقل دارای یک قلم ماده اولیه ورودی باشد.")
    if not output_items:
        raise BusinessLogicError("عملیات تبدیل باید حداقل دارای یک قلم محصول خروجی باشد.")

    total_in = Decimal('0.000')
    for inp in input_items:
        prod = inp['product']
        wt = Decimal(str(inp['net_weight_kg']))
        bal = get_product_stock_balance(prod)
        if wt > bal:
            raise InsufficientStockError(
                f"موجودی ماده اولیه «{prod.name}» کافی نیست (موجودی: {bal} kg، درخواستی: {wt} kg)."
            )
        total_in += wt

    total_out = Decimal('0.000')
    for out in output_items:
        wt = Decimal(str(out['net_weight_kg']))
        total_out += wt

    variance = total_in - total_out
    if total_in > Decimal('0.000'):
        yield_pct = (total_out / total_in) * Decimal('100.0')
    else:
        yield_pct = Decimal('0.00')

    if variance == Decimal('0.000'):
        reconciliation_status = ProcessingReconciliationStatus.RECONCILED
    elif variance > Decimal('0.000'):
        reconciliation_status = ProcessingReconciliationStatus.UNEXPLAINED_LOSS
    else:
        reconciliation_status = ProcessingReconciliationStatus.NEGATIVE_VARIANCE_FLAGGED

    record = ProcessingRecord.objects.create(
        document_number=document_number,
        operator=operator,
        total_input_weight_kg=total_in,
        total_output_weight_kg=total_out,
        unexplained_variance_kg=variance,
        yield_percentage=round(yield_pct, 2),
        reconciliation_status=reconciliation_status,
        remarks=remarks,
        status=DocumentStatus.FINALIZED,
    )

    for inp in input_items:
        prod = inp['product']
        wt = Decimal(str(inp['net_weight_kg']))
        ProcessingInputLine.objects.create(
            processing_record=record,
            product=prod,
            net_weight_kg=wt,
        )
        StockMovement.objects.create(
            product=prod,
            direction=StockMovementDirection.OUT,
            movement_type=StockMovementType.PROCESSING_INPUT,
            net_weight_kg=wt,
            reference_document_number=document_number,
            operator=operator,
            remarks=f"مصرف در فرآوری {document_number}",
        )

    for out in output_items:
        prod = out['product']
        wt = Decimal(str(out['net_weight_kg']))
        is_waste = out.get('is_byproduct_or_waste', False)
        ProcessingOutputLine.objects.create(
            processing_record=record,
            product=prod,
            net_weight_kg=wt,
            is_byproduct_or_waste=is_waste,
        )
        StockMovement.objects.create(
            product=prod,
            direction=StockMovementDirection.IN,
            movement_type=StockMovementType.PROCESSING_OUTPUT,
            net_weight_kg=wt,
            reference_document_number=document_number,
            operator=operator,
            remarks=f"استحصال از فرآوری {document_number} (ضایعات/افت: {is_waste})",
        )

    return record


def calculate_inventory_loss(parent_product: Product = None, start_date=None, end_date=None) -> dict:
    """
    Computes yield and loss reporting (افت / بازدهی و اختلاف وزن) for parent product(s).
    Loss / Variance = incoming parent weight (IN) - outgoing child products (OUT).
    Yield % = (outgoing cuts / incoming parent) * 100
    Loss % = (loss / incoming parent) * 100
    Includes child cut breakdown of outgoing products and current stock.

    This is a theoretical, movement-based metric. Reconciliation ADJUSTMENT movements are
    excluded from the period flows so that approved physical loss (reported separately by
    calculate_confirmed_physical_loss) is never counted a second time here.
    """
    if parent_product and not parent_product.is_parent:
        parent_product = parent_product.get_parent() or parent_product

    if parent_product:
        parents = [parent_product]
    else:
        parents = list(
            Product.objects.filter(is_parent=True, is_active=True).select_related('category').order_by('category__display_order', 'id')
        )

    results = []
    overall_in = Decimal('0.000')
    overall_out = Decimal('0.000')

    for parent in parents:
        qs_in = StockMovement.objects.filter(
            Q(parent_product=parent) | Q(product=parent, parent_product__isnull=True),
            direction=StockMovementDirection.IN
        ).exclude(movement_type=StockMovementType.ADJUSTMENT)
        qs_out = StockMovement.objects.filter(
            Q(parent_product=parent) | Q(product=parent, parent_product__isnull=True),
            direction=StockMovementDirection.OUT
        ).exclude(movement_type=StockMovementType.ADJUSTMENT)

        if start_date:
            qs_in = qs_in.filter(document_date__gte=start_date)
            qs_out = qs_out.filter(document_date__gte=start_date)
        if end_date:
            qs_in = qs_in.filter(document_date__lte=end_date)
            qs_out = qs_out.filter(document_date__lte=end_date)

        parent_in = qs_in.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')
        parent_out = qs_out.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')
        current_stock = get_parent_stock_balance(parent)

        loss_kg = parent_in - parent_out
        loss_pct = round((loss_kg / parent_in) * Decimal('100.0'), 2) if parent_in > Decimal('0.000') else Decimal('0.00')
        yield_pct = round((parent_out / parent_in) * Decimal('100.0'), 2) if parent_in > Decimal('0.000') else Decimal('0.00')

        # Detailed breakdown of outgoing child cuts
        cuts = qs_out.values('product__id', 'product__name').annotate(
            total_cut_kg=Sum('net_weight_kg')
        ).order_by('-total_cut_kg')

        cut_breakdown = []
        for c in cuts:
            w = c['total_cut_kg'] or Decimal('0.000')
            share_out = round((w / parent_out) * Decimal('100.0'), 2) if parent_out > Decimal('0.000') else Decimal('0.00')
            share_in = round((w / parent_in) * Decimal('100.0'), 2) if parent_in > Decimal('0.000') else Decimal('0.00')
            cut_breakdown.append({
                'product_id': c['product__id'],
                'product_name': c['product__name'],
                'weight_kg': w,
                'share_of_output_pct': share_out,
                'share_of_input_pct': share_in,
            })

        results.append({
            'parent_product': parent,
            'incoming_weight_kg': parent_in,
            'outgoing_weight_kg': parent_out,
            'loss_kg': loss_kg,
            'loss_percentage': loss_pct,
            'yield_percentage': yield_pct,
            'current_stock_kg': current_stock,
            'cut_breakdown': cut_breakdown,
        })
        overall_in += parent_in
        overall_out += parent_out

    overall_loss = overall_in - overall_out
    overall_loss_pct = round((overall_loss / overall_in) * Decimal('100.0'), 2) if overall_in > Decimal('0.000') else Decimal('0.00')
    overall_yield_pct = round((overall_out / overall_in) * Decimal('100.0'), 2) if overall_in > Decimal('0.000') else Decimal('0.00')

    res_dict = {
        'items': results,
        'overall_incoming_kg': overall_in,
        'overall_outgoing_kg': overall_out,
        'overall_loss_kg': overall_loss,
        'overall_loss_percentage': overall_loss_pct,
        'overall_yield_percentage': overall_yield_pct,
        'start_date': start_date,
        'end_date': end_date,
    }
    if results:
        first = results[0]
        res_dict['parent_in_kg'] = first['incoming_weight_kg']
        res_dict['child_out_kg'] = first['outgoing_weight_kg']
        res_dict['loss_kg'] = first['loss_kg']
        res_dict['loss_pct'] = first['loss_percentage']
        res_dict['yield_pct'] = first['yield_percentage']
        res_dict['cuts_breakdown'] = first['cut_breakdown']
    else:
        res_dict['parent_in_kg'] = Decimal('0.000')
        res_dict['child_out_kg'] = Decimal('0.000')
        res_dict['loss_kg'] = Decimal('0.000')
        res_dict['loss_pct'] = Decimal('0.00')
        res_dict['yield_pct'] = Decimal('0.00')
        res_dict['cuts_breakdown'] = []
    return res_dict


AUTHORITATIVE_RECONCILIATION_STATUSES = [ReconciliationStatus.APPROVED, ReconciliationStatus.CLOSED]


def calculate_confirmed_physical_loss(parent_product: Product = None, start_date=None, end_date=None) -> dict:
    """
    Confirmed physical loss from authoritative physical inventory reconciliations.

    - Authoritative = APPROVED or CLOSED (CLOSED is reachable only from APPROVED) and complete
      (verified opening stock, physical count and discrepancy present).
    - discrepancy_kg = expected - actual: positive is a shortage (confirmed loss), negative a surplus.
    - Confirmed loss sums positive discrepancies only; surpluses and exact matches add nothing.
    - Filters: reconciliation period fully inside [start_date, end_date]; product filter covers the
      parent pool and its child cuts, which are separate stock pools and never overlap.
    - Summary and records come from the same complete (unsliced) queryset.
    """
    qs = PhysicalInventoryReconciliation.objects.select_related('product', 'approved_by', 'created_by')
    if parent_product:
        qs = qs.filter(Q(product=parent_product) | Q(product__parent=parent_product))
    if start_date:
        qs = qs.filter(period_start_date__gte=start_date)
    if end_date:
        qs = qs.filter(period_end_date__lte=end_date)

    authoritative = Q(
        status__in=AUTHORITATIVE_RECONCILIATION_STATUSES,
        opening_stock_kg__isnull=False,
        is_opening_verified=True,
        actual_physical_closing_stock_kg__isnull=False,
        discrepancy_kg__isnull=False,
    )
    confirmed_records = list(qs.filter(authoritative))
    excluded_records = list(qs.exclude(authoritative))

    shortage_kg = Decimal('0.000')
    surplus_kg = Decimal('0.000')
    shortage_count = surplus_count = match_count = 0
    for rec in confirmed_records:
        if rec.discrepancy_kg > Decimal('0.000'):
            shortage_kg += rec.discrepancy_kg
            shortage_count += 1
        elif rec.discrepancy_kg < Decimal('0.000'):
            surplus_kg += -rec.discrepancy_kg
            surplus_count += 1
        else:
            match_count += 1

    return {
        'confirmed_records': confirmed_records,
        'excluded_records': excluded_records,
        'confirmed_loss_kg': shortage_kg,
        'confirmed_surplus_kg': surplus_kg,
        'shortage_count': shortage_count,
        'surplus_count': surplus_count,
        'match_count': match_count,
    }


def is_user_authorized_for_reconciliation(user) -> bool:
    """
    Checks if a user is authorized to approve or close physical inventory reconciliations.
    Authorized users are staff, superusers, or users with explicit permissions.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    if hasattr(user, 'has_perm') and user.has_perm('sales.approve_reconciliation'):
        return True
    return False


def calculate_physical_reconciliation(
    product: Product,
    start_date=None,
    end_date=None,
    actual_physical_closing_stock: Decimal = None,
    opening_stock: Decimal = None,
    is_opening_verified: bool = False,
    is_parent_pool: bool = None,
    user=None,
    notes: str = "",
    save_record: bool = False,
    reconciliation_instance: PhysicalInventoryReconciliation = None,
) -> PhysicalInventoryReconciliation:
    """
    Calculates physical inventory reconciliation for a product or parent inventory pool.
    
    Formula:
        expected_closing_stock = opening_stock + period_receipts - period_issues
        discrepancy = expected_closing_stock - actual_physical_closing_stock
        (Positive = shortage/کسری, Negative = surplus/مازاد, Zero = reconciled/تراز)
        discrepancy_percentage = (discrepancy / expected_closing_stock) * 100 (when expected > 0)
    
    Rules:
    - Calculation alone creates NO stock movements.
    - Opening stock comes from the previous approved period's actual physical closing stock,
      or explicitly verified opening stock. Never invents an opening balance.
    - If actual physical closing stock is missing, reconciliation is marked incomplete.
    - Zero/negative denominators in percentage calculation are handled safely without exceptions.
    - Approved/closed reconciliations cannot be recalculated.
    - Parent and child stock pools are segregated according to Phase 1 rules to prevent double counting.
    """
    if reconciliation_instance and reconciliation_instance.pk:
        if reconciliation_instance.status in [ReconciliationStatus.APPROVED, ReconciliationStatus.CLOSED]:
            raise ReconciliationLockedError("سند انبارگردانی تاییدشده یا بسته‌شده غیرقابل تغییر و محاسبه مجدد است.")

    if is_parent_pool is None:
        is_parent_pool = product.is_parent

    # Standardize dates
    if start_date is None:
        start_date = timezone.localdate()
    elif isinstance(start_date, str):
        from .date_utils import parse_jalali_or_gregorian_date
        start_date = parse_jalali_or_gregorian_date(start_date)

    if end_date is None:
        end_date = timezone.localdate()
    elif isinstance(end_date, str):
        from .date_utils import parse_jalali_or_gregorian_date
        end_date = parse_jalali_or_gregorian_date(end_date)

    # 1. Resolve Opening Stock
    resolved_opening_stock = None
    resolved_is_verified = False

    if opening_stock is not None:
        resolved_opening_stock = Decimal(str(opening_stock))
        resolved_is_verified = is_opening_verified
    else:
        # Check prior approved or closed reconciliation for this product / pool
        prev_recon = PhysicalInventoryReconciliation.objects.filter(
            product=product,
            is_parent_pool=bool(is_parent_pool),
            status__in=[ReconciliationStatus.APPROVED, ReconciliationStatus.CLOSED],
            period_end_date__lte=start_date,
        ).order_by('-period_end_date', '-id').first()

        if prev_recon and prev_recon.actual_physical_closing_stock_kg is not None:
            resolved_opening_stock = prev_recon.actual_physical_closing_stock_kg
            resolved_is_verified = True
        else:
            resolved_opening_stock = None
            resolved_is_verified = False

    # 2. Calculate Period Receipts and Issues without double-counting parent-child stock
    if is_parent_pool and product.is_parent:
        qs_in = StockMovement.objects.filter(
            product=product,
            direction=StockMovementDirection.IN
        ).exclude(movement_type=StockMovementType.ADJUSTMENT)

        qs_out = StockMovement.objects.filter(
            Q(product=product) | Q(parent_product=product, remarks__startswith=PARENT_FALLBACK_PREFIX),
            direction=StockMovementDirection.OUT
        ).exclude(movement_type=StockMovementType.ADJUSTMENT)
    else:
        qs_in = StockMovement.objects.filter(
            product=product,
            direction=StockMovementDirection.IN
        ).exclude(movement_type=StockMovementType.ADJUSTMENT)

        qs_out = StockMovement.objects.filter(
            product=product,
            direction=StockMovementDirection.OUT
        ).exclude(remarks__startswith=PARENT_FALLBACK_PREFIX).exclude(movement_type=StockMovementType.ADJUSTMENT)

    if start_date:
        qs_in = qs_in.filter(document_date__gte=start_date)
        qs_out = qs_out.filter(document_date__gte=start_date)
    if end_date:
        qs_in = qs_in.filter(document_date__lte=end_date)
        qs_out = qs_out.filter(document_date__lte=end_date)

    period_receipts = qs_in.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')
    period_issues = qs_out.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')

    # 3. Calculate Expected Closing Stock
    expected_closing_stock = None
    if resolved_opening_stock is not None and resolved_is_verified:
        expected_closing_stock = resolved_opening_stock + period_receipts - period_issues

    # 4. Actual Physical Closing Stock
    actual_closing_val = None
    if actual_physical_closing_stock is not None:
        actual_closing_val = Decimal(str(actual_physical_closing_stock))

    # 5. Discrepancy
    discrepancy = None
    if expected_closing_stock is not None and actual_closing_val is not None:
        discrepancy = expected_closing_stock - actual_closing_val

    # 6. Discrepancy Percentage (Safely handle division by zero, negative, or undefined denominator)
    discrepancy_percentage = None
    if discrepancy is not None and expected_closing_stock is not None:
        if expected_closing_stock > Decimal('0.000'):
            try:
                discrepancy_percentage = round((discrepancy / expected_closing_stock) * Decimal('100.0'), 2)
            except Exception:
                discrepancy_percentage = None
        else:
            discrepancy_percentage = None

    # Status determination
    status = (
        ReconciliationStatus.CALCULATED
        if (actual_closing_val is not None and expected_closing_stock is not None)
        else ReconciliationStatus.DRAFT
    )

    if save_record:
        if reconciliation_instance:
            recon = reconciliation_instance
        else:
            date_str = timezone.localdate().strftime('%Y%m%d')
            count = PhysicalInventoryReconciliation.objects.count() + 1
            doc_num = f"STK-REC-{date_str}-{count:04d}"
            recon = PhysicalInventoryReconciliation(document_number=doc_num)

        recon.product = product
        recon.is_parent_pool = bool(is_parent_pool)
        recon.period_start_date = start_date
        recon.period_end_date = end_date
        recon.opening_stock_kg = resolved_opening_stock
        recon.is_opening_verified = resolved_is_verified
        recon.period_receipts_kg = period_receipts
        recon.period_issues_kg = period_issues
        recon.expected_closing_stock_kg = expected_closing_stock
        recon.actual_physical_closing_stock_kg = actual_closing_val
        recon.discrepancy_kg = discrepancy
        recon.discrepancy_percentage = discrepancy_percentage
        recon.status = status
        recon.notes = notes
        if user and getattr(user, 'is_authenticated', False):
            recon.created_by = user
        recon.save()
        return recon

    return PhysicalInventoryReconciliation(
        document_number=reconciliation_instance.document_number if reconciliation_instance else "PREVIEW",
        product=product,
        is_parent_pool=bool(is_parent_pool),
        period_start_date=start_date,
        period_end_date=end_date,
        opening_stock_kg=resolved_opening_stock,
        is_opening_verified=resolved_is_verified,
        period_receipts_kg=period_receipts,
        period_issues_kg=period_issues,
        expected_closing_stock_kg=expected_closing_stock,
        actual_physical_closing_stock_kg=actual_closing_val,
        discrepancy_kg=discrepancy,
        discrepancy_percentage=discrepancy_percentage,
        status=status,
        notes=notes,
        created_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
    )


def approve_physical_reconciliation(
    reconciliation: PhysicalInventoryReconciliation,
    user,
    notes: str = "",
    apply_stock_adjustment: bool = False,
    idempotency_key: str = None,
) -> PhysicalInventoryReconciliation:
    """
    Approves a completed physical inventory reconciliation.
    
    Rules:
    - Only authorized users (staff, superusers, or permissions) can approve.
    - Cannot approve incomplete reconciliation (missing physical closing count or unverified opening stock).
    - Repeated approval is idempotent and does NOT create duplicate stock adjustment movements.
    - If apply_stock_adjustment=True and discrepancy != 0, creates an explicit, traceable StockMovement
      with movement_type=StockMovementType.ADJUSTMENT.
    - Historical stock movements are NEVER mutated.
    """
    if not is_user_authorized_for_reconciliation(user):
        raise UnauthorizedReconciliationError("کاربر مجاز به تایید یا تصویب انبارگردانی نمی‌باشد.")

    if not reconciliation.is_complete:
        if reconciliation.actual_physical_closing_stock_kg is None:
            raise IncompleteReconciliationError("امکان تصویب انبارگردانی بدون ثبت موجودی عینی فیزیکی وجود ندارد.")
        if reconciliation.opening_stock_kg is None or not reconciliation.is_opening_verified:
            raise IncompleteReconciliationError("امکان تصویب انبارگردانی بدون تایید موجودی اول دوره وجود ندارد.")

    # Idempotency / Retry Protection: return existing if already approved or closed
    if reconciliation.status in [ReconciliationStatus.APPROVED, ReconciliationStatus.CLOSED]:
        return reconciliation

    with transaction.atomic():
        reconciliation.status = ReconciliationStatus.APPROVED
        reconciliation.approved_by = user
        reconciliation.approved_at = timezone.now()
        if idempotency_key:
            reconciliation.idempotency_key = idempotency_key
        if notes:
            reconciliation.notes = (reconciliation.notes + "\n" + notes).strip()

        if apply_stock_adjustment and reconciliation.discrepancy_kg and reconciliation.discrepancy_kg != Decimal('0.000'):
            if not reconciliation.adjustment_movement:
                disc = reconciliation.discrepancy_kg
                if disc > Decimal('0.000'):
                    # Shortage: recorded expected > actual physical count -> reduce inventory
                    direction = StockMovementDirection.OUT
                    desc = "کسری"
                else:
                    # Surplus: recorded expected < actual physical count -> increase inventory
                    direction = StockMovementDirection.IN
                    desc = "مازاد"

                adj_weight = abs(disc)
                user_name = getattr(user, 'get_full_name', lambda: '')() or user.username

                adj_movement = StockMovement.objects.create(
                    product=reconciliation.product,
                    parent_product=reconciliation.product.get_parent() or reconciliation.product,
                    direction=direction,
                    movement_type=StockMovementType.ADJUSTMENT,
                    net_weight_kg=adj_weight,
                    reference_document_number=reconciliation.document_number,
                    document_date=reconciliation.period_end_date,
                    operator=user,
                    operator_name=user_name,
                    remarks=f"تعدیل انبارگردانی {reconciliation.document_number} ({desc} به میزان {adj_weight} کیلوگرم)",
                )
                reconciliation.adjustment_movement = adj_movement

        reconciliation.save()

    return reconciliation


def close_physical_reconciliation(
    reconciliation: PhysicalInventoryReconciliation,
    user,
) -> PhysicalInventoryReconciliation:
    """
    Closes an approved physical inventory reconciliation permanently.
    """
    if not is_user_authorized_for_reconciliation(user):
        raise UnauthorizedReconciliationError("کاربر مجاز به بستن قطعی انبارگردانی نمی‌باشد.")

    if reconciliation.status == ReconciliationStatus.CLOSED:
        return reconciliation

    if reconciliation.status != ReconciliationStatus.APPROVED:
        raise BusinessLogicError("فقط اسناد انبارگردانی تاییدشده قابل بستن قطعی می‌باشند.")

    reconciliation.status = ReconciliationStatus.CLOSED
    reconciliation.save()
    return reconciliation


# ---------------------------------------------------------------------------
# Phase 4 Data-Safety & Catalogue Integrity Services
# ---------------------------------------------------------------------------

CHICKEN_BURGER_CANONICAL_VARIANTS = {
    "چیکن برگر",
    "چیکنبرگر",
    "برگر مرغ",
    "برگر چیکن",
}


def normalize_persian_product_name(name: str) -> str:
    """
    Normalizes Persian product names for robust comparison without modifying database records:
    - Removes zero-width non-joiners (half-space \u200c, \u200b, \ufeff)
    - Normalizes Arabic/Persian letter variants (ي -> ی, ك -> ک, ة -> ه)
    - Collapses multiple whitespace characters and strips leading/trailing spaces
    """
    if not name:
        return ""
    s = str(name).replace('\u200c', ' ').replace('\u200b', '').replace('\ufeff', '')
    s = s.replace('ي', 'ی').replace('ك', 'ک').replace('ة', 'ه')
    s = " ".join(s.split())
    return s.strip()


def is_equivalent_chicken_burger_name(name: str) -> bool:
    """
    Checks if a product name matches any known variant of Chicken Burger.
    Handles Persian zero-width non-joiners (half-space), collapsed spacing,
    and standard butchery naming conventions.
    """
    if not name:
        return False
    norm = normalize_persian_product_name(name)
    if norm in CHICKEN_BURGER_CANONICAL_VARIANTS:
        return True
    no_space = norm.replace(" ", "")
    if no_space in {"چیکنبرگر", "برگرمرغ", "برگرچیکن"}:
        return True
    return False


def resolve_canonical_parent_product(category) -> tuple:
    """
    Deterministically resolves the canonical parent carcass product for a category.
    Orders candidates stably by ID: .filter(category=category, is_parent=True).order_by('id')
    Returns: (canonical_parent, all_candidate_parents, has_ambiguity)
    """
    if not category:
        return None, [], False
    parents = list(Product.objects.filter(category=category, is_parent=True).order_by('id'))
    if not parents:
        return None, [], False
    has_ambiguity = len(parents) > 1
    return parents[0], parents, has_ambiguity


def safe_apply_catalogue_integrity(apps=None, dry_run=False) -> dict:
    """
    Safe, non-destructive catalogue integrity procedure:
    1. Preserves existing is_active status on all products (never reactivates inactive products).
    2. Normalizes Persian names (\u200c, whitespace, variants) to prevent duplicate creation.
    3. Resolves parent products deterministically using order_by('id').
    4. Never reassigns ambiguous matches.
    5. Preserves existing product IDs and historical relationships.
    """
    CatModel = apps.get_model('products', 'Category') if apps else Category
    ProdModel = apps.get_model('products', 'Product') if apps else Product

    cat_chicken = CatModel.objects.filter(slug='chicken').first()
    if not cat_chicken:
        cat_chicken = CatModel.objects.create(name='مرغ', slug='chicken', display_order=1, is_active=True)

    parent_chicken = ProdModel.objects.filter(category=cat_chicken, is_parent=True).order_by('id').first()
    if not parent_chicken:
        parent_chicken = ProdModel.objects.create(
            category=cat_chicken,
            name='مرغ',
            unit='kg',
            is_parent=True,
            is_active=True
        )

    results = {
        'reassigned_count': 0,
        'preserved_inactive_count': 0,
        'created_count': 0,
        'ambiguous_skipped': [],
        'existing_found': None,
    }

    # 1. Inspect existing products in cat_chicken to find any equivalent chicken burger
    chicken_prods = ProdModel.objects.filter(category=cat_chicken)
    existing_equiv = None
    for p in chicken_prods:
        if is_equivalent_chicken_burger_name(p.name):
            existing_equiv = p
            results['existing_found'] = p
            break

    # 2. Check for unambiguous misplaced chicken burger products in OTHER categories
    other_prods = ProdModel.objects.exclude(category=cat_chicken)
    for p in other_prods:
        if is_equivalent_chicken_burger_name(p.name):
            if existing_equiv:
                results['ambiguous_skipped'].append((p.id, p.name, "Duplicate variant found in both categories"))
                continue
            old_active = p.is_active
            p.category = cat_chicken
            p.parent = parent_chicken
            # CRITICAL: Preserve existing is_active status!
            if not dry_run:
                p.save(update_fields=['category', 'parent'])
            results['reassigned_count'] += 1
            if not old_active:
                results['preserved_inactive_count'] += 1
            existing_equiv = p
            results['existing_found'] = p
        elif "چیکن" in p.name or "برگر مرغ" in p.name:
            results['ambiguous_skipped'].append((p.id, p.name, "Ambiguous keyword match"))

    # 3. Only create standard 'چیکن برگر' if NO equivalent product was found anywhere
    if not existing_equiv:
        if not dry_run:
            new_p = ProdModel.objects.create(
                category=cat_chicken,
                name='چیکن برگر',
                unit='kg',
                parent=parent_chicken,
                is_active=True,
                description='برگر تهیه شده از سینه و فیله مرغ'
            )
            results['created_count'] += 1
            results['existing_found'] = new_p

    # 4. Deterministic parent linkage for unparented cuts
    for slug in ['chicken', 'lamb', 'beef', 'turkey']:
        cat = CatModel.objects.filter(slug=slug).first()
        if not cat:
            continue
        p_carcass = ProdModel.objects.filter(category=cat, is_parent=True).order_by('id').first()
        if p_carcass:
            unparented = ProdModel.objects.filter(category=cat, parent__isnull=True).exclude(id=p_carcass.id)
            if not dry_run:
                unparented.update(parent=p_carcass)

    return results


