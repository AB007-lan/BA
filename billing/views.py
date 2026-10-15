from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import OrgDeleteMixin, OrgScopedMixin

from .forms import CustomerForm, InvoiceForm, LineFormSet, PaymentForm
from .models import Customer, Invoice, Payment


class CustomerList(OrgScopedMixin, ListView):
    model = Customer
    template_name = "billing/customer_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        return qs.filter(name__icontains=q) if q else qs


class CustomerCreate(OrgScopedMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "core/form.html"
    success_url = reverse_lazy("customer_list")
    success_message = "Client enregistré."
    extra_context = {"title": "Nouveau client"}


class CustomerUpdate(OrgScopedMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "core/form.html"
    success_url = reverse_lazy("customer_list")
    success_message = "Client modifié."
    extra_context = {"title": "Modifier le client"}


class CustomerDelete(OrgDeleteMixin, DeleteView):
    model = Customer
    success_url = reverse_lazy("customer_list")

    def post(self, request, *args, **kwargs):
        if self.get_object().invoices.exists():
            messages.error(request, "Ce client a des factures : il ne peut pas être supprimé.")
            return redirect("customer_list")
        return super().post(request, *args, **kwargs)


class InvoiceList(OrgScopedMixin, ListView):
    model = Invoice
    template_name = "billing/invoice_list.html"

    def get_queryset(self):
        return super().get_queryset().select_related("customer").with_paid()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        wanted = self.request.GET.get("statut", "")
        invoices = list(ctx["object_list"])
        if wanted:
            invoices = [i for i in invoices if i.status == wanted]
        ctx.update(invoices=invoices, statuses=Invoice.Status.choices, wanted=wanted)
        return ctx


class InvoiceFormMixin(OrgScopedMixin):
    model = Invoice
    form_class = InvoiceForm
    template_name = "billing/invoice_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "lines" not in ctx:
            ctx["lines"] = LineFormSet(instance=self.object or Invoice(), organization=self.request.org)
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if self.kwargs.get("pk") else None
        form = self.get_form()
        lines = LineFormSet(request.POST, instance=self.object or Invoice(), organization=request.org)
        if form.is_valid() and lines.is_valid():
            with transaction.atomic():
                form.instance.organization = request.org
                invoice = form.save()
                lines.instance = invoice
                lines.save()
                lines.save_line_defaults(invoice)
                invoice.recalculate()
            messages.success(request, f"Facture {invoice.number} enregistrée.")
            return redirect("invoice_detail", pk=invoice.pk)
        return self.render_to_response(self.get_context_data(form=form, lines=lines))


class InvoiceCreate(InvoiceFormMixin, CreateView):
    extra_context = {"title": "Nouvelle facture"}


class InvoiceUpdate(InvoiceFormMixin, UpdateView):
    extra_context = {"title": "Modifier la facture"}


class InvoiceDetail(OrgScopedMixin, DetailView):
    model = Invoice
    template_name = "billing/invoice_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("customer").prefetch_related("lines", "payments")


class InvoiceDelete(OrgDeleteMixin, DeleteView):
    model = Invoice
    success_url = reverse_lazy("invoice_list")

    def post(self, request, *args, **kwargs):
        if self.get_object().payments.exists():
            messages.error(request, "Cette facture a des paiements : établissez un avoir plutôt que de la supprimer.")
            return redirect("invoice_list")
        return super().post(request, *args, **kwargs)


class PaymentList(OrgScopedMixin, ListView):
    model = Payment
    template_name = "billing/payment_list.html"
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("invoice", "invoice__customer")


class PaymentCreate(OrgScopedMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "core/form.html"
    success_message = "Paiement enregistré."
    extra_context = {"title": "Enregistrer un paiement"}

    def get_initial(self):
        initial = super().get_initial()
        invoice = Invoice.objects.filter(organization=self.request.org, pk=self.request.GET.get("facture") or 0).first()
        if invoice:
            initial.update(invoice=invoice, amount=invoice.balance)
        return initial

    def get_success_url(self):
        return reverse("invoice_detail", args=[self.object.invoice_id])


class PaymentDelete(OrgDeleteMixin, DeleteView):
    model = Payment
    success_url = reverse_lazy("payment_list")
