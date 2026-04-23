from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Q, Subquery
from django.utils.text import smart_split
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from api.serializers import MeSerializer, PartDetailSerializer, PartListRowSerializer
from bom.models import PartRevision, UserMeta

User = get_user_model()


class DashboardPartPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


def get_request_organization(request):
    user_meta = (
        UserMeta.objects.select_related("organization")
        .filter(user=request.user)
        .first()
    )
    if user_meta is None:
        return None
    return user_meta.organization


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Missing refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Token successfully blacklisted."},
                status=status.HTTP_200_OK,
            )
        except TokenError:
            return Response(
                {"detail": "The refresh token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data, status=status.HTTP_200_OK)


class ItemListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = ["item1", "item2", "item3"]
        return Response(items)


class PartListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PartListRowSerializer
    pagination_class = DashboardPartPagination

    def get_queryset(self):
        organization = get_request_organization(self.request)
        if organization is None:
            return PartRevision.objects.none()

        latest_revision_subquery = (
            PartRevision.objects.filter(part_id=OuterRef("part_id"))
            .order_by("-id")
            .values("id")[:1]
        )
        queryset = (
            PartRevision.objects.filter(
                id=Subquery(latest_revision_subquery),
                part__organization=organization,
            )
            .select_related(
                "part",
                "part__number_class",
                "part__primary_manufacturer_part",
                "part__primary_manufacturer_part__manufacturer",
            )
            .order_by(
                "part__number_class__code",
                "part__number_item",
                "part__number_variation",
            )
        )

        part_class_id = self.request.GET.get("part_class_id")
        if part_class_id and part_class_id.isdigit():
            queryset = queryset.filter(part__number_class_id=int(part_class_id))

        product = self.request.GET.get("product")
        if product == "1":
            queryset = queryset.filter(material__in=["with_loi", "no_loi"])
        elif product == "0":
            queryset = queryset.filter(material="no_bom")

        query = (self.request.GET.get("q") or "").strip()
        if query:
            search_terms = [term.replace('"', "") for term in smart_split(query)]
            search_filter = Q()
            for term in search_terms:
                search_filter |= Q(searchable_synopsis__icontains=term)
                search_filter |= Q(part__number_item__icontains=term)
                search_filter |= Q(part__number_variation__icontains=term)
                search_filter |= Q(part__number_class__code__icontains=term)
                search_filter |= Q(
                    part__primary_manufacturer_part__manufacturer_part_number__icontains=term
                )
                search_filter |= Q(
                    part__primary_manufacturer_part__manufacturer__name__icontains=term
                )

            queryset = queryset.filter(search_filter)

        return queryset


class PartDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, part_id):
        organization = get_request_organization(request)
        if organization is None:
            return Response(
                {"detail": "No organization found for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        base_query = PartRevision.objects.filter(
            part_id=part_id,
            part__organization=organization,
        ).select_related(
            "part",
            "part__number_class",
            "part__primary_manufacturer_part",
            "part__primary_manufacturer_part__manufacturer",
        )

        revision_id = request.GET.get("revision_id")
        if revision_id and revision_id.isdigit():
            part_revision = base_query.filter(id=int(revision_id)).first()
        else:
            part_revision = base_query.order_by("-id").first()

        if part_revision is None:
            return Response(
                {"detail": "Part not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            PartDetailSerializer(part_revision).data, status=status.HTTP_200_OK
        )


class PartBomView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _serialize_bom_item(item):
        seller_part = item.seller_part
        return {
            "bom_id": item.bom_id,
            "parent_id": getattr(item, "parent_id", None),
            "indent_level": getattr(item, "indent_level", None),
            "part_id": item.part.pk,
            "part_revision_id": item.part_revision.pk,
            "part_number": item.part.full_part_number(),
            "revision": item.part_revision.revision,
            "description": item.part_revision.description,
            "references": item.references,
            "quantity": item.quantity,
            "extended_quantity": item.extended_quantity,
            "total_extended_quantity": item.total_extended_quantity,
            "do_not_load": item.do_not_load,
            "seller": {
                "id": seller_part.pk if seller_part is not None else None,
                "name": seller_part.seller.name if seller_part is not None else "",
                "seller_part_number": (
                    seller_part.seller_part_number if seller_part is not None else ""
                ),
            },
        }

    def get(self, request, part_id):
        organization = get_request_organization(request)
        if organization is None:
            return Response(
                {"detail": "No organization found for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        base_query = PartRevision.objects.filter(
            part_id=part_id,
            part__organization=organization,
        ).select_related("part", "part__number_class")

        revision_id = request.GET.get("revision_id")
        if revision_id and revision_id.isdigit():
            part_revision = base_query.filter(id=int(revision_id)).first()
        else:
            part_revision = base_query.order_by("-id").first()

        if part_revision is None:
            return Response(
                {"detail": "Part not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        view_mode = (request.GET.get("view") or "indented").lower()
        if view_mode not in ["indented", "flat"]:
            return Response(
                {"detail": "Invalid view. Supported values: indented, flat."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quantity_param = request.GET.get("quantity", "100")
        if not quantity_param.isdigit() or int(quantity_param) < 1:
            return Response(
                {"detail": "Quantity must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quantity = int(quantity_param)
        if view_mode == "flat":
            bom = part_revision.flat(top_level_quantity=quantity)
        else:
            bom = part_revision.indented(
                top_level_quantity=quantity,
                is_weighted_bom=False,
            )

        bom_items = bom.parts.values() if hasattr(bom.parts, "values") else bom.parts
        items = [self._serialize_bom_item(item) for item in bom_items]

        return Response(
            {
                "part_id": part_revision.part.pk,
                "part_revision_id": part_revision.pk,
                "part_number": part_revision.part.full_part_number(),
                "view": view_mode,
                "quantity": quantity,
                "summary": {
                    "unit_cost": str(bom.unit_cost),
                    "missing_item_costs": bom.missing_item_costs,
                    "nre_cost": str(bom.nre_cost),
                    "out_of_pocket_cost": str(bom.out_of_pocket_cost),
                },
                "items": items,
            },
            status=status.HTTP_200_OK,
        )


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if request.user.id != user_id and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to view this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            user = User.objects.get(id=user_id)
            user_info = {
                "id": user.pk,
                "email": user.email,
                "name": user.get_full_name() or user.username,
            }
            return Response(user_info, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
