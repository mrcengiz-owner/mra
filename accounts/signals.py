from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, SubDealerProfile

from django.contrib.auth.signals import user_logged_in
from .utils import log_action

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created and instance.role == CustomUser.Roles.SUBDEALER:
        if not hasattr(instance, 'profile'):
            SubDealerProfile.objects.create(user=instance)

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    log_action(request, user, "LOGIN", details={"msg": "User logged in"})
