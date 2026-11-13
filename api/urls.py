from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, stream_users

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    # Before the router: otherwise "stream" is matched as the pk of users/{pk}/.
    path("users/stream/", stream_users, name="user-stream"),
    *router.urls,
]
