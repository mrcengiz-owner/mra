from rest_framework import generics, permissions
from .serializers import UserCreateSerializer, UserConfigurationSerializer
from django.contrib.auth import get_user_model
from .models import SubDealerProfile, CustomUser
from django.shortcuts import get_object_or_404

User = get_user_model()

class IsSystemAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            request.user.role == CustomUser.Roles.ADMIN
        )

class CreateUserAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [IsSystemAdmin]

class UpdateDealerConfigView(generics.RetrieveUpdateAPIView):
    # RetrieveUpdateAPIView allows GET (to populate modal) and PATCH (to update)
    serializer_class = UserConfigurationSerializer
    permission_classes = [IsSystemAdmin]

    def get_object(self):
        # Allow looking up by User ID passed in URL
        user_id = self.kwargs.get('pk')
        return get_object_or_404(SubDealerProfile, user_id=user_id) 

    def update(self, request, *args, **kwargs):
        print(f"DEBUG: Update Request Data: {request.data}")
        return super().update(request, *args, **kwargs) 
