import json
import csv
from datetime import datetime, date
from decimal import Decimal
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg, F
from django.views.decorators.http import require_http_methods
from products.models import Product, Category
from .models import (
    TareType,
    GoodsReceipt,
    GoodsReceiptItem,
    GoodsIssue,
    GoodsIssueItem,
    WeighingTareRow,
    StockMovement,
    Invoice,
    InvoiceItem,
    InvoiceType,
    Operator,
    GoodsIssueReason,
    DocumentStatus,
    ReconciliationStatus,
    PhysicalInventoryReconciliation,
)
from .services import (
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
    calculate_inventory_loss,
    calculate_physical_reconciliation,
    approve_physical_reconciliation,
    close_physical_reconciliation,
    InvalidTareWeightError,
    InsufficientStockError,
    BusinessLogicError,
    UnauthorizedReconciliationError,
    ReconciliationLockedError,
    IncompleteReconciliationError,
)
from .date_utils import (
    parse_jalali_or_gregorian_date,
    get_tehran_date_range_bounds,
    to_jalali_date,
    to_jalali_datetime,
    to_latin_digits,
    to_persian_digits,
)
from scale.service import get_scale, get_stable_weight
from scale.base import ScaleUnavailableError, UnstableWeightError


# ---------------------------------------------------------------------------
# Scale Simulation API Endpoints (Used by interactive UI buttons)
# ---------------------------------------------------------------------------

def scale_read_api(request):
    """Returns current scale reading, stability, and connectivity status."""
    scale = get_scale()
    try:
        is_connected = scale.is_connected() if hasattr(scale, 'is_connected') else True
        if not is_connected:
            return JsonResponse({'success': False, 'error': 'ترازو متصل نیست.'}, status=503)

        weight = scale.get_weight()
        stable = scale.is_stable()
        return JsonResponse({
            'success': True,
            'weight_kg': float(weight),
            'is_stable': stable,
            'is_connected': True,
        })
    except ScaleUnavailableError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=503)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["POST"])
