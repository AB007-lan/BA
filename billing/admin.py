from django.contrib import admin

from .models import Customer, Invoice, InvoiceLine, Payment


class LineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "customer", "total_ttc", "organization")
    list_filter = ("organization",)
    inlines = [LineInline]


admin.site.register(Customer)
admin.site.register(Payment)
