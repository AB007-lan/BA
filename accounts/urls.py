from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("inscription/", views.SignupView.as_view(), name="signup"),
    path("connexion/", auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("parametres/", views.OrgSettingsView.as_view(), name="org_settings"),
    path("equipe/", views.TeamView.as_view(), name="team"),
]
