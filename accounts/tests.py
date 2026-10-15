from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import Customer, Invoice
from inventory.models import Product

from .models import Membership, Organization

User = get_user_model()


def make_org(name, username, role=Membership.Role.OWNER):
    org = Organization.objects.create(name=name)
    user = User.objects.create_user(username=username, password="S3cure-pass!")
    Membership.objects.create(user=user, organization=org, role=role)
    return org, user


class SignupTests(TestCase):
    def test_signup_creates_organization_and_owner(self):
        resp = self.client.post(reverse("signup"), {
            "username": "ahmed", "email": "", "organization_name": "Pharmacie Al Amal",
            "phone": "+222 49 00 00 00", "password1": "Tres-Sur-2026", "password2": "Tres-Sur-2026",
        })
        self.assertRedirects(resp, reverse("org_settings"))
        membership = Membership.objects.get(user__username="ahmed")
        self.assertEqual(membership.organization.name, "Pharmacie Al Amal")
        self.assertEqual(membership.role, Membership.Role.OWNER)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertRedirects(resp, f"{reverse('login')}?next=/")

    def test_user_without_organization_is_refused(self):
        User.objects.create_user(username="orphan", password="S3cure-pass!")
        self.client.login(username="orphan", password="S3cure-pass!")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})


class TenantIsolationTests(TestCase):
    """A user must never read or change another organization's data."""

    def setUp(self):
        self.org_a, self.user_a = make_org("A", "a")
        self.org_b, self.user_b = make_org("B", "b")
        self.product_a = Product.objects.create(organization=self.org_a, code="P1", name="Riz", sale_price=100)
        customer = Customer.objects.create(organization=self.org_a, name="Client A")
        self.invoice_a = Invoice.objects.create(organization=self.org_a, customer=customer)
        self.client.login(username="b", password="S3cure-pass!")

    def test_lists_only_show_own_records(self):
        self.assertNotContains(self.client.get(reverse("product_list")), "Riz")
        self.assertNotContains(self.client.get(reverse("customer_list")), "Client A")

    def test_cannot_open_or_edit_other_org_records(self):
        for url in (
            reverse("product_update", args=[self.product_a.pk]),
            reverse("invoice_detail", args=[self.invoice_a.pk]),
            reverse("invoice_update", args=[self.invoice_a.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        resp = self.client.post(reverse("product_update", args=[self.product_a.pk]), {"code": "X", "name": "Pirate"})
        self.assertEqual(resp.status_code, 404)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.name, "Riz")

    def test_cannot_reference_other_org_product_in_a_sale(self):
        resp = self.client.post(reverse("sale_create"), {
            "date": "2026-10-15", "product": self.product_a.pk, "quantity": "1", "method": "ESPECES", "discount_rate": "0",
        })
        self.assertEqual(resp.status_code, 200)  # form redisplayed with an error
        self.assertIn("product", resp.context["form"].errors)

    def test_cannot_pay_other_org_invoice(self):
        resp = self.client.post(reverse("payment_create"), {
            "invoice": self.invoice_a.pk, "date": "2026-10-15", "amount": "10", "method": "ESPECES",
        })
        self.assertIn("invoice", resp.context["form"].errors)


class RoleTests(TestCase):
    def setUp(self):
        self.org, _ = make_org("A", "owner")
        self.staff = User.objects.create_user(username="staff", password="S3cure-pass!")
        Membership.objects.create(user=self.staff, organization=self.org, role=Membership.Role.STAFF)
        self.product = Product.objects.create(organization=self.org, code="P1", name="Riz")

    def test_staff_cannot_delete_or_change_settings(self):
        self.client.login(username="staff", password="S3cure-pass!")
        self.assertEqual(self.client.post(reverse("product_delete", args=[self.product.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("org_settings")).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_owner_can_add_staff(self):
        self.client.login(username="owner", password="S3cure-pass!")
        self.client.post(reverse("team"), {"username": "aicha", "password1": "Tres-Sur-2026", "password2": "Tres-Sur-2026"})
        m = Membership.objects.get(user__username="aicha")
        self.assertEqual((m.organization, m.role), (self.org, Membership.Role.STAFF))

    def test_invoice_numbers_are_sequential_per_org(self):
        other, _ = make_org("B", "other")
        self.assertEqual(self.org.next_invoice_number(2026), "FAC-2026-0001")
        self.assertEqual(self.org.next_invoice_number(2026), "FAC-2026-0002")
        self.assertEqual(other.next_invoice_number(2026), "FAC-2026-0001")

    def test_dashboard_renders(self):
        self.client.login(username="owner", password="S3cure-pass!")
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["stock_value"], Decimal("0"))
