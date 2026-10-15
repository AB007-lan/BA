from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from accounts.models import MONEY, PaymentMethod, TenantModel
from billing.models import Payment, money
from inventory.models import QTY, Product, StockMovement


def _sum(qs, field="amount"):
    return qs.aggregate(s=Sum(field))["s"] or Decimal("0")


class Sale(TenantModel):
    date = models.DateField("date", default=timezone.localdate)
    ticket = models.CharField("n° ticket", max_length=30, blank=True)
    seller = models.CharField("vendeur", max_length=60, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, verbose_name="produit")
    description = models.CharField("désignation", max_length=200, blank=True)
    quantity = models.DecimalField("quantité", validators=[MinValueValidator(Decimal("0.01"))], **QTY)
    unit_price = models.DecimalField("prix unitaire", blank=True, null=True, validators=[MinValueValidator(0)], **MONEY)
    discount_rate = models.DecimalField(
        "remise", default=0, max_digits=5, decimal_places=4, validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    method = models.CharField("mode de paiement", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    amount = models.DecimalField("montant", default=0, editable=False, **MONEY)

    class Meta:
        verbose_name = "vente"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["organization", "date"])]

    def __str__(self):
        return f"{self.date} {self.description} {self.amount}"

    def save(self, *args, **kwargs):
        if self.product:
            if self.unit_price is None:
                self.unit_price = self.product.sale_price
            if not self.description:
                self.description = self.product.name
        self.amount = money(self.quantity * (self.unit_price or 0) * (1 - self.discount_rate))
        with transaction.atomic():
            super().save(*args, **kwargs)
            self._sync_stock()

    def _sync_stock(self):
        """A sale of a catalogue product removes it from stock; editing the sale keeps the movement in step."""
        movement = StockMovement.objects.filter(sale=self).first()
        if not self.product:
            if movement:
                movement.delete()
            return
        movement = movement or StockMovement(organization=self.organization, sale=self, kind=StockMovement.Kind.OUT)
        movement.product, movement.date, movement.quantity = self.product, self.date, self.quantity
        movement.unit_price, movement.reference = self.unit_price, f"Vente {self.ticket}".strip()
        movement.note = "Vente caisse"
        movement.save()


class Expense(TenantModel):
    class Category(models.TextChoices):
        GOODS = "achats", "Achats marchandises"
        TRANSPORT = "transport", "Transport"
        SALARIES = "salaires", "Salaires"
        RENT = "loyer", "Loyer"
        UTILITIES = "energie", "Électricité / eau"
        TELECOM = "telecom", "Téléphone / internet"
        MAINTENANCE = "entretien", "Entretien"
        TAXES = "taxes", "Taxes"
        OTHER = "divers", "Divers"

    date = models.DateField("date", default=timezone.localdate)
    category = models.CharField("catégorie", max_length=20, choices=Category.choices, default=Category.OTHER)
    label = models.CharField("libellé", max_length=200)
    amount = models.DecimalField("montant", validators=[MinValueValidator(Decimal("0.01"))], **MONEY)
    method = models.CharField("mode de paiement", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    receipt_ref = models.CharField("justificatif", max_length=60, blank=True)

    class Meta:
        verbose_name = "dépense"
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive")]

    def __str__(self):
        return f"{self.date} {self.label}"


class CashMovement(TenantModel):
    class Kind(models.TextChoices):
        DEPOSIT_IN = "apport", "Apport"
        WITHDRAWAL = "retrait", "Retrait gérant"
        BANK = "banque", "Dépôt en banque"

    date = models.DateField("date", default=timezone.localdate)
    kind = models.CharField("type", max_length=10, choices=Kind.choices)
    amount = models.DecimalField("montant", validators=[MinValueValidator(Decimal("0.01"))], **MONEY)
    note = models.CharField("motif", max_length=200, blank=True)

    class Meta:
        verbose_name = "mouvement d'espèces"
        ordering = ["-date", "-id"]

    @property
    def signed_amount(self):
        return self.amount if self.kind == self.Kind.DEPOSIT_IN else -self.amount


class CashClosing(TenantModel):
    date = models.DateField("date", default=timezone.localdate)
    counted_cash = models.DecimalField("espèces comptées", validators=[MinValueValidator(0)], **MONEY)
    comment = models.CharField("commentaire", max_length=200, blank=True)

    class Meta:
        verbose_name = "clôture de caisse"
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["organization", "date"], name="uniq_closing_per_day")]

    def __str__(self):
        return f"Clôture {self.date}"

    @property
    def opening(self):
        previous = (
            CashClosing.objects.filter(organization=self.organization, date__lt=self.date).order_by("-date").first()
        )
        return previous.counted_cash if previous else self.organization.opening_cash

    def day_figures(self):
        org, day, cash = self.organization, self.date, PaymentMethod.CASH
        sales = Sale.objects.filter(organization=org, date=day)
        movements = CashMovement.objects.filter(organization=org, date=day)
        figures = {
            "cash_sales": _sum(sales.filter(method=cash)),
            "other_sales": _sum(sales.exclude(method=cash)),
            "cash_invoice_payments": _sum(Payment.objects.filter(organization=org, date=day, method=cash)),
            "cash_expenses": _sum(Expense.objects.filter(organization=org, date=day, method=cash)),
            "movements": _sum(movements.filter(kind=CashMovement.Kind.DEPOSIT_IN))
            - _sum(movements.exclude(kind=CashMovement.Kind.DEPOSIT_IN)),
        }
        figures["opening"] = self.opening
        figures["theoretical"] = (
            figures["opening"] + figures["cash_sales"] + figures["cash_invoice_payments"]
            - figures["cash_expenses"] + figures["movements"]
        )
        figures["difference"] = self.counted_cash - figures["theoretical"]
        return figures
