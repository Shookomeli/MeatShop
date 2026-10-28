from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_order', 'is_active', 'get_product_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    ordering = ('display_order', 'id')

    def get_product_count(self, obj):
        return obj.products.count()
    get_product_count.short_description = "تعداد اقلام"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'code', 'unit', 'price_display', 'is_active', 'updated_at')
    list_filter = ('category', 'unit', 'is_active')
    search_fields = ('name', 'code')
    list_editable = ('is_active',)
    ordering = ('category', 'name')
