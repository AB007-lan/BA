from django.contrib import admin

from .models import CashClosing, CashMovement, Expense, Sale

for model in (Sale, Expense, CashMovement, CashClosing):
    admin.site.register(model)
