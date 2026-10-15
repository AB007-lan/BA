class OrganizationMiddleware:
    """Attach the user's organization to the request (None for anonymous users or users without one)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org = None
        request.is_owner = False
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            membership = getattr(user, "membership", None)
            if membership is not None:
                request.org = membership.organization
                request.is_owner = membership.role == membership.Role.OWNER
        return self.get_response(request)
