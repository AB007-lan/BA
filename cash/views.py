from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import OrgDeleteMixin, OrgScopedMixin

from .forms import CashClosingForm, CashMovementForm, ExpenseForm, SaleForm
from .models import CashClosing, CashMovement, Expense, Sale


def crud(model, form_class, list_url, label, list_template):
    """Build the list / create / update / delete views shared by the cash records."""

    class List(OrgScopedMixin, ListView):
        paginate_by = 50
        template_name = list_template

    class Create(OrgScopedMixin, CreateView):
        template_name = "core/form.html"
        success_message = f"{label} enregistré(e)."
        extra_context = {"title": f"{label} — nouveau"}

    class Update(OrgScopedMixin, UpdateView):
        template_name = "core/form.html"
        success_message = f"{label} modifié(e)."
        extra_context = {"title": f"{label} — modifier"}

    class Delete(OrgDeleteMixin, DeleteView):
        pass

    for view in (List, Create, Update, Delete):
        view.model = model
    for view in (Create, Update):
        view.form_class = form_class
    for view in (Create, Update, Delete):
        view.success_url = reverse_lazy(list_url)
    return List, Create, Update, Delete


SaleList, SaleCreate, SaleUpdate, SaleDelete = crud(Sale, SaleForm, "sale_list", "Vente", "cash/sale_list.html")
ExpenseList, ExpenseCreate, ExpenseUpdate, ExpenseDelete = crud(
    Expense, ExpenseForm, "expense_list", "Dépense", "cash/expense_list.html"
)
MovementList, MovementCreate, MovementUpdate, MovementDelete = crud(
    CashMovement, CashMovementForm, "cashmovement_list", "Mouvement d'espèces", "cash/cashmovement_list.html"
)
_ClosingList, ClosingCreate, ClosingUpdate, ClosingDelete = crud(
    CashClosing, CashClosingForm, "closing_list", "Clôture", "cash/closing_list.html"
)


class ClosingList(_ClosingList):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rows"] = [(closing, closing.day_figures()) for closing in ctx["object_list"]]
        return ctx
