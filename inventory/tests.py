from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests import make_org

from .models import Product, StockMovement


class StockTests(TestCase):
    def setUp(self):
        self.org, _ = make_org("A", "a")
        self.client.login(username="a", password="S3cure-pass!")

    def test_initial_stock_creates_movement_and_status(self):
        self.client.post(reverse("product_create"), {
            "code": "riz25", "name": "Riz 25 kg", "unit": "sac", "purchase_price": "1150", "sale_price": "1300",
            "alert_threshold": "10", "is_active": "on", "initial_stock": "40",
        })
        product = Product.objects.get(organization=self.org, code="RIZ25")
        self.assertEqual(product.current_stock, Decimal("40"))
        StockMovement.objects.create(organization=self.org, product=product, kind="OUT", quantity=32)
        self.assertEqual(product.current_stock, Decimal("8"))
        self.assertEqual(product.status, "a_commander")
        StockMovement.objects.create(organization=self.org, product=product, kind="OUT", quantity=8)
        self.assertEqual(Product.objects.with_stock().get(pk=product.pk).status, "rupture")

    def test_code_unique_per_org_only(self):
        Product.objects.create(organization=self.org, code="P1", name="Riz")
        resp = self.client.post(reverse("product_create"), {"code": "p1", "name": "Doublon", "purchase_price": "0",
                                                            "sale_price": "0", "alert_threshold": "0"})
        self.assertIn("code", resp.context["form"].errors)
        other, _ = make_org("B", "b")
        Product.objects.create(organization=other, code="P1", name="Riz B")  # allowed

    def test_product_with_movements_cannot_be_deleted(self):
        p = Product.objects.create(organization=self.org, code="P1", name="Riz")
        StockMovement.objects.create(organization=self.org, product=p, kind="IN", quantity=1)
        self.client.post(reverse("product_delete", args=[p.pk]))
        self.assertTrue(Product.objects.filter(pk=p.pk).exists())
