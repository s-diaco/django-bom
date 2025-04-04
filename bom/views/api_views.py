from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken


class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Token successfully blacklisted"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class ItemListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = ["item1", "item2", "item3"]
        return Response(items)
