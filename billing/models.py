from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import MONEY, PaymentMethod, TenantModel
from inventory.models import QTY, Product

CENT = Decimal("0.01")
RATE = {"max_digits": 5, "decimal_places": 4, "validators": [MinValueValidator(0), MaxValueValidator(1)]}


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class Customer(TenantModel):
    name = models.CharField("nom / raison sociale", max_length=150)
    contact = models.CharField("contact", max_length=100, blank=True)
    phone = models.CharField("téléphone", max_length=40, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    nif = models.CharField("NIF", max_length=40, blank=True)
    payment_terms_days = models.PositiveIntegerField(
        "délai de paiement (jours)", null=True, blank=True, help_text="Vide = délai par défaut de l'entreprise."
    )

    class Meta:
        verbose_name = "client"
        ordering = ["name"]

    def __str__(self):
        return self.name


class InvoiceQuerySet(models.QuerySet):
    def with_paid(self):
        return self.annotate(paid=Coalesce(Sum("payments__amount"), Decimal("0"), output_field=models.DecimalField(**MONEY)))


class Invoice(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        TO_COLLECT = "to_collect", "À encaisser"
        PARTIAL = "partial", "Partielle"
        LATE = "late", "En retard"
        PAID = "paid", "Payée"

    number = models.CharField("numéro", max_length=40, editable=False)
    date = models.DateField("date", default=timezone.localdate)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices", verbose_name="client")
    due_date = models.DateField("échéance", blank=True, null=True, help_text="Vide = calculée selon le délai du client.")
    subject = models.CharField("objet", max_length=200, blank=True)
    total_ht = models.DecimalField(default=0, editable=False, **MONEY)
    total_vat = models.DecimalField(default=0, editable=False, **MONEY)
    total_ttc = models.DecimalField(default=0, editable=False, **MONEY)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        verbose_name = "facture"
        ordering = ["-date", "-id"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="uniq_invoice_number_per_org")]
        indexes = [models.Index(fields=["organization", "date"])]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.organization.next_invoice_number(self.date.year)
        if not self.due_date:
            terms = self.customer.payment_terms_days
            if terms is None:
                terms = self.organization.payment_terms_days
            self.due_date = self.date + timedelta(days=terms)
        super().save(*args, **kwargs)

    def recalculate(self):
        lines = list(self.lines.all())
        self.total_ht = sum((line.amount_ht for line in lines), Decimal("0"))
        self.total_vat = sum((line.amount_vat for line in lines), Decimal("0"))
        self.total_ttc = self.total_ht + self.total_vat
        self.save(update_fields=["total_ht", "total_vat", "total_ttc", "updated_at"])

    @property
    def amount_paid(self):
        paid = getattr(self, "paid", None)
        if paid is None:
            paid = self.payments.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return paid

    @property
    def balance(self):
        return self.total_ttc - self.amount_paid

    @property
    def status(self):
        if self.total_ttc <= 0:
            return self.Status.DRAFT
        if self.balance <= 0:
            return self.Status.PAID
        if self.due_date and self.due_date < timezone.localdate():
            return self.Status.LATE
        if self.amount_paid > 0:
            return self.Status.PARTIAL
        return self.Status.TO_COLLECT

    @property
    def status_label(self):
        return self.Status(self.status).label


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="article")
    description = models.CharField("désignation", max_length=200, blank=True)
    quantity = models.DecimalField("quantité", validators=[MinValueValidator(Decimal("0.01"))], **QTY)
    unit_price = models.DecimalField("prix unitaire HT", blank=True, null=True, validators=[MinValueValidator(0)], **MONEY)
    discount_rate = models.DecimalField("remise", default=0, **RATE)
    vat_rate = models.DecimalField("TVA", blank=True, null=True, **RATE)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.description

    @property
    def amount_ht(self):
        return money(self.quantity * (self.unit_price or 0) * (1 - self.discount_rate))

    @property
    def amount_vat(self):
        return money(self.amount_ht * (self.vat_rate or 0))

    @property
    def amount_ttc(self):
        return self.amount_ht + self.amount_vat


class Payment(TenantModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments", verbose_name="facture")
    date = models.DateField("date", default=timezone.localdate)
    amount = models.DecimalField("montant", validators=[MinValueValidator(Decimal("0.01"))], **MONEY)
    method = models.CharField("mode", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference = models.CharField("référence transaction", max_length=80, blank=True)

    class Meta:
        verbose_name = "paiement"
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive")]

    def __str__(self):
        return f"{self.amount} — {self.invoice}"
