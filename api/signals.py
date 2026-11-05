from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, raw, **kwargs):
    """Create a Profile for every new User.

    Skipped for raw saves (loaddata), where fixtures supply their own profiles.
    """
    if created and not raw:
        Profile.objects.create(user=instance)
