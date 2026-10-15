from django import forms
from django.forms import inlineformset_factory

from accounts.forms import OrgFormMixin

from .models import Customer, Invoice, InvoiceLine, Payment

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class CustomerForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "contact", "phone", "address", "nif", "payment_terms_days")


class InvoiceForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ("date", "customer", "due_date", "subject")
        widgets = {"date": DATE, "due_date": DATE}


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ("product", "description", "quantity", "unit_price", "discount_rate", "vat_rate")
        widgets = {
            "discount_rate": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0,10 = 10 %"}),
            "vat_rate": forms.NumberInput(attrs={"step": "0.01", "placeholder": "défaut"}),
        }

    def clean(self):
        data = super().clean()
        product = data.get("product")
        if not product and not data.get("description"):
            raise forms.ValidationError("Choisissez un article ou saisissez une désignation.")
        if not product and data.get("unit_price") is None:
            raise forms.ValidationError("Indiquez un prix pour une ligne sans article.")
        return data


class BaseLineFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.fields["product"].queryset = form.fields["product"].queryset.filter(
                organization=organization, is_active=True
            )

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        kept = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if not kept:
            raise forms.ValidationError("Une facture doit contenir au moins une ligne.")

    def save_line_defaults(self, invoice):
        """Fill blank price, label and VAT from the product and the organization defaults."""
        org = invoice.organization
        for line in invoice.lines.all():
            changed = False
            if line.product:
                if line.unit_price is None:
                    line.unit_price, changed = line.product.sale_price, True
                if not line.description:
                    line.description, changed = line.product.name, True
            if line.vat_rate is None:
                line.vat_rate, changed = org.default_vat_rate, True
            if changed:
                line.save()


LineFormSet = inlineformset_factory(
    Invoice, InvoiceLine, form=InvoiceLineForm, formset=BaseLineFormSet, extra=5, can_delete=True, max_num=50
)


class PaymentForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("invoice", "date", "amount", "method", "reference")
        widgets = {"date": DATE}

    def clean(self):
        data = super().clean()
        invoice, amount = data.get("invoice"), data.get("amount")
        if invoice and amount:
            remaining = invoice.balance + (self.instance.amount if self.instance.pk else 0)
            if amount > remaining:
                raise forms.ValidationError(f"Le montant dépasse le reste à payer ({remaining}).")
        return data
