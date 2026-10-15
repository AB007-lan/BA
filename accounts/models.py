from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F

MONEY = {"max_digits": 14, "decimal_places": 2}


class PaymentMethod(models.TextChoices):
    CASH = "ESPECES", "Espèces"
    BANKILY = "BANKILY", "Bankily"
    MASRVI = "MASRVI", "Masrvi"
    SEDAD = "SEDAD", "Sedad"
    WAVE = "WAVE", "Wave"
    ORANGE_MONEY = "ORANGE_MONEY", "Orange Money"
    TRANSFER = "VIREMENT", "Virement"
    CARD = "CARTE", "Carte"
    CHEQUE = "CHEQUE", "Chèque"


class Organization(models.Model):
    name = models.CharField("nom de l'entreprise", max_length=150)
    activity = models.CharField("activité", max_length=150, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    phone = models.CharField("téléphone", max_length=40, blank=True)
    email = models.EmailField("e-mail", blank=True)
    nif = models.CharField("NIF", max_length=40, blank=True)
    rc = models.CharField("registre du commerce", max_length=40, blank=True)
    bankily = models.CharField("numéro Bankily", max_length=40, blank=True)
    masrvi = models.CharField("numéro Masrvi / Sedad", max_length=40, blank=True)
    bank_details = models.CharField("banque / RIB", max_length=120, blank=True)
    currency = models.CharField("devise", max_length=8, default="MRU")
    default_vat_rate = models.DecimalField(
        "taux de TVA par défaut",
        max_digits=5,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="0 si non assujetti. Mauritanie : 0,16 (à confirmer avec votre comptable).",
    )
    payment_terms_days = models.PositiveIntegerField("délai de paiement (jours)", default=30)
    invoice_prefix = models.CharField("préfixe des factures", max_length=20, default="FAC-")
    invoice_footer = models.CharField("mention en bas de facture", max_length=255, blank=True)
    opening_cash = models.DecimalField("fond de caisse de départ", default=0, **MONEY)
    invoice_seq = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "entreprise"

    def __str__(self):
        return self.name

    def next_invoice_number(self, year):
        """Allocate the next invoice number atomically (safe under concurrent requests)."""
        with transaction.atomic():
            Organization.objects.filter(pk=self.pk).update(invoice_seq=F("invoice_seq") + 1)
            seq = Organization.objects.only("invoice_seq").get(pk=self.pk).invoice_seq
        return f"{self.invoice_prefix}{year}-{seq:04d}"


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Gérant"
        STAFF = "staff", "Employé"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    def __str__(self):
        return f"{self.user} @ {self.organization}"


class TenantModel(models.Model):
    """Base for every business record: each row belongs to exactly one organization."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="+", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
