from django import forms

from accounts.forms import OrgFormMixin

from .models import CashClosing, CashMovement, Expense, Sale

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class SaleForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("date", "ticket", "seller", "product", "description", "quantity", "unit_price", "discount_rate", "method")
        widgets = {"date": DATE, "discount_rate": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0,05 = 5 %"})}
        help_texts = {"unit_price": "Vide = prix du catalogue.", "product": "Vide = vente libre (pas de stock)."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = self.fields["product"].queryset.filter(is_active=True)

    def clean(self):
        data = super().clean()
        if not data.get("product"):
            if not data.get("description"):
                self.add_error("description", "Désignation obligatoire pour une vente sans produit.")
            if data.get("unit_price") is None:
                self.add_error("unit_price", "Prix obligatoire pour une vente sans produit.")
        return data


class ExpenseForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("date", "category", "label", "amount", "method", "receipt_ref")
        widgets = {"date": DATE}


class CashMovementForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = CashMovement
        fields = ("date", "kind", "amount", "note")
        widgets = {"date": DATE}


class CashClosingForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = CashClosing
        fields = ("date", "counted_cash", "comment")
        widgets = {"date": DATE}

    def clean_date(self):
        day = self.cleaned_data["date"]
        clash = CashClosing.objects.filter(organization=self.organization, date=day).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Une clôture existe déjà pour ce jour.")
        return day
