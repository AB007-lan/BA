from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests import make_org
from billing.models import Customer, Invoice, Payment
from inventory.models import Product, StockMovement

from .models import CashClosing, CashMovement, Expense, Sale

D1, D2 = date(2026, 10, 1), date(2026, 10, 2)


class SaleStockTests(TestCase):
    def setUp(self):
        self.org, _ = make_org("A", "a")
        self.bread = Product.objects.create(organization=self.org, code="P001", name="Pain", sale_price=15)
        StockMovement.objects.create(organization=self.org, product=self.bread, kind="IN", quantity=100)

    def test_sale_moves_stock_and_follows_edits(self):
        sale = Sale.objects.create(organization=self.org, date=D1, product=self.bread, quantity=10)
        self.assertEqual(sale.amount, Decimal("150"))
        self.assertEqual(sale.description, "Pain")
        self.assertEqual(self.bread.current_stock, Decimal("90"))
        sale.quantity = 4
        sale.save()
        self.assertEqual(self.bread.current_stock, Decimal("96"))
        sale.delete()
        self.assertEqual(self.bread.current_stock, Decimal("100"))

    def test_free_sale_does_not_touch_stock(self):
        sale = Sale.objects.create(organization=self.org, date=D1, description="Divers", quantity=1, unit_price=250)
        self.assertEqual(sale.amount, Decimal("250"))
        self.assertFalse(StockMovement.objects.filter(sale=sale).exists())

    def test_discount_rounding(self):
        sugar = Product.objects.create(organization=self.org, code="P3", name="Sucre", sale_price=45)
        sale = Sale.objects.create(organization=self.org, date=D2, product=sugar, quantity=10, discount_rate=Decimal("0.05"))
        self.assertEqual(sale.amount, Decimal("427.50"))


class ClosingTests(TestCase):
    def setUp(self):
        self.org, _ = make_org("A", "a")
        self.org.opening_cash = 5000
        self.org.save()

    def test_day_figures_match_the_excel_kit(self):
        Sale.objects.create(organization=self.org, date=D1, description="Pain", quantity=10, unit_price=15)
        Sale.objects.create(organization=self.org, date=D1, description="Lait", quantity=2, unit_price=60)
        Sale.objects.create(organization=self.org, date=D1, description="Recharge", quantity=5, unit_price=100, method="BANKILY")
        Sale.objects.create(organization=self.org, date=D1, description="Divers", quantity=1, unit_price=250)
        Expense.objects.create(organization=self.org, date=D1, label="Livraison", amount=300)
        day1 = CashClosing.objects.create(organization=self.org, date=D1, counted_cash=5235)
        f = day1.day_figures()
        self.assertEqual((f["opening"], f["cash_sales"], f["other_sales"]), (Decimal("5000"), Decimal("520"), Decimal("500")))
        self.assertEqual((f["theoretical"], f["difference"]), (Decimal("5220"), Decimal("15")))

        CashMovement.objects.create(organization=self.org, date=D2, kind="retrait", amount=1000)
        customer = Customer.objects.create(organization=self.org, name="C")
        inv = Invoice.objects.create(organization=self.org, customer=customer, date=D2)
        Payment.objects.create(organization=self.org, invoice=inv, date=D2, amount=200, method="ESPECES")
        day2 = CashClosing.objects.create(organization=self.org, date=D2, counted_cash=4435)
        f2 = day2.day_figures()
        self.assertEqual(f2["opening"], Decimal("5235"))  # counted the day before
        self.assertEqual((f2["theoretical"], f2["difference"]), (Decimal("4435"), Decimal("0")))

    def test_one_closing_per_day(self):
        self.client.login(username="a", password="S3cure-pass!")
        CashClosing.objects.create(organization=self.org, date=D1, counted_cash=1)
        resp = self.client.post(reverse("closing_create"), {"date": "2026-10-01", "counted_cash": "5"})
        self.assertIn("date", resp.context["form"].errors)

    def test_closing_list_renders(self):
        self.client.login(username="a", password="S3cure-pass!")
        CashClosing.objects.create(organization=self.org, date=D1, counted_cash=5000)
        self.assertContains(self.client.get(reverse("closing_list")), "Clôtures de caisse")
