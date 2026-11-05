from datetime import date
from io import StringIO
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from mcp_server.server import call_api
from rest_framework.test import APITestCase

from .models import Profile

User = get_user_model()


def make_user(username, city="", **fields):
    user = User.objects.create_user(username=username, **fields)
    if city:
        user.profile.city = city
        user.profile.save()
    return user


class UserApiTests(APITestCase):
    list_url = reverse("user-list")

    @staticmethod
    def detail_url(user):
        return reverse("user-detail", args=[user.pk])

    def test_list_is_paginated_to_ten_per_page(self):
        for index in range(12):
            make_user(f"user{index}")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])

    def test_retrieve_returns_user_with_profile(self):
        user = make_user("alice", city="Tampa", first_name="Alice")

        response = self.client.get(self.detail_url(user))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "id": user.pk,
                "username": "alice",
                "first_name": "Alice",
                "last_name": "",
                "email": "",
                "profile": {"birth_date": None, "city": "Tampa", "workplace": ""},
            },
        )

    def test_create_with_profile(self):
        payload = {
            "username": "bob",
            "email": "bob@example.com",
            "profile": {
                "birth_date": "1990-05-01",
                "city": "Tampa",
                "workplace": "Acme",
            },
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["profile"], payload["profile"])
        profile = Profile.objects.get(user__username="bob")
        self.assertEqual(profile.birth_date, date(1990, 5, 1))
        self.assertEqual(profile.city, "Tampa")
        self.assertEqual(profile.workplace, "Acme")
        self.assertFalse(profile.user.has_usable_password())

    def test_create_without_profile_still_creates_one(self):
        response = self.client.post(
            self.list_url, {"username": "bob"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["profile"],
            {"birth_date": None, "city": "", "workplace": ""},
        )

    def test_create_with_invalid_profile_creates_nothing(self):
        response = self.client.post(
            self.list_url,
            {"username": "bob", "profile": {"birth_date": "not-a-date"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("birth_date", response.data["profile"])
        self.assertFalse(User.objects.filter(username="bob").exists())

    def test_patch_updates_only_given_profile_fields(self):
        user = make_user("alice", city="Tampa")
        user.profile.workplace = "Acme"
        user.profile.save()

        response = self.client.patch(
            self.detail_url(user), {"profile": {"city": "Miami"}}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["city"], "Miami")
        self.assertEqual(response.data["profile"]["workplace"], "Acme")
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.city, "Miami")
        self.assertEqual(user.profile.workplace, "Acme")

    def test_put_updates_user_and_profile(self):
        user = make_user("alice", city="Tampa")

        response = self.client.put(
            self.detail_url(user),
            {
                "username": "alice2",
                "first_name": "Alice",
                "profile": {"birth_date": "1991-02-03", "city": "Orlando"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["city"], "Orlando")
        user.refresh_from_db()
        self.assertEqual(user.username, "alice2")
        self.assertEqual(user.first_name, "Alice")
        self.assertEqual(user.profile.birth_date, date(1991, 2, 3))

    def test_city_filter_is_case_insensitive(self):
        make_user("alice", city="Tampa")
        make_user("bob", city="Miami")

        response = self.client.get(self.list_url, {"city": "tampa"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [user["username"] for user in response.data["results"]], ["alice"]
        )

    def test_search_matches_username_and_names(self):
        make_user("alice")
        make_user("bob", first_name="Alicia")
        make_user("carol", last_name="Malice")
        make_user("dave")

        response = self.client.get(self.list_url, {"search": "alic"})

        self.assertEqual(
            [user["username"] for user in response.data["results"]],
            ["alice", "bob", "carol"],
        )

    def test_delete_removes_user_and_profile(self):
        user = make_user("alice")

        response = self.client.delete(self.detail_url(user))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Profile.objects.filter(user_id=user.pk).exists())


class ProfileSignalTests(TestCase):
    def test_profile_is_created_once(self):
        user = User.objects.create_user("alice")
        user.first_name = "Alice"
        user.save()

        self.assertEqual(Profile.objects.filter(user=user).count(), 1)


class SeedUsersTests(TestCase):
    def test_second_run_creates_no_duplicates(self):
        call_command("seed_users", stdout=StringIO())
        call_command("seed_users", stdout=StringIO())

        self.assertEqual(User.objects.count(), 10)
        self.assertEqual(Profile.objects.exclude(city="").count(), 10)


class UserAdminTests(TestCase):
    def test_add_form_saves_without_duplicate_profile(self):
        admin_user = User.objects.create_superuser("admin", password="secret")
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("admin:auth_user_add"),
            {
                "username": "newuser",
                "usable_password": "false",
                "password1": "",
                "password2": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Profile.objects.filter(user__username="newuser").count(), 1)

    def test_change_form_shows_profile_inline(self):
        admin_user = User.objects.create_superuser("admin", password="secret")
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("admin:auth_user_change", args=[admin_user.pk])
        )

        self.assertContains(response, "profile-0-city")


class McpCallApiTests(SimpleTestCase):
    @patch("mcp_server.server.httpx.request")
    def test_request_error_is_returned_as_data(self, request):
        request.side_effect = httpx.ConnectError("Connection refused")

        result = call_api("GET", "/users/1/")

        self.assertEqual(
            result,
            {
                "error": "api_unavailable",
                "detail": "ConnectError: Connection refused",
            },
        )

    @patch("mcp_server.server.httpx.request")
    def test_timeout_detail_keeps_exception_type(self, request):
        request.side_effect = httpx.ReadTimeout("")

        result = call_api("GET", "/users/1/")

        self.assertEqual(result["error"], "api_unavailable")
        self.assertIn("ReadTimeout", result["detail"])
