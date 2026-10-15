from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import CreateView, FormView, TemplateView, UpdateView

from billing.models import Invoice, Payment
from cash.models import CashClosing, Expense, Sale
from inventory.models import Product

from .forms import OrganizationForm, SignupForm, StaffCreateForm
from .mixins import OrgRequiredMixin, OwnerRequiredMixin
from .models import Membership, PaymentMethod


def _sum(qs, field="amount"):
    return qs.aggregate(s=Sum(field))["s"] or Decimal("0")


class SignupView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignupForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Bienvenue ! Complétez les paramètres de votre entreprise.")
        return redirect("org_settings")


class DashboardView(OrgRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_period(self):
        today = timezone.localdate()
        start = parse_date(self.request.GET.get("du", "") or "") or today.replace(day=1)
        end = parse_date(self.request.GET.get("au", "") or "") or today
        return start, end

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.org
        start, end = self.get_period()
        period = {"organization": org, "date__gte": start, "date__lte": end}

        sales = Sale.objects.filter(**period)
        payments = Payment.objects.filter(**period)
        expenses = Expense.objects.filter(**period)
        invoices = list(Invoice.objects.filter(organization=org).with_paid())

        cash_sales = _sum(sales)
        collected = _sum(payments)
        spent = _sum(expenses)
        late = [i for i in invoices if i.status == Invoice.Status.LATE]

        products = list(Product.objects.filter(organization=org, is_active=True).with_stock())
        alerts = sorted((p for p in products if p.status != "ok"), key=lambda p: p.stock)

        by_method = []
        for value, label in PaymentMethod.choices:
            amount = _sum(sales.filter(method=value)) + _sum(payments.filter(method=value))
            if amount:
                by_method.append((label, amount))

        last_closing = CashClosing.objects.filter(organization=org).order_by("-date").first()
        ctx.update(
            start=start, end=end,
            cash_sales=cash_sales,
            invoiced=sum((i.total_ttc for i in invoices if start <= i.date <= end), Decimal("0")),
            collected=collected, spent=spent, result=cash_sales + collected - spent,
            receivable=sum((i.balance for i in invoices if i.balance > 0), Decimal("0")),
            late_count=len(late), late_amount=sum((i.balance for i in late), Decimal("0")),
            stock_value=sum((p.stock * p.purchase_price for p in products if p.stock > 0), Decimal("0")),
            alerts=alerts[:10], alert_count=len(alerts),
            by_method=by_method,
            last_closing=last_closing,
            last_closing_figures=last_closing.day_figures() if last_closing else None,
            is_new=not products and not invoices and not sales.exists(),
        )
        return ctx


class OrgSettingsView(OwnerRequiredMixin, OrgRequiredMixin, UpdateView):
    form_class = OrganizationForm
    template_name = "core/form.html"
    success_url = reverse_lazy("dashboard")
    extra_context = {"title": "Paramètres de l'entreprise"}

    def get_object(self, queryset=None):
        return self.request.org

    def form_valid(self, form):
        messages.success(self.request, "Paramètres enregistrés.")
        return super().form_valid(form)


class TeamView(OwnerRequiredMixin, OrgRequiredMixin, CreateView):
    form_class = StaffCreateForm
    template_name = "accounts/team.html"
    success_url = reverse_lazy("team")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "organization": self.request.org}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["members"] = Membership.objects.filter(organization=self.request.org).select_related("user")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Employé ajouté. Communiquez-lui son identifiant et son mot de passe.")
        return super().form_valid(form)
