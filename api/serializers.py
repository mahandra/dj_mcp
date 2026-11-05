from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("birth_date", "city", "workplace")


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "profile")

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop("profile", {})
        user = User(**validated_data)
        # The API does not manage credentials, so API-created users cannot log in.
        user.set_unusable_password()
        user.save()  # The post_save signal creates the Profile.
        self._update_profile(user, profile_data)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        user = super().update(instance, validated_data)
        self._update_profile(user, profile_data)
        return user

    @staticmethod
    def _update_profile(user, profile_data):
        # Goes through user.profile so the cached relation stays current
        # for the response that is serialized next.
        if not profile_data:
            return
        profile = user.profile
        for field, value in profile_data.items():
            setattr(profile, field, value)
        profile.save()
