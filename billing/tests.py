from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests import make_org
from inventory.models import Product

from .models import Customer, Invoice, Payment


def line_data(prefix_rows, total_forms=None):
    data = {"lines-TOTAL_FORMS": str(total_forms or len(prefix_rows)), "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "50"}
    for i, row in enumerate(prefix_rows):
        for k, v in row.items():
            data[f"lines-{i}-{k}"] = v
    return data


class InvoiceTests(TestCase):
    def setUp(self):
        self.org, _ = make_org("A", "a")
        self.org.default_vat_rate = Decimal("0.16")
        self.org.save()
        self.kit = Product.objects.create(organization=self.org, code="KIT", name="Kit stock", sale_price=1500)
        self.customer = Customer.objects.create(organization=self.org, name="Pharmacie", payment_terms_days=15)
        self.client.login(username="a", password="S3cure-pass!")

    def create_invoice(self, day="2026-10-02"):
        data = {"date": day, "customer": self.customer.pk, "due_date": "", "subject": "Kits"}
        data.update(line_data([
            {"product": self.kit.pk, "quantity": "2", "discount_rate": "0.10"},
            {"description": "Formation 1 h", "quantity": "1", "unit_price": "800", "discount_rate": "0"},
        ]))
        resp = self.client.post(reverse("invoice_create"), data)
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["lines"].errors)
        return Invoice.objects.latest("id")

    def test_totals_numbering_due_date(self):
        inv = self.create_invoice()
        self.assertEqual(inv.number, "FAC-2026-0001")
        self.assertEqual((inv.total_ht, inv.total_vat, inv.total_ttc), (Decimal("3500"), Decimal("560"), Decimal("4060")))
        self.assertEqual(inv.due_date, date(2026, 10, 17))
        self.assertEqual(self.create_invoice().number, "FAC-2026-0002")

    def test_payment_status_and_overpayment(self):
        inv = self.create_invoice(day=timezone.localdate().isoformat())
        self.assertEqual(inv.status, Invoice.Status.TO_COLLECT)
        resp = self.client.post(reverse("payment_create"), {"invoice": inv.pk, "date": timezone.localdate().isoformat(),
                                                            "amount": "5000", "method": "BANKILY"})
        self.assertEqual(resp.status_code, 200)  # refused: more than the balance
        Payment.objects.create(organization=self.org, invoice=inv, amount=2000, method="BANKILY")
        self.assertEqual(inv.status, Invoice.Status.PARTIAL)
        self.assertEqual(inv.balance, Decimal("2060"))
        Payment.objects.create(organization=self.org, invoice=inv, amount=2060, method="ESPECES")
        self.assertEqual(Invoice.objects.with_paid().get(pk=inv.pk).status, Invoice.Status.PAID)

    def test_late_status(self):
        inv = self.create_invoice(day=(timezone.localdate() - timedelta(days=40)).isoformat())
        self.assertEqual(inv.status, Invoice.Status.LATE)

    def test_invoice_requires_a_line(self):
        data = {"date": "2026-10-02", "customer": self.customer.pk}
        data.update(line_data([], total_forms=1))
        resp = self.client.post(reverse("invoice_create"), data)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Invoice.objects.exists())

    def test_invoice_with_payment_cannot_be_deleted(self):
        inv = self.create_invoice()
        Payment.objects.create(organization=self.org, invoice=inv, amount=100)
        self.client.post(reverse("invoice_delete", args=[inv.pk]))
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())

    def test_print_view(self):
        inv = self.create_invoice()
        resp = self.client.get(reverse("invoice_detail", args=[inv.pk]))
        self.assertContains(resp, "FAC-2026-0001")
        self.assertContains(resp, "4 060")
