from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # In-app sign-in for operational pages (rendered inside the MeatShop layout, not Django Admin)
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('products.urls')),
    path('products/', include('products.urls')),
    path('', include('sales.urls')),
]
