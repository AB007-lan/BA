from django.urls import path

from . import views

urlpatterns = [
    path("clients/", views.CustomerList.as_view(), name="customer_list"),
    path("clients/nouveau/", views.CustomerCreate.as_view(), name="customer_create"),
    path("clients/<int:pk>/", views.CustomerUpdate.as_view(), name="customer_update"),
    path("clients/<int:pk>/supprimer/", views.CustomerDelete.as_view(), name="customer_delete"),
    path("factures/", views.InvoiceList.as_view(), name="invoice_list"),
    path("factures/nouvelle/", views.InvoiceCreate.as_view(), name="invoice_create"),
    path("factures/<int:pk>/", views.InvoiceDetail.as_view(), name="invoice_detail"),
    path("factures/<int:pk>/modifier/", views.InvoiceUpdate.as_view(), name="invoice_update"),
    path("factures/<int:pk>/supprimer/", views.InvoiceDelete.as_view(), name="invoice_delete"),
    path("paiements/", views.PaymentList.as_view(), name="payment_list"),
    path("paiements/nouveau/", views.PaymentCreate.as_view(), name="payment_create"),
    path("paiements/<int:pk>/supprimer/", views.PaymentDelete.as_view(), name="payment_delete"),
]
