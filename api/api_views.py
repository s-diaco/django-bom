from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework import status


class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Token successfully blacklisted"}, status=status.HTTP_200_OK
            )
        except TokenError as e:
            # Handle expired or invalid token
            return Response(
                {"error": "The refresh token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Handle other exceptions
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ItemListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = ["item1", "item2", "item3"]
        return Response(items)
