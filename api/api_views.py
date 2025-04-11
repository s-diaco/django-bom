from time import sleep
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework import status
from django.contrib.auth.models import User


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
        sleep(2)  # Simulate a delay
        items = ["item1", "item2", "item3"]
        return Response(items)


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            # Query the user from the database
            user = User.objects.get(id=user_id)
            user_info = {
                "email": user.email,
                "name": user.get_full_name() or user.username,
            }
            return Response(user_info, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            # Handle the case where the user does not exist
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