def scale_set_weight_api(request):
    """Sets simulated scale load (developer helper for testing weighing workflows)."""
    scale = get_scale()
    try:
        data = json.loads(request.body.decode('utf-8'))
        weight = Decimal(str(data.get('weight', '0.000')))
        settling = float(data.get('settling_duration', 0.1))
        if hasattr(scale, 'set_target_weight'):
            scale.set_target_weight(weight, settling_duration=settling)
            return JsonResponse({'success': True, 'target_weight': float(weight)})
        return JsonResponse({'success': False, 'error': 'Scale is not a MockScale'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ---------------------------------------------------------------------------
# Inventory Overview & Cardex View
# ---------------------------------------------------------------------------

def inventory_overview_view(request):
    """Current stock balance cards by cut and category, plus recent movement ledger."""
    category_slug = request.GET.get('category', '').strip()
    query = request.GET.get('q', '').strip()

    products = Product.objects.select_related('category', 'parent').filter(is_active=True)
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if query:
        query_clean = query.strip()
        latin_q = to_latin_digits(query_clean)
        persian_q = to_persian_digits(query_clean)
        products = products.filter(
            Q(name__icontains=query_clean) |
            Q(name__icontains=latin_q) |
            Q(name__icontains=persian_q) |
            Q(code__icontains=query_clean) |
            Q(code__icontains=latin_q) |
            Q(code__icontains=persian_q)
        )

    products = products.order_by('category__display_order', 'category__id', '-is_parent', 'name', 'id')

    stock_items = []
    total_inventory_weight = Decimal('0.000')

    for p in products:
        bal = get_product_stock_balance(p)
        avail = get_product_available_stock(p)
        stock_items.append({
            'product': p,
            'balance_kg': bal,
            'available_kg': avail,
        })
        total_inventory_weight += bal

    recent_movements = StockMovement.objects.select_related('product', 'operator').order_by('-timestamp')[:25]
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')

    context = {
        'stock_items': stock_items,
        'total_inventory_weight': total_inventory_weight,
        'recent_movements': recent_movements,
        'categories': categories,
        'selected_category': category_slug,
        'query': query,
    }
    return render(request, 'sales/inventory.html', context)


# ---------------------------------------------------------------------------
# Goods Receipt (ورود کالا)
# ---------------------------------------------------------------------------

def goods_receipt_list_view(request):
    receipts = GoodsReceipt.objects.select_related('product', 'product__category', 'operator', 'invoice').prefetch_related('items__product', 'tare_rows').order_by('-date_time')
    return render(request, 'sales/receipt_list.html', {'receipts': receipts})


def goods_receipt_detail_view(request, pk):
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related('product', 'product__category', 'operator', 'invoice').prefetch_related(
            'items__product',
            'items__product__category',
            'items__tare_rows__tare_type',
            'tare_rows__tare_type'
        ),
        pk=pk
    )
    return render(request, 'sales/receipt_detail.html', {'receipt': receipt})


def goods_receipt_create_view(request):
    products = Product.objects.filter(is_active=True).select_related('category', 'parent').order_by(
        'category__display_order', 'category__id', '-is_parent', 'name'
    )
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')
    tare_types = TareType.objects.filter(is_active=True).order_by('tare_weight_grams')
    operators = Operator.objects.filter(is_active=True).order_by('display_order', 'id')

    today_jalali = to_jalali_date(timezone.localdate(), fmt='%Y/%m/%d', persian_digits=False)
    form_data = {
        'document_date': today_jalali,
        'operator_selection': operators.first().name if operators.exists() else '',
    }
    form_errors = {}

    if request.method == 'POST':
        form_data = request.POST.dict()
        if not form_data.get('document_date'):
            form_data['document_date'] = today_jalali
        supplier_name = request.POST.get('supplier_name', '').strip()
        supplier_doc_ref = request.POST.get('supplier_document_ref', '').strip()
        document_date_str = request.POST.get('document_date', '').strip()
        operator_selection = request.POST.get('operator_selection', '').strip() or request.POST.get('operator_select', '').strip()
        operator_custom = request.POST.get('operator_custom', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        idempotency_key = request.POST.get('idempotency_key', '').strip() or None

        op_name = operator_custom.strip() if operator_selection == 'custom' or not operator_selection else operator_selection.strip()

        items_json = request.POST.get('items_json', '').strip()
        parsed_items_data = None

        try:
            if not supplier_name:
                form_errors['supplier_name'] = "نام تأمین‌کننده یا مبدأ بار الزامی است."
                raise BusinessLogicError("نام تأمین‌کننده یا مبدأ بار الزامی است.")

            # Validate document date
            parsed_date = None
            if document_date_str:
                try:
                    parsed_date = parse_jalali_or_gregorian_date(document_date_str)
                except ValueError as ve:
                    form_errors['document_date'] = str(ve)
                    raise BusinessLogicError(str(ve))

            if items_json:
                raw_items = json.loads(items_json)
                if not raw_items:
                    form_errors['items'] = "لطفاً حداقل یک قلم کالا برای ثبت رسید اضافه نمایید."
                    raise BusinessLogicError("لطفاً حداقل یک قلم کالا برای ثبت رسید اضافه نمایید.")
                parsed_items_data = []
                for idx, raw in enumerate(raw_items, 1):
                    pid = raw.get('product_id')
                    if not pid:
                        raise BusinessLogicError(f"کالای ردیف {idx} انتخاب نشده است.")
                    try:
                        prod = Product.objects.get(pk=int(pid), is_active=True)
                    except (Product.DoesNotExist, ValueError):
                        raise BusinessLogicError(f"کالای انتخاب‌شده در ردیف {idx} معتبر نمی‌باشد.")

                    gross_wt = Decimal(str(raw.get('gross_weight_kg', '0')))
                    if gross_wt <= Decimal('0.000'):
                        raise BusinessLogicError(f"وزن ناخالص ردیف {idx} باید بزرگتر از صفر باشد.")

                    unit_p = raw.get('unit_price_rial')
                    unit_price_rial = int(unit_p) if unit_p not in (None, '', 'null') else None

                    tares = []
                    for tr in raw.get('tare_entries', []):
                        tt_id = int(tr['tare_type_id'])
                        tt = TareType.objects.get(pk=tt_id)
                        qty = int(tr.get('quantity', 1))
                        custom_g = int(tr.get('custom_tare_grams', 0))
                        tares.append({
                            'tare_type': tt,
                            'quantity': qty,
                            'custom_tare_grams': custom_g,
                        })

                    pkg = raw.get('package_count')
                    parsed_items_data.append({
                        'product': prod,
                        'gross_weight_kg': gross_wt,
                        'tare_entries': tares,
                        'unit_price_rial': unit_price_rial,
                        'package_count': int(pkg) if pkg else None,
                        'condition_notes': raw.get('condition_notes', '').strip(),
                        'remarks': raw.get('remarks', '').strip(),
                    })

            date_prefix = timezone.now().strftime('%Y%m%d')
            count_today = GoodsReceipt.objects.count() + 1
            doc_num = f"REC-{date_prefix}-{count_today:04d}"

            if parsed_items_data:
                receipt = finalize_goods_receipt(
                    document_number=doc_num,
                    supplier_name=supplier_name,
                    supplier_document_ref=supplier_doc_ref,
                    operator=request.user if request.user.is_authenticated else None,
                    operator_name=op_name,
                    document_date=parsed_date,
                    remarks=remarks,
                    items_data=parsed_items_data,
                    idempotency_key=idempotency_key,
                )
            else:
                # Fallback to single-product form submission
                product_id = request.POST.get('product') or request.POST.get('selected_product_id')
                if not product_id:
                    form_errors['product'] = "لطفاً کالا را انتخاب نمایید."
                    raise BusinessLogicError("لطفاً کالا را انتخاب نمایید.")
                try:
                    product = Product.objects.get(pk=int(product_id), is_active=True)
                except (Product.DoesNotExist, ValueError):
                    form_errors['product'] = "کالای انتخاب‌شده معتبر نمی‌باشد."
                    raise BusinessLogicError("کالای انتخاب‌شده معتبر نمی‌باشد.")

                gross_weight_str = request.POST.get('gross_weight_kg', '0').strip()
                gross_weight = Decimal(gross_weight_str) if gross_weight_str else Decimal('0.000')
                package_count = request.POST.get('package_count') or None
                condition_notes = request.POST.get('condition_notes', '').strip()
                unit_price_str = request.POST.get('unit_price_rial', '').strip()
                unit_price_rial = int(unit_price_str) if unit_price_str else None

                tare_ids = request.POST.getlist('tare_type_id')
                tare_qtys = request.POST.getlist('tare_qty')
                custom_grams_list = request.POST.getlist('custom_tare_grams')

                tare_entries = []
                for i, tid in enumerate(tare_ids):
                    if tid:
                        try:
                            tt = TareType.objects.get(pk=int(tid))
                            qty = int(tare_qtys[i]) if i < len(tare_qtys) and tare_qtys[i] else 1
                            custom_g = int(custom_grams_list[i]) if i < len(custom_grams_list) and custom_grams_list[i] else 0
                            tare_entries.append({
                                'tare_type': tt,
                                'quantity': qty,
                                'custom_tare_grams': custom_g,
                            })
                        except (TareType.DoesNotExist, ValueError):
                            pass

                receipt = finalize_goods_receipt(
                    document_number=doc_num,
                    supplier_name=supplier_name,
                    product=product,
                    gross_weight_kg=gross_weight,
                    tare_entries=tare_entries,
                    unit_price_rial=unit_price_rial,
                    supplier_document_ref=supplier_doc_ref,
                    package_count=int(package_count) if package_count else None,
                    condition_notes=condition_notes,
                    document_date=parsed_date,
                    operator=request.user if request.user.is_authenticated else None,
                    operator_name=op_name,
                    remarks=remarks,
                    idempotency_key=idempotency_key,
                )

            messages.success(
                request,
                f"رسید ورود کالا به شماره «{receipt.document_number}» به وزن خالص {receipt.aggregate_net_weight} کیلوگرم با موفقیت ثبت شد."
            )
            return redirect('receipt_detail', pk=receipt.pk)
        except (InvalidTareWeightError, BusinessLogicError) as e:
            form_errors['general'] = str(e)
            messages.error(request, str(e))
        except Exception as e:
            form_errors['general'] = f"خطای ثبت رسید: {str(e)}"
            messages.error(request, f"خطای ثبت رسید: {str(e)}")

    context = {
        'products': products,
        'categories': categories,
        'tare_types': tare_types,
        'operators': operators,
        'today_jalali': today_jalali,
        'form_data': form_data,
        'form_errors': form_errors,
    }
    return render(request, 'sales/receipt_form.html', context)


# ---------------------------------------------------------------------------
# Goods Issue (خروج و حواله کالا)
# ---------------------------------------------------------------------------

def goods_issue_list_view(request):
    issues = GoodsIssue.objects.select_related('product', 'operator', 'invoice').prefetch_related('items__product').order_by('-date_time')
    return render(request, 'sales/issue_list.html', {'issues': issues})


def goods_issue_detail_view(request, pk):
    issue = get_object_or_404(
        GoodsIssue.objects.select_related('product', 'operator', 'invoice').prefetch_related(
            'items__product',
            'tare_rows',
            'tare_rows__tare_type'
        ),
        pk=pk
    )
    return render(request, 'sales/issue_detail.html', {'issue': issue})


def goods_issue_create_view(request):
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')
    tare_types = TareType.objects.filter(is_active=True).order_by('tare_weight_grams')
    operators = Operator.objects.filter(is_active=True).order_by('display_order', 'id')

    all_products = Product.objects.filter(is_active=True).select_related('category', 'parent').order_by(
        'category__display_order', 'category__id', '-is_parent', 'name'
    )
    products_display = []
    for p in all_products:
        bal = get_product_stock_balance(p)
        avail = get_product_available_stock(p)
        parent = p.get_parent()
        products_display.append({
            'product': p,
            'parent': parent,
            'balance_kg': bal,
            'available_kg': avail,
            'has_stock': avail > Decimal('0.000'),
        })
    # Sort: category order, category id, parent product first, in-stock status, product name
    products_display.sort(key=lambda x: (
        x['product'].category.display_order if x['product'].category else 99,
        x['product'].category.id if x['product'].category else 9999,
        not x['product'].is_parent,
        not x['has_stock'],
        x['product'].name
    ))

    today_jalali = to_jalali_date(timezone.localdate(), fmt='%Y/%m/%d', persian_digits=False)
    form_data = {
        'goods_owner_name': 'واکا پروتئین',
        'document_date': today_jalali,
        'operator_selection': operators.first().name if operators.exists() else '',
    }
    form_errors = {}

    if request.method == 'POST':
        form_data = request.POST.dict()
        if not form_data.get('document_date'):
            form_data['document_date'] = today_jalali
        goods_owner_name = request.POST.get('goods_owner_name', 'واکا پروتئین').strip()
        recipient_name = request.POST.get('recipient_name', '').strip()
        driver_name = request.POST.get('driver_name', '').strip()
        destination_address = request.POST.get('destination_address', '').strip()
        issue_reason = request.POST.get('issue_reason', GoodsIssueReason.SALE)
        document_date_str = request.POST.get('document_date', '').strip()
        operator_selection = request.POST.get('operator_selection', '').strip() or request.POST.get('operator_select', '').strip()
        operator_custom = request.POST.get('operator_custom', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        idempotency_key = request.POST.get('idempotency_key', '').strip() or None

        op_name = operator_custom.strip() if operator_selection == 'custom' or not operator_selection else operator_selection.strip()

        items_json = request.POST.get('items_json', '').strip()
        parsed_items_data = None

        try:
            if not recipient_name:
                form_errors['recipient_name'] = "نام خریدار / تحویل‌گیرنده الزامی است."
                raise BusinessLogicError("نام خریدار / تحویل‌گیرنده الزامی است.")

            parsed_date = None
            if document_date_str:
                try:
                    parsed_date = parse_jalali_or_gregorian_date(document_date_str)
                except ValueError as ve:
                    form_errors['document_date'] = str(ve)
                    raise BusinessLogicError(str(ve))

            if items_json:
                raw_items = json.loads(items_json)
                if not raw_items:
                    form_errors['items'] = "حداقل یک سطر کالا برای صدور حواله الزامی است."
                    raise BusinessLogicError("حداقل یک سطر کالا برای صدور حواله الزامی است.")
                parsed_items_data = []
                for idx, raw in enumerate(raw_items, 1):
                    prod = get_object_or_404(Product, pk=int(raw['product_id']))
                    gross_wt = Decimal(str(raw['gross_weight_kg']))
                    if gross_wt <= Decimal('0.000'):
                        raise BusinessLogicError(f"وزن ناخالص ردیف {idx} باید بزرگتر از صفر باشد.")
                    u_price = int(raw['unit_price_rial']) if raw.get('unit_price_rial') else None
                    tares = []
                    for tr in raw.get('tare_entries', []):
                        tt_id = int(tr['tare_type_id'])
                        tt = TareType.objects.get(pk=tt_id)
                        qty = int(tr.get('quantity', 1))
                        custom_g = int(tr.get('custom_tare_grams', 0))
                        tares.append({
                            'tare_type': tt,
                            'quantity': qty,
                            'custom_tare_grams': custom_g,
                        })
                    parsed_items_data.append({
                        'product': prod,
                        'gross_weight_kg': gross_wt,
                        'tare_entries': tares,
                        'unit_price_rial': u_price,
                        'remarks': raw.get('remarks', ''),
                    })

            date_prefix = timezone.now().strftime('%Y%m%d')
            count_today = GoodsIssue.objects.count() + 1
            doc_num = f"ISS-{date_prefix}-{count_today:04d}"

            if parsed_items_data:
                issue = finalize_goods_issue(
                    document_number=doc_num,
                    goods_owner_name=goods_owner_name,
                    recipient_name=recipient_name,
                    driver_name=driver_name,
                    destination_address=destination_address,
                    issue_reason=issue_reason,
                    document_date=parsed_date,
                    operator=request.user if request.user.is_authenticated else None,
                    operator_name=op_name,
                    remarks=remarks,
                    items_data=parsed_items_data,
                    idempotency_key=idempotency_key,
                )
            else:
                # Fallback to single-product form submission
                product_id = request.POST.get('product')
                if not product_id:
                    form_errors['product'] = "لطفاً حداقل یک کالا برای خروج انتخاب نمایید."
                    raise BusinessLogicError("لطفاً حداقل یک کالا برای خروج انتخاب نمایید.")
                product = get_object_or_404(Product, pk=product_id)
                gross_weight_str = request.POST.get('gross_weight_kg', '0').strip()
                gross_weight = Decimal(gross_weight_str) if gross_weight_str else Decimal('0.000')
                unit_price_str = request.POST.get('unit_price_rial', '').strip()
                unit_price_rial = int(unit_price_str) if unit_price_str else None

                tare_ids = request.POST.getlist('tare_type_id')
                tare_qtys = request.POST.getlist('tare_qty')
                custom_grams_list = request.POST.getlist('custom_tare_grams')

                tare_entries = []
                for i, tid in enumerate(tare_ids):
                    if tid:
                        try:
                            tt = TareType.objects.get(pk=int(tid))
                            qty = int(tare_qtys[i]) if i < len(tare_qtys) and tare_qtys[i] else 1
                            custom_g = int(custom_grams_list[i]) if i < len(custom_grams_list) and custom_grams_list[i] else 0
                            tare_entries.append({
                                'tare_type': tt,
                                'quantity': qty,
                                'custom_tare_grams': custom_g,
                            })
                        except (TareType.DoesNotExist, ValueError):
                            pass

                issue = finalize_goods_issue(
                    document_number=doc_num,
                    product=product,
                    gross_weight_kg=gross_weight,
                    tare_entries=tare_entries,
                    goods_owner_name=goods_owner_name,
                    recipient_name=recipient_name,
                    driver_name=driver_name,
                    destination_address=destination_address,
                    issue_reason=issue_reason,
                    unit_price_rial=unit_price_rial,
                    document_date=parsed_date,
                    operator=request.user if request.user.is_authenticated else None,
                    operator_name=op_name,
                    remarks=remarks,
                    idempotency_key=idempotency_key,
                )

            messages.success(
                request,
                f"حواله خروج کالا به شماره «{issue.document_number}» به وزن خالص {issue.aggregate_net_weight} کیلوگرم با موفقیت صادر شد."
            )
            return redirect('issue_detail', pk=issue.pk)
        except (InsufficientStockError, InvalidTareWeightError, BusinessLogicError) as e:
            form_errors['general'] = str(e)
            messages.error(request, str(e))
        except Exception as e:
            form_errors['general'] = f"خطای ثبت حواله خروج: {str(e)}"
            messages.error(request, f"خطای ثبت حواله خروج: {str(e)}")

    context = {
        'products_display': products_display,
        'products_with_stock': [p for p in products_display if p['has_stock']],
        'categories': categories,
        'tare_types': tare_types,
        'operators': operators,
        'today_jalali': today_jalali,
        'reasons': GoodsIssueReason.choices,
        'form_data': form_data,
        'form_errors': form_errors,
    }
    return render(request, 'sales/issue_form.html', context)


# ---------------------------------------------------------------------------
# Invoices (فاکتور فروش)
# ---------------------------------------------------------------------------

def invoice_list_view(request):
    invoices = Invoice.objects.select_related('operator').prefetch_related('items').order_by('-date', '-id')
    return render(request, 'sales/invoice_list.html', {'invoices': invoices})


def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'sales/invoice_detail.html', {'invoice': invoice})


def invoice_create_view(request):
    products = Product.objects.filter(is_active=True).select_related('category', 'parent').order_by(
        'category__display_order', 'category__id', '-is_parent', 'name'
    )
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')
    operators = Operator.objects.filter(is_active=True).order_by('display_order', 'id')

    today_jalali = to_jalali_date(timezone.localdate(), fmt='%Y/%m/%d', persian_digits=False)
    form_data = {
        'goods_owner_name': 'واکا پروتئین',
        'date': today_jalali,
        'document_date': today_jalali,
        'operator_selection': operators.first().name if operators.exists() else '',
    }
    form_errors = {}

    if request.method == 'POST':
        form_data = request.POST.dict()
        if not form_data.get('document_date'):
            form_data['document_date'] = today_jalali
        if not form_data.get('date'):
            form_data['date'] = today_jalali
        goods_owner_name = request.POST.get('goods_owner_name', 'واکا پروتئین').strip()
        buyer_name = request.POST.get('buyer_name', '').strip()
        driver_name = request.POST.get('driver_name', '').strip()
        date_str = request.POST.get('date', '').strip() or request.POST.get('document_date', '').strip()
        operator_selection = request.POST.get('operator_selection', '').strip() or request.POST.get('operator_select', '').strip()
        operator_custom = request.POST.get('operator_custom', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        idempotency_key = request.POST.get('idempotency_key', '').strip() or None

        op_name = operator_custom.strip() if operator_selection == 'custom' or not operator_selection else operator_selection.strip()

        items_json = request.POST.get('items_json', '').strip()
        items_data = []

        try:
            if not buyer_name:
                form_errors['buyer_name'] = "نام خریدار یا مشتری الزامی است."
                raise BusinessLogicError("نام خریدار یا مشتری الزامی است.")

            parsed_date = None
            if date_str:
                try:
                    parsed_date = parse_jalali_or_gregorian_date(date_str)
                except ValueError as ve:
                    form_errors['date'] = str(ve)
                    raise BusinessLogicError(str(ve))

            if items_json:
                raw_items = json.loads(items_json)
                if not raw_items:
                    form_errors['items'] = "فاکتور فروش باید دارای حداقل یک سطر کالا باشد."
                    raise BusinessLogicError("فاکتور فروش باید دارای حداقل یک سطر کالا باشد.")
                for i, raw in enumerate(raw_items, 1):
                    pid = raw.get('product_id')
                    if not pid:
                        raise BusinessLogicError(f"کالای ردیف {i} انتخاب نشده است.")
                    try:
                        prod = Product.objects.get(pk=int(pid), is_active=True)
                    except (Product.DoesNotExist, ValueError):
                        raise BusinessLogicError(f"کالای ردیف {i} نامعتبر می‌باشد.")

                    wt = Decimal(str(raw.get('net_weight_kg', '1.000')))
                    qty = int(raw.get('quantity', 1))
                    price = int(raw.get('unit_price_rial', 0))
                    if price <= 0:
                        raise BusinessLogicError(f"قیمت واحد کالای ردیف {i} تعیین نشده است.")

                    items_data.append({
                        'product': prod,
                        'net_weight_kg': wt,
                        'quantity': qty,
                        'unit_price_rial': price,
                    })
            else:
                prod_ids = request.POST.getlist('product_id')
                weights = request.POST.getlist('net_weight_kg')
                quantities = request.POST.getlist('quantity')
                prices = request.POST.getlist('unit_price_rial')

                if not prod_ids:
                    # check for indexed format e.g. items[0][product_id]
                    idx = 0
                    while f"items[{idx}][product_id]" in request.POST:
                        prod_ids.append(request.POST.get(f"items[{idx}][product_id]"))
                        weights.append(request.POST.get(f"items[{idx}][net_weight_kg]", "1.000"))
                        quantities.append(request.POST.get(f"items[{idx}][quantity]", "1"))
                        prices.append(request.POST.get(f"items[{idx}][unit_price_rial]", "0"))
                        idx += 1

                for i, pid in enumerate(prod_ids, 1):
                    if not pid:
                        raise BusinessLogicError(f"کالای ردیف {i} انتخاب نشده است.")
                    try:
                        prod = Product.objects.get(pk=int(pid), is_active=True)
                    except (Product.DoesNotExist, ValueError):
                        raise BusinessLogicError(f"کالای ردیف {i} نامعتبر می‌باشد.")

                    wt = Decimal(weights[i-1]) if (i-1) < len(weights) and weights[i-1] else Decimal('1.000')
                    qty = int(quantities[i-1]) if (i-1) < len(quantities) and quantities[i-1] else 1
                    price = int(prices[i-1]) if (i-1) < len(prices) and prices[i-1] else 0
                    if price <= 0:
                        raise BusinessLogicError(f"قیمت واحد کالای ردیف {i} تعیین نشده است.")

                    items_data.append({
                        'product': prod,
                        'net_weight_kg': wt,
                        'quantity': qty,
                        'unit_price_rial': price,
                    })

            if not items_data:
                form_errors['items'] = "فاکتور فروش باید دارای حداقل یک سطر کالا باشد."
                raise BusinessLogicError("فاکتور فروش باید دارای حداقل یک سطر کالا باشد.")

            count_inv = Invoice.objects.count() + 1
            doc_num = f"INV-{count_inv:05d}"

            invoice = finalize_invoice(
                document_number=doc_num,
                goods_owner_name=goods_owner_name,
                buyer_name=buyer_name,
                items_data=items_data,
                driver_name=driver_name,
                document_date=parsed_date,
                operator=request.user if request.user.is_authenticated else None,
                operator_name=op_name,
                remarks=remarks,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f"فاکتور فروش شماره «{invoice.document_number}» با موفقیت صادر شد.")
            return redirect('invoice_detail', pk=invoice.pk)
        except BusinessLogicError as e:
            form_errors['general'] = str(e)
            messages.error(request, str(e))
        except Exception as e:
            form_errors['general'] = f"خطای صدور فاکتور: {str(e)}"
            messages.error(request, f"خطای صدور فاکتور: {str(e)}")

    context = {
        'products': products,
        'categories': categories,
        'operators': operators,
        'today_jalali': today_jalali,
        'form_data': form_data,
        'form_errors': form_errors,
    }
    return render(request, 'sales/invoice_form.html', context)


def invoice_from_source_view(request):
    """
    Issue official sales or purchase invoice from existing source documents:
    Tab 1: Sales invoices from un-invoiced GoodsIssue records.
    Tab 2: Purchase invoices from un-invoiced GoodsReceipt records (requires entering purchase price).
    """
    uninvoiced_issues = GoodsIssue.objects.filter(
        invoice__isnull=True,
        status=DocumentStatus.FINALIZED
    ).prefetch_related('items__product', 'product').order_by('-date_time')

    uninvoiced_receipts = GoodsReceipt.objects.filter(
        invoice__isnull=True,
        status=DocumentStatus.FINALIZED
    ).prefetch_related('items__product').select_related('product', 'product__category').order_by('-date_time')

    if request.method == 'POST':
        source_type = request.POST.get('source_type', 'SALE').strip()
        buyer_or_supplier_name = request.POST.get('buyer_or_supplier_name', '').strip()
        goods_owner_name = request.POST.get('goods_owner_name', 'فروشگاه پروتئینی').strip()
        driver_name = request.POST.get('driver_name', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        idempotency_key = request.POST.get('idempotency_key', '').strip() or None

        prices_override = {}
        for key, val in request.POST.items():
            if (key.startswith('price_override_') or key.startswith('unit_price_rial_')) and val:
                clean_key = key.replace('price_override_', '').replace('unit_price_rial_', '')
                try:
                    prices_override[clean_key] = int(val)
                except ValueError:
                    pass

        try:
            if source_type == 'SALE':
                doc_ids_raw = request.POST.getlist('selected_issues')
                doc_ids = [int(i) for i in doc_ids_raw if i]
                if not doc_ids:
                    raise BusinessLogicError("لطفاً حداقل یک حواله خروج را برای صدور فاکتور فروش انتخاب نمایید.")
            elif source_type == 'PURCHASE':
                doc_ids_raw = request.POST.getlist('selected_receipts')
                doc_ids = [int(i) for i in doc_ids_raw if i]
                if not doc_ids:
                    raise BusinessLogicError("لطفاً حداقل یک رسید ورود را برای صدور فاکتور خرید انتخاب نمایید.")
            else:
                raise BusinessLogicError(f"نوع مبدأ ناشناخته است: {source_type}")

            invoice = generate_invoice_from_source_documents(
                source_type=source_type,
                document_ids=doc_ids,
                buyer_or_supplier_name=buyer_or_supplier_name,
                goods_owner_name=goods_owner_name,
                driver_name=driver_name,
                remarks=remarks,
                operator=request.user if request.user.is_authenticated else None,
                prices_override=prices_override,
                idempotency_key=idempotency_key,
            )
            type_label = "فروش" if source_type == 'SALE' else "خرید"
            messages.success(
                request,
                f"فاکتور {type_label} به شماره «{invoice.document_number}» با موفقیت از اسناد مبدأ صادر شد."
            )
            return redirect('invoice_detail', pk=invoice.pk)
        except BusinessLogicError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"خطای صدور فاکتور از اسناد: {str(e)}")

    context = {
        'uninvoiced_issues': uninvoiced_issues,
        'uninvoiced_receipts': uninvoiced_receipts,
        'active_tab': request.GET.get('tab', 'sales'),
    }
    return render(request, 'sales/invoice_from_source.html', context)


@require_http_methods(["POST"])
def invoice_cancel_view(request, pk):
    """Cancels a finalized invoice safely without deleting financial audit trail."""
    invoice = get_object_or_404(Invoice, pk=pk)
    reason = request.POST.get('cancellation_reason', 'ابطال به درخواست کاربر').strip()
    try:
        cancel_invoice(
            invoice=invoice,
            operator=request.user if request.user.is_authenticated else None,
            cancellation_reason=reason,
        )
        messages.success(
            request,
            f"فاکتور شماره «{invoice.document_number}» ابطال شد و اسناد مبدأ متصل آزاد گردیدند."
        )
    except Exception as e:
        messages.error(request, f"خطا در ابطال فاکتور: {str(e)}")
    return redirect('invoice_detail', pk=pk)


# ---------------------------------------------------------------------------
# Reporting & Analytics Views
# ---------------------------------------------------------------------------

def reports_hub_view(request):
    """Central reporting overview dashboard with KPI metric cards and quick links."""
    total_sales_rial = Invoice.objects.filter(status=DocumentStatus.FINALIZED).aggregate(
        total=Sum('total_amount_rial')
    )['total'] or 0

    total_invoices_count = Invoice.objects.filter(status=DocumentStatus.FINALIZED).count()
    total_receipts_count = GoodsReceipt.objects.count()
    total_issues_count = GoodsIssue.objects.count()

    total_stock_kg = Decimal('0.000')
    parent_balances = get_all_stock_balances()
    for pb in parent_balances:
        total_stock_kg += pb['balance_kg']

    context = {
        'total_sales_rial': total_sales_rial,
        'total_sales_toman': total_sales_rial // 10,
        'total_invoices_count': total_invoices_count,
        'total_receipts_count': total_receipts_count,
        'total_issues_count': total_issues_count,
        'parent_balances': parent_balances,
        'total_stock_kg': total_stock_kg,
    }
    return render(request, 'sales/reports_hub.html', context)


def sales_summary_report_view(request):
    """Sales analysis filtered by date range, customer, category, and cut."""
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()
    buyer = request.GET.get('buyer', '').strip()
    category_slug = request.GET.get('category', '').strip()
    product_id = request.GET.get('product', '').strip()

    invoices = Invoice.objects.filter(status=DocumentStatus.FINALIZED).prefetch_related('items__product__category')

    if start_date_str:
        try:
            start_date = parse_jalali_or_gregorian_date(start_date_str)
            if start_date:
                invoices = invoices.filter(date__gte=start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = parse_jalali_or_gregorian_date(end_date_str)
            if end_date:
                invoices = invoices.filter(date__lte=end_date)
        except ValueError:
            pass

    if buyer:
        invoices = invoices.filter(buyer_name__icontains=buyer)

    invoice_ids = invoices.values_list('id', flat=True)
    items_qs = InvoiceItem.objects.filter(invoice_id__in=invoice_ids).select_related('product__category')

    if category_slug:
        items_qs = items_qs.filter(product__category__slug=category_slug)
    if product_id:
        items_qs = items_qs.filter(product_id=product_id)

    total_revenue_rial = items_qs.aggregate(total=Sum('total_price_rial'))['total'] or 0
    total_sold_weight_kg = items_qs.aggregate(total=Sum('net_weight_kg'))['total'] or Decimal('0.000')

    # Product-level breakdown
    product_stats = items_qs.values(
        'product__id',
        'product__name',
        'product__category__name',
        'product__unit'
    ).annotate(
        total_weight=Sum('net_weight_kg'),
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price_rial'),
    ).order_by('-total_revenue')

    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')
    products = Product.objects.filter(is_active=True).select_related('category', 'parent').order_by(
        'category__display_order', 'category__id', '-is_parent', 'name'
    )

    context = {
        'start_date': start_date_str,
        'end_date': end_date_str,
        'buyer': buyer,
        'selected_category': category_slug,
        'selected_product': product_id,
        'categories': categories,
        'products': products,
        'total_revenue_rial': total_revenue_rial,
        'total_revenue_toman': total_revenue_rial // 10,
        'total_sold_weight_kg': total_sold_weight_kg,
        'invoice_count': invoices.count(),
        'product_stats': product_stats,
    }
    return render(request, 'sales/report_sales.html', context)


def inventory_balance_report_view(request):
    """Detailed inventory audit with category totals and stock status."""
    category_slug = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', 'all').strip()

    products = Product.objects.select_related('category', 'parent').filter(is_active=True)
    if category_slug:
        products = products.filter(category__slug=category_slug)

    products = products.order_by('category__display_order', 'category__id', '-is_parent', 'name', 'id')

    category_summary = {}
    rows = []
    total_inventory_kg = Decimal('0.000')

    for p in products:
        bal = get_product_stock_balance(p)
        cat_name = p.category.name
        if cat_name not in category_summary:
            category_summary[cat_name] = Decimal('0.000')
        category_summary[cat_name] += bal
        total_inventory_kg += bal

        if status_filter == 'in_stock' and bal <= Decimal('0.000'):
            continue
        if status_filter == 'out_of_stock' and bal > Decimal('0.000'):
            continue

        rows.append({
            'product': p,
            'balance_kg': bal,
        })

    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')

    context = {
        'rows': rows,
        'category_summary': category_summary,
        'total_inventory_kg': total_inventory_kg,
        'categories': categories,
        'selected_category': category_slug,
        'selected_status': status_filter,
    }
    return render(request, 'sales/report_inventory.html', context)


def inventory_loss_report_view(request):
    """
    Yield and Loss Analysis report (گزارش افت و بازدهی و تراز گوشت).
    Compares incoming parent carcasses against outgoing cut products to compute net weight loss and yields.
    """
    preset = request.GET.get('preset', 'last30').strip()
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()
    parent_id = request.GET.get('parent_id', '').strip()

    start_date = None
    end_date = None

    today = timezone.localdate()
    if preset == 'today':
        start_date = today
        end_date = today
    elif preset == 'last7':
        from datetime import timedelta
        start_date = today - timedelta(days=7)
        end_date = today
    elif preset == 'last30':
        from datetime import timedelta
        start_date = today - timedelta(days=30)
        end_date = today
    elif preset == 'all':
        start_date = None
        end_date = None
    else:
        # custom date range
        if start_date_str:
            try:
                start_date = parse_jalali_or_gregorian_date(start_date_str)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = parse_jalali_or_gregorian_date(end_date_str)
            except ValueError:
                pass

    parent_product = None
    if parent_id:
        try:
            parent_product = Product.objects.get(pk=int(parent_id), is_parent=True)
        except (Product.DoesNotExist, ValueError):
            pass

    parent_products = Product.objects.filter(is_parent=True, is_active=True).select_related('category').order_by('category__display_order', 'id')
    loss_data = calculate_inventory_loss(parent_product=parent_product, start_date=start_date, end_date=end_date)

    reconciliations = PhysicalInventoryReconciliation.objects.all().select_related('product', 'approved_by', 'created_by')
    if parent_product:
        reconciliations = reconciliations.filter(
            Q(product=parent_product) | Q(product__parent=parent_product)
        )
    if start_date:
        reconciliations = reconciliations.filter(period_start_date__gte=start_date)
    if end_date:
        reconciliations = reconciliations.filter(period_end_date__lte=end_date)

    context = {
        'loss_data': loss_data,
        'parent_products': parent_products,
        'selected_parent_id': parent_id,
        'preset': preset,
        'start_date_str': start_date_str or (to_jalali_date(start_date, persian_digits=False) if start_date else ''),
        'end_date_str': end_date_str or (to_jalali_date(end_date, persian_digits=False) if end_date else ''),
        'reconciliations': reconciliations[:25],
    }
    return render(request, 'sales/report_loss.html', context)


def tare_analysis_report_view(request):
    """Analysis of container tare usage and deductions across receipts and issues."""
    tare_types = TareType.objects.filter(is_active=True).order_by('tare_weight_grams')
    tare_stats = []
    grand_tare_kg = Decimal('0.000')

    for tt in tare_types:
        rows = WeighingTareRow.objects.filter(tare_type=tt)
        count_used = rows.aggregate(total=Sum('quantity'))['total'] or 0
        total_kg = rows.aggregate(total=Sum('subtotal_tare_kg'))['total'] or Decimal('0.000')
        grand_tare_kg += total_kg
        tare_stats.append({
            'tare_type': tt,
            'count_used': count_used,
            'total_tare_kg': total_kg,
        })

    context = {
        'tare_stats': tare_stats,
        'grand_tare_kg': grand_tare_kg,
    }
    return render(request, 'sales/report_tare.html', context)


def export_sales_csv_view(request):
    """Exports sales line items to CSV with Persian UTF-8 BOM encoding for Microsoft Excel."""
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    invoices = Invoice.objects.filter(status=DocumentStatus.FINALIZED)
    if start_date_str:
        try:
            start_date = parse_jalali_or_gregorian_date(start_date_str)
            if start_date:
                invoices = invoices.filter(date__gte=start_date)
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = parse_jalali_or_gregorian_date(end_date_str)
            if end_date:
                invoices = invoices.filter(date__lte=end_date)
        except ValueError:
            pass

    invoice_ids = invoices.values_list('id', flat=True)
    items = InvoiceItem.objects.filter(invoice_id__in=invoice_ids).select_related('invoice', 'product__category').order_by('-invoice__date', '-invoice__id')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="meatshop_sales_export.csv"'
    # Write UTF-8 BOM so Excel opens Persian text without corrupting encoding
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'شماره فاکتور',
        'تاریخ شمسی',
        'تاریخ میلادی',
        'نام خریدار',
        'صاحب کالا',
        'نام کالا',
        'دسته‌بندی',
        'وزن خالص (کیلوگرم)',
        'تعداد',
        'قیمت واحد (ریال)',
        'مبلغ کل سطر (ریال)',
        'مبلغ کل سطر (تومان)',
    ])

    for item in items:
        writer.writerow([
            item.invoice.document_number,
            to_jalali_date(item.invoice.date),
            item.invoice.date.strftime('%Y-%m-%d'),
            item.invoice.buyer_name,
            item.invoice.goods_owner_name,
            item.product_name_snapshot,
            item.product.category.name,
            f"{item.net_weight_kg:.3f}",
            item.quantity,
            item.unit_price_rial,
            item.total_price_rial,
            item.total_price_rial // 10,
        ])

    return response


def export_inventory_csv_view(request):
    """Exports current stock balances to CSV with UTF-8 BOM encoding for Excel."""
    products = Product.objects.select_related('category').filter(is_active=True).order_by('category', 'name', 'id')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="meatshop_inventory_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'ردیف',
        'نام کالا',
        'دسته‌بندی',
        'کد کالا',
        'واحد سنجش',
        'موجودی فعلی (کیلوگرم)',
        'وضعیت موجودی',
    ])

    for i, p in enumerate(products, 1):
        bal = get_product_stock_balance(p)
        status_str = "موجود" if bal > Decimal('0.000') else "کسری / ناموجود"
        writer.writerow([
            i,
            p.name,
            p.category.name,
            p.code or '',
            p.get_unit_display(),
            f"{bal:.3f}",
            status_str,
        ])

    return response
