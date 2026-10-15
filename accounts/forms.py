from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import Membership, Organization

User = get_user_model()


class OrgFormMixin:
    """Forms receive the current organization so choice fields only list its own records."""

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            qs = getattr(field, "queryset", None)
            if qs is not None and hasattr(qs.model, "organization") and organization is not None:
                field.queryset = qs.filter(organization=organization)


class SignupForm(UserCreationForm):
    organization_name = forms.CharField(label="Nom de votre entreprise", max_length=150)
    phone = forms.CharField(label="Téléphone / WhatsApp", max_length=40, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        labels = {"username": "Identifiant", "email": "E-mail (facultatif)"}

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        org = Organization.objects.create(name=self.cleaned_data["organization_name"], phone=self.cleaned_data["phone"])
        Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        return user


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        exclude = ("invoice_seq", "created_at")
        widgets = {"default_vat_rate": forms.NumberInput(attrs={"step": "0.01"})}


class StaffCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)
        labels = {"username": "Identifiant de l'employé"}

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        Membership.objects.create(user=user, organization=self.organization, role=Membership.Role.STAFF)
        return user
