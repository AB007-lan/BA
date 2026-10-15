from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy


class OrgRequiredMixin(LoginRequiredMixin):
    """Require a logged-in user who belongs to an organization."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.org is None:
            raise PermissionDenied("Aucune entreprise associée à ce compte.")
        return super().dispatch(request, *args, **kwargs)


class OrgScopedMixin(OrgRequiredMixin):
    """Restrict every queryset to the current organization and stamp it on created objects.

    Objects of other organizations are invisible: get_object() raises 404 for them.
    """

    model = None
    success_message = ""

    def get_queryset(self):
        return self.model.objects.filter(organization=self.request.org)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.org
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.org
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response


class OwnerRequiredMixin:
    """Deletion and settings are reserved to the owner."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.is_owner:
            raise PermissionDenied("Action réservée au gérant.")
        return super().dispatch(request, *args, **kwargs)


class OrgDeleteMixin(OwnerRequiredMixin, OrgScopedMixin):
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("dashboard")

    def get_form_kwargs(self):
        # Deletion uses Django's plain confirmation form, which takes no organization.
        return super(OrgScopedMixin, self).get_form_kwargs()

    def form_valid(self, form):
        messages.success(self.request, "Élément supprimé.")
        return super(OrgScopedMixin, self).form_valid(form)
