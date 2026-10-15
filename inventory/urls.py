from django.urls import path

from . import views

urlpatterns = [
    path("produits/", views.ProductList.as_view(), name="product_list"),
    path("produits/nouveau/", views.ProductCreate.as_view(), name="product_create"),
    path("produits/<int:pk>/", views.ProductUpdate.as_view(), name="product_update"),
    path("produits/<int:pk>/supprimer/", views.ProductDelete.as_view(), name="product_delete"),
    path("mouvements/", views.MovementList.as_view(), name="movement_list"),
    path("mouvements/nouveau/", views.MovementCreate.as_view(), name="movement_create"),
    path("mouvements/<int:pk>/supprimer/", views.MovementDelete.as_view(), name="movement_delete"),
]
