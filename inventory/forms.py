from decimal import Decimal

from django import forms

from accounts.forms import OrgFormMixin

from .models import Product, StockMovement


class ProductForm(OrgFormMixin, forms.ModelForm):
    initial_stock = forms.DecimalField(
        label="Stock de départ", required=False, min_value=0, decimal_places=2,
        help_text="Crée automatiquement une entrée de stock « Stock initial ».",
    )

    class Meta:
        model = Product
        fields = ("code", "name", "category", "unit", "purchase_price", "sale_price", "alert_threshold", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields["initial_stock"]

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        clash = Product.objects.filter(organization=self.organization, code=code).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Ce code est déjà utilisé par un autre produit.")
        return code

    def save(self, commit=True):
        product = super().save(commit=commit)
        qty = self.cleaned_data.get("initial_stock") or Decimal("0")
        if commit and qty > 0:
            StockMovement.objects.create(
                organization=product.organization, product=product, kind=StockMovement.Kind.IN,
                quantity=qty, unit_price=product.purchase_price, note="Stock initial",
            )
        return product


class StockMovementForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ("date", "product", "kind", "quantity", "unit_price", "reference", "note")
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = self.fields["product"].queryset.filter(is_active=True)
