from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list_view, name='product_list'),
    path('new/', views.product_create_view, name='product_create'),
    path('<int:pk>/edit/', views.product_update_view, name='product_edit'),
    path('<int:pk>/toggle-active/', views.product_toggle_active_view, name='product_toggle_active'),
]
