import asyncio
import json
import logging
import time
from time import sleep

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework import filters, viewsets

from .serializers import UserSerializer

logger = logging.getLogger(__name__)

User = get_user_model()

# Demo pause between streamed users, to make the streaming visible in curl.
# asyncio.sleep, not time.sleep: a blocking sleep would stall the whole event loop.
STREAM_DELAY = 0.1


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile").order_by("id")
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


# Read-only, so CSRF protection adds nothing; exempting it lets non-GET requests
# reach require_GET and get 405 rather than a CSRF 403.
@csrf_exempt
@require_GET
async def stream_users(request):
    """Stream all users as NDJSON: one JSON object per line, sent as it is read.

    A plain async Django view rather than a DRF one, because DRF views are sync.
    Supports the same ``?city=`` filter as the user list. ``select_related`` matters:
    the serializer must not query the database from async code.
    """
    queryset = User.objects.select_related("profile").order_by("id")
    city = request.GET.get("city")
    if city:
        queryset = queryset.filter(profile__city__iexact=city)
    logger.info("stream: request received, city=%r", city)

    async def lines():
        # The body runs only when the server starts reading the response,
        # i.e. after stream_users has already returned.
        logger.info("stream: generator started, sending users")
        started = time.monotonic()
        sent = 0
        try:
            # Async iteration fetches rows in chunks instead of loading them all first.
            async for user in queryset:
                logger.info("stream: read user id=%s from the database", user.pk)
                data = UserSerializer(user).data
                yield json.dumps(data, cls=DjangoJSONEncoder) + "\n"
                # Resumes once the server has taken the chunk and asks for the next one.
                sent += 1
                logger.info("stream: sent user id=%s, sleeping %ss", user.pk, STREAM_DELAY)
                await asyncio.sleep(STREAM_DELAY)
        except asyncio.CancelledError:
            # Django cancels the stream when the client disconnects.
            logger.info(
                "stream: client disconnected after %d users, %.2fs",
                sent, time.monotonic() - started,
            )
            raise
        logger.info("stream: finished, %d users in %.2fs", sent, time.monotonic() - started)

    response = StreamingHttpResponse(lines(), content_type="application/x-ndjson")
    # Nothing has been sent yet: the view only hands the generator to the server.
    logger.info("stream: view returned the response, streaming starts now")
    return response
