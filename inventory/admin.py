from django.contrib import admin

from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "sale_price", "is_active")
    list_filter = ("organization",)
    search_fields = ("code", "name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("date", "product", "kind", "quantity", "organization")
    list_filter = ("organization", "kind")
