from django import forms
from .models import Product, Category


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'category',
            'code',
            'unit',
            'price_per_unit_rial',
            'parent',
            'is_parent',
            'is_active',
            'description',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'نام دقیق برش یا قطعه گوشت',
                'required': True,
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_parent': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'اختیاری (مثلاً ۱۰۱)',
                'dir': 'ltr',
            }),
            'unit': forms.Select(attrs={
                'class': 'form-select',
            }),
            'price_per_unit_rial': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'اختیاری (مبلغ به ریال)',
                'min': '0',
                'dir': 'ltr',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'توضیحات اختیاری درباره ویژگی‌های قطعه',
            }),
        }
        labels = {
            'name': 'نام کالا',
            'category': 'دسته‌بندی',
            'parent': 'کالای والد (برای ردیابی در انبار)',
            'is_parent': 'این کالا، کالای والد (اصلی) است',
            'code': 'کد کالا (اختیاری)',
            'unit': 'واحد سنجش',
            'price_per_unit_rial': 'قیمت پایه واحد به ریال (اختیاری)',
            'is_active': 'وضعیت فعال در فروشگاه',
            'description': 'توضیحات تکمیلی',
        }
        error_messages = {
            'name': {
                'required': 'وارد کردن نام کالا الزامی است.',
            },
            'code': {
                'unique': 'این کد کالا قبلاً ثبت شده است. لطفاً کد دیگری وارد کنید.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True).order_by('display_order', 'id')
        self.fields['parent'].queryset = Product.objects.filter(is_parent=True, is_active=True).select_related('category').order_by('category__display_order', 'category__id', 'name')

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code and not code.strip():
            return None
        return code

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get('parent')
        is_parent = cleaned_data.get('is_parent')

        if parent:
            if not parent.is_parent:
                self.add_error('parent', 'کالای انتخاب شده به عنوان والد، خود یک کالای والد نیست.')
            if is_parent:
                self.add_error('parent', 'کالای والد نمی‌تواند خود دارای والد باشد.')

            # Check for circular reference in form layer
            if self.instance and self.instance.pk:
                if parent.id == self.instance.id:
                    self.add_error('parent', 'یک کالا نمی‌تواند والد خودش باشد.')

                visited = set()
                current_parent = parent
                while current_parent is not None:
                    if current_parent.id in visited:
                        break
                    visited.add(current_parent.id)
                    if current_parent.id == self.instance.id:
                        self.add_error('parent', 'ارجاع حلقوی در انتخاب والد مجاز نیست.')
                        break
                    current_parent = current_parent.parent

        return cleaned_data

