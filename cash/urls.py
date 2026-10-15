from django.urls import path

from . import views

urlpatterns = []
for prefix, name, (lst, create, update, delete) in (
    ("ventes", "sale", (views.SaleList, views.SaleCreate, views.SaleUpdate, views.SaleDelete)),
    ("depenses", "expense", (views.ExpenseList, views.ExpenseCreate, views.ExpenseUpdate, views.ExpenseDelete)),
    ("especes", "cashmovement", (views.MovementList, views.MovementCreate, views.MovementUpdate, views.MovementDelete)),
    ("clotures", "closing", (views.ClosingList, views.ClosingCreate, views.ClosingUpdate, views.ClosingDelete)),
):
    urlpatterns += [
        path(f"{prefix}/", lst.as_view(), name=f"{name}_list"),
        path(f"{prefix}/nouveau/", create.as_view(), name=f"{name}_create"),
        path(f"{prefix}/<int:pk>/", update.as_view(), name=f"{name}_update"),
        path(f"{prefix}/<int:pk>/supprimer/", delete.as_view(), name=f"{name}_delete"),
    ]
