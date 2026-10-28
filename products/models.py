from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=64, unique=True, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(
        max_length=64,
        unique=True,
        allow_unicode=True,
        verbose_name="شناسه یکتا (اسلاگ)"
    )
    display_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name


class Product(models.Model):
    UNIT_CHOICES = [
        ('kg', 'کیلوگرم'),
        ('pack', 'بسته'),
        ('piece', 'عدد'),
    ]

    name = models.CharField(max_length=128, verbose_name="نام کالا")
    code = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کد کالا (اختیاری)"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name="دسته‌بندی"
    )
    unit = models.CharField(
        max_length=16,
        choices=UNIT_CHOICES,
        default='kg',
        verbose_name="واحد سنجش"
    )
    price_per_unit_rial = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت پایه واحد به ریال (اختیاری)"
    )
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال")
    description = models.TextField(blank=True, verbose_name="توضیحات قطعه")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_products',
        verbose_name="کالای والد (دسته‌بندی اصلی)"
    )
    is_parent = models.BooleanField(
        default=False,
        verbose_name="کالای والد است"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")

    class Meta:
        verbose_name = "کالا"
        verbose_name_plural = "کالاها"
        ordering = ['category', 'name']

    def __str__(self):
        return self.name

    def get_parent(self):
        """
        Resolves and returns the canonical parent product for inventory management.
        If self is marked as a parent, returns self.
        If self has an explicit parent configured, recursively returns that parent.
        If no explicit parent is set, looks for a parent product in the same category.
        """
        if self.is_parent:
            return self
        if self.parent_id is not None:
            if self.parent == self:
                return self
            return self.parent.get_parent()

        # Phase 5: Ambiguity Reporting
        # Fallback: look up designated parent product in this category
        parents = list(Product.objects.filter(category=self.category, is_parent=True).order_by('id'))
        if not parents:
            return None

        if len(parents) > 1:
            # Cannot automatically determine parent. Return None to indicate ambiguity safely.
            return None

        cat_parent = parents[0]
        if cat_parent.id != self.id:
            return cat_parent
        return None

    @property
    def parent_name(self):
        parent = self.get_parent()
        return parent.name if parent else "بدون والد"

    @property
    def price_display(self):
        """Formats the price in Toman or Rial based on settings without altering the stored Rial value."""
        if self.price_per_unit_rial is None:
            return "تعیین نشده"
        display_unit = getattr(settings, 'CURRENCY_DISPLAY_UNIT', 'TOMAN')
        if display_unit == 'TOMAN':
            toman_value = self.price_per_unit_rial // 10
            return f"{toman_value:,} تومان"
        return f"{self.price_per_unit_rial:,} ریال"

    def clean(self):
        super().clean()
        if not self.name or not self.name.strip():
            raise ValidationError({'name': 'نام کالا نمی‌تواند خالی باشد.'})
        # If code is blank string, store as None to avoid unique constraint violations
        if self.code is not None and not self.code.strip():
            self.code = None

        if self.parent_id:
            if self.id and self.parent_id == self.id:
                raise ValidationError({'parent': 'یک کالا نمی‌تواند والد خودش باشد.'})

            # Check if parent is actually a parent product
            if self.parent and not self.parent.is_parent:
                raise ValidationError({'parent': 'کالای انتخاب شده به عنوان والد، خود یک کالای والد نیست.'})

            # Circular dependency check
            visited = set()
            current_parent = self.parent
            while current_parent is not None:
                if current_parent.id in visited:
                    break
                visited.add(current_parent.id)
                if self.id and current_parent.id == self.id:
                    raise ValidationError({'parent': 'ارجاع حلقوی در انتخاب والد مجاز نیست.'})
                current_parent = current_parent.parent

        if self.is_parent and self.parent_id is not None:
            raise ValidationError({'parent': 'کالای والد نمی‌تواند خود دارای والد باشد.'})

    def save(self, *args, **kwargs):
        if self.code is not None and not self.code.strip():
            self.code = None

        # Only attempt to auto-assign a parent if there's no ambiguity.
        if not self.is_parent and self.parent_id is None and self.category_id:
            parents = list(Product.objects.filter(category_id=self.category_id, is_parent=True).order_by('id'))
            if len(parents) == 1:
                cat_parent = parents[0]
                if cat_parent.id != self.id:
                    self.parent = cat_parent
            elif len(parents) > 1:
                # Do NOT auto-assign and hide the ambiguity. It's better to let validation or the user handle it.
                pass

        self.full_clean()
        super().save(*args, **kwargs)
