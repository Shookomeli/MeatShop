from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Product, Category
from .forms import ProductForm


def product_list_view(request):
    """Clean, high-density, searchable Persian catalogue list."""
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', 'all').strip()

    products = Product.objects.select_related('category', 'parent').all()

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)

    if query:
        from sales.date_utils import to_latin_digits, to_persian_digits
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

    products = products.order_by('category__display_order', 'category__id', '-is_parent', 'name')

    categories = Category.objects.filter(is_active=True).order_by('display_order', 'id')
    total_count = Product.objects.count()
    active_count = Product.objects.filter(is_active=True).count()

    context = {
        'products': products,
        'categories': categories,
        'selected_category': category_slug,
        'selected_status': status_filter,
        'query': query,
        'total_count': total_count,
        'active_count': active_count,
    }
    return render(request, 'products/product_list.html', context)


def product_create_view(request):
    """Simple form for adding a new product/cut."""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'کالای «{product.name}» با موفقیت افزوده شد.')
            return redirect('product_list')
    else:
        form = ProductForm()

    return render(request, 'products/product_form.html', {
        'form': form,
        'is_edit': False,
    })


def product_update_view(request, pk):
    """Simple form for editing an existing product/cut."""
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'اطلاعات کالای «{product.name}» بروزرسانی شد.')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)

    return render(request, 'products/product_form.html', {
        'form': form,
        'product': product,
        'is_edit': True,
    })


@require_POST
def product_toggle_active_view(request, pk):
    """Safely toggle product activation status without deleting records."""
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save()
    status_str = "فعال" if product.is_active else "غیرفعال"
    messages.info(request, f'وضعیت کالای «{product.name}» به {status_str} تغییر یافت.')
    return redirect(request.META.get('HTTP_REFERER', 'product_list'))
