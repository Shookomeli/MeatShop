from django.urls import path
from . import views

urlpatterns = [
    # Inventory Stock Overview & Cardex
    path('inventory/', views.inventory_overview_view, name='inventory_overview'),

    # Goods Receipts (ورود کالا)
    path('receipts/', views.goods_receipt_list_view, name='receipt_list'),
    path('receipts/new/', views.goods_receipt_create_view, name='receipt_create'),
    path('receipts/<int:pk>/', views.goods_receipt_detail_view, name='receipt_detail'),

    # Goods Issues (خروج و حواله کالا)
    path('issues/', views.goods_issue_list_view, name='issue_list'),
    path('issues/new/', views.goods_issue_create_view, name='issue_create'),
    path('issues/<int:pk>/', views.goods_issue_detail_view, name='issue_detail'),

    # Invoices (فاکتورها)
    path('invoices/', views.invoice_list_view, name='invoice_list'),
    path('invoices/new/', views.invoice_create_view, name='invoice_create'),
    path('invoices/from-source/', views.invoice_from_source_view, name='invoice_from_source'),
    path('invoices/<int:pk>/', views.invoice_detail_view, name='invoice_detail'),
    path('invoices/<int:pk>/cancel/', views.invoice_cancel_view, name='invoice_cancel'),

    # Phase 9: Reports & Data Analytics (گزارش‌ها و تحلیل آمار)
    path('reports/', views.reports_hub_view, name='reports_hub'),
    path('reports/sales/', views.sales_summary_report_view, name='report_sales'),
    path('reports/inventory/', views.inventory_balance_report_view, name='report_inventory'),
    path('reports/loss/', views.inventory_loss_report_view, name='report_loss'),
    path('reports/tare/', views.tare_analysis_report_view, name='report_tare'),
    path('reports/sales/export/csv/', views.export_sales_csv_view, name='export_sales_csv'),
    path('reports/inventory/export/csv/', views.export_inventory_csv_view, name='export_inventory_csv'),

    # Scale Integration & Simulation API
    path('scale/read/', views.scale_read_api, name='scale_read_api'),
    path('scale/set/', views.scale_set_weight_api, name='scale_set_weight_api'),
]
