from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.api_views import (
    ItemListView,
    LogoutView,
    MeView,
    PartBomView,
    PartDetailView,
    PartListView,
    UserView,
)

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="token_blacklist"),
    path("auth/me/", MeView.as_view(), name="auth_me"),
    path("parts/", PartListView.as_view(), name="part-list"),
    path("parts/<int:part_id>/", PartDetailView.as_view(), name="part-detail"),
    path("parts/<int:part_id>/bom/", PartBomView.as_view(), name="part-bom"),
    path("items/", ItemListView.as_view(), name="item-list"),
    path("users/<int:user_id>/", UserView.as_view(), name="user-detail"),
]
