from kr2inco_api.viewsets import (
    HSReportViewSet,
    LoginViewSet,
    RefreshViewSet,
    RegistrationViewSet,
    UserViewSet,
)
from rest_framework.routers import SimpleRouter

routes = SimpleRouter()

# AUTHENTICATION
routes.register(r"auth/login", LoginViewSet, basename="auth-login")
routes.register(r"auth/register", RegistrationViewSet, basename="auth-register")
routes.register(r"auth/refresh", RefreshViewSet, basename="auth-refresh")

# USER
routes.register(r"user", UserViewSet, basename="user")

# HSReport
routes.register(r"hsreport", HSReportViewSet, basename="hsreport")

urlpatterns = [*routes.urls]
