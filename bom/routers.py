from bom.viewsets import (
    PartRevisionViewSet,
)
from rest_framework.routers import SimpleRouter

routes = SimpleRouter()

# AUTHENTICATION
# routes.register(r"auth/login", LoginViewSet, basename="auth-login")
# routes.register(r"auth/register", RegistrationViewSet, basename="auth-register")
# routes.register(r"auth/refresh", RefreshViewSet, basename="auth-refresh")

# USER
# routes.register(r"user", UserViewSet, basename="user")

# HSReport
routes.register(r"dashboard", PartRevisionViewSet, basename="dashboard")

urlpatterns = [*routes.urls]
