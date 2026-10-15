from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import OrgDeleteMixin, OrgScopedMixin

from .forms import ProductForm, StockMovementForm
from .models import Product, StockMovement


class ProductList(OrgScopedMixin, ListView):
    model = Product
    template_name = "inventory/product_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().with_stock().order_by("name")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(category__icontains=q))
        return qs


class ProductCreate(OrgScopedMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "core/form.html"
    success_url = reverse_lazy("product_list")
    success_message = "Produit enregistré."
    extra_context = {"title": "Nouveau produit"}


class ProductUpdate(OrgScopedMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "core/form.html"
    success_url = reverse_lazy("product_list")
    success_message = "Produit modifié."
    extra_context = {"title": "Modifier le produit"}


class ProductDelete(OrgDeleteMixin, DeleteView):
    model = Product
    success_url = reverse_lazy("product_list")

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        from django.shortcuts import redirect

        product = self.get_object()
        if product.movements.exists():
            messages.error(request, "Ce produit a des mouvements : désactivez-le plutôt que de le supprimer.")
            return redirect("product_list")
        return super().post(request, *args, **kwargs)


class MovementList(OrgScopedMixin, ListView):
    model = StockMovement
    template_name = "inventory/movement_list.html"
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("product")


class MovementCreate(OrgScopedMixin, CreateView):
    model = StockMovement
    form_class = StockMovementForm
    template_name = "core/form.html"
    success_url = reverse_lazy("movement_list")
    success_message = "Mouvement enregistré."
    extra_context = {"title": "Nouveau mouvement de stock"}


class MovementDelete(OrgDeleteMixin, DeleteView):
    model = StockMovement
    success_url = reverse_lazy("movement_list")

    def get_queryset(self):
        # Movements created by a cash sale are removed by deleting the sale.
        return super().get_queryset().filter(sale__isnull=True)
