from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomUser

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=CustomUser.Roles.choices, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'email', 'first_name', 'last_name', 'role')

    def validate(self, attrs):
        # Hierarchy Restrictions
        request = self.context.get('request')
        if request and request.user:
            creator = request.user
            new_role = attrs.get('role')

            # 1. Only SuperUser/SuperAdmin can create SuperAdmin
            if new_role == CustomUser.Roles.SUPERADMIN:
                if not (creator.is_superuser or creator.is_superadmin()):
                     raise serializers.ValidationError("You are not authorized to create a SuperAdmin.")
            
            # 2. Admin cannot create SuperAdmin (Covered above)
            # Admins can create Admins and SubDealers.

        return attrs

    def create(self, validated_data):
        # Ensure role is respected
        password = validated_data.pop('password')
        # create_user handles hashing if we use it, but since we popped password...
        # Standard create_user usage:
        user = User(**validated_data) # role is in validated_data
        user.set_password(password)
        user.save()
        return user
