import logging

from django.contrib.auth import get_user_model
from rest_framework import filters, viewsets

from .serializers import UserSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile").order_by("id")
    logger.info("UserViewSet initialized")
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "first_name", "last_name", "profile__workplace"]

    def get_queryset(self):
        queryset = super().get_queryset()
        city = self.request.query_params.get("city")
        if self.action == "list" and city:
            queryset = queryset.filter(profile__city__iexact=city)
        return queryset

    def perform_create(self, serializer):
        user = serializer.save()
        logger.info("Created user id=%s username=%r", user.pk, user.username)

    def perform_update(self, serializer):
        user = serializer.save()
        logger.info("Updated user id=%s username=%r", user.pk, user.username)

    def perform_destroy(self, instance):
        # Django clears instance.pk on delete, so capture the values first.
        user_id, username = instance.pk, instance.username
        instance.delete()
        logger.info("Deleted user id=%s username=%r", user_id, username)
