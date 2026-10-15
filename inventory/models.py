from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import MONEY, TenantModel

QTY = {"max_digits": 12, "decimal_places": 2}
ZERO = Value(Decimal("0"), output_field=DecimalField(**QTY))


class ProductQuerySet(models.QuerySet):
    def with_stock(self):
        signed = Case(
            When(movements__kind=StockMovement.Kind.IN, then=F("movements__quantity")),
            When(movements__kind=StockMovement.Kind.OUT, then=-F("movements__quantity")),
            default=ZERO,
            output_field=DecimalField(**QTY),
        )
        return self.annotate(stock=Coalesce(Sum(signed), ZERO))


class Product(TenantModel):
    code = models.CharField("code", max_length=40)
    name = models.CharField("désignation", max_length=150)
    category = models.CharField("catégorie", max_length=80, blank=True)
    unit = models.CharField("unité", max_length=30, blank=True, default="pièce")
    purchase_price = models.DecimalField("prix d'achat", default=0, validators=[MinValueValidator(0)], **MONEY)
    sale_price = models.DecimalField("prix de vente", default=0, validators=[MinValueValidator(0)], **MONEY)
    alert_threshold = models.DecimalField("seuil d'alerte", default=0, validators=[MinValueValidator(0)], **QTY)
    is_active = models.BooleanField("actif", default=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "produit"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uniq_product_code_per_org")]

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def current_stock(self):
        stock = getattr(self, "stock", None)
        if stock is None:
            stock = Product.objects.filter(pk=self.pk).with_stock().values_list("stock", flat=True).first()
        return stock or Decimal("0")

    @property
    def status(self):
        stock = self.current_stock
        if stock <= 0:
            return "rupture"
        if stock <= self.alert_threshold:
            return "a_commander"
        return "ok"


class StockMovement(TenantModel):
    class Kind(models.TextChoices):
        IN = "IN", "Entrée"
        OUT = "OUT", "Sortie"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements", verbose_name="produit")
    date = models.DateField("date", default=timezone.localdate)
    kind = models.CharField("type", max_length=3, choices=Kind.choices)
    quantity = models.DecimalField("quantité", validators=[MinValueValidator(Decimal("0.01"))], **QTY)
    unit_price = models.DecimalField("prix unitaire", null=True, blank=True, validators=[MinValueValidator(0)], **MONEY)
    reference = models.CharField("référence", max_length=60, blank=True)
    note = models.CharField("note", max_length=255, blank=True)
    sale = models.OneToOneField(
        "cash.Sale", null=True, blank=True, on_delete=models.CASCADE, related_name="stock_movement", editable=False
    )

    class Meta:
        verbose_name = "mouvement de stock"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["organization", "date"])]
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="movement_quantity_positive")]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity} {self.product}"
