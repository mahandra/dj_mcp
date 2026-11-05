from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    readonly_fields = ("created_at", "updated_at")


admin.site.unregister(get_user_model())


@admin.register(get_user_model())
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

    def get_inline_instances(self, request, obj=None):
        # On the add form the signal creates the Profile when the User is saved,
        # so an inline there would try to insert a second one.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)
