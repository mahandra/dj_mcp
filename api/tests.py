import json
from datetime import date
from io import StringIO
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import AsyncClient, SimpleTestCase, TestCase
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

    def test_search_matches_workplace(self):
        alice = make_user("alice")
        alice.profile.workplace = "Bayshore Software"
        alice.profile.save()
        make_user("bob")

        response = self.client.get(self.list_url, {"search": "bayshore"})

        self.assertEqual(
            [user["username"] for user in response.data["results"]], ["alice"]
        )

    def test_delete_removes_user_and_profile(self):
        user = make_user("alice")

        response = self.client.delete(self.detail_url(user))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Profile.objects.filter(user_id=user.pk).exists())


class UserApiLoggingTests(APITestCase):
    def assert_logged(self, logs, message):
        self.assertEqual([record.getMessage() for record in logs.records], [message])

    def test_create_is_logged(self):
        with self.assertLogs("api.views", level="INFO") as logs:
            response = self.client.post(
                reverse("user-list"), {"username": "bob"}, format="json"
            )

        self.assert_logged(
            logs, f"Created user id={response.data['id']} username='bob'"
        )

    def test_update_is_logged(self):
        user = make_user("alice")

        with self.assertLogs("api.views", level="INFO") as logs:
            self.client.patch(
                reverse("user-detail", args=[user.pk]),
                {"first_name": "Alice"},
                format="json",
            )

        self.assert_logged(logs, f"Updated user id={user.pk} username='alice'")

    def test_delete_is_logged(self):
        user = make_user("alice")
        user_id = user.pk

        with self.assertLogs("api.views", level="INFO") as logs:
            self.client.delete(reverse("user-detail", args=[user_id]))

        self.assert_logged(logs, f"Deleted user id={user_id} username='alice'")

    def test_rejected_create_is_not_logged(self):
        make_user("bob")

        with self.assertNoLogs("api.views", level="INFO"):
            response = self.client.post(
                reverse("user-list"), {"username": "bob"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@patch("api.views.STREAM_DELAY", 0)
class UserStreamTests(TestCase):
    url = reverse("user-stream")

    @classmethod
    def setUpTestData(cls):
        make_user("alice", city="Tampa", first_name="Alice")
        make_user("bob", city="Boston")
        make_user("carol", city="tampa")

    async def stream(self, params=None):
        """Request the stream and read it fully; the view's logs are captured, not printed."""
        with self.assertLogs("api.views", level="INFO") as logs:
            response = await self.async_client.get(self.url, params)
            body = b"".join([chunk async for chunk in response.streaming_content])
        lines = [json.loads(line) for line in body.decode().splitlines()]
        return response, lines, [record.getMessage() for record in logs.records]

    async def test_streams_users_as_ndjson(self):
        response, users, _ = await self.stream()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertEqual(response["Content-Type"], "application/x-ndjson")
        self.assertEqual([u["username"] for u in users], ["alice", "bob", "carol"])
        self.assertEqual(users[0]["first_name"], "Alice")
        self.assertEqual(users[0]["profile"]["city"], "Tampa")
        self.assertNotIn("password", users[0])

    async def test_city_filter_is_case_insensitive(self):
        _, users, _ = await self.stream({"city": "TAMPA"})

        self.assertEqual([u["username"] for u in users], ["alice", "carol"])

    async def test_logs_stream_lifecycle(self):
        _, _, messages = await self.stream({"city": "Boston"})

        # The view returns before the generator sends anything.
        self.assertEqual(
            messages,
            [
                "stream: request received, city='Boston'",
                "stream: view returned the response, streaming starts now",
                "stream: generator started, sending users",
                "stream: read user id=2 from the database",
                "stream: sent user id=2, sleeping 0s",
                messages[-1],
            ],
        )
        self.assertRegex(messages[-1], r"^stream: finished, 1 users in \d+\.\d\ds$")

    async def test_rejects_non_get(self):
        # The test client skips CSRF checks by default; the real server does not.
        client = AsyncClient(enforce_csrf_checks=True)
        response = await client.post(self.url)

        self.assertEqual(response.status_code, 405)


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
