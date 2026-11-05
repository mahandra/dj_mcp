from django.contrib.auth import get_user_model
from rest_framework import filters, viewsets

from .serializers import UserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile").order_by("id")
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "first_name", "last_name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        city = self.request.query_params.get("city")
        if self.action == "list" and city:
            queryset = queryset.filter(profile__city__iexact=city)
        return queryset
