from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomUser

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=CustomUser.Roles.choices, required=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'email', 'first_name', 'last_name', 'role')

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user:
            creator = request.user
            new_role = attrs.get('role')

            # Task 1: Hierarchy Logic
            # 1. If Creator is NOT SuperUser, they CANNOT create SUPERADMIN
            if new_role == CustomUser.Roles.SUPERADMIN:
                if not creator.is_superuser:
                    raise serializers.ValidationError("You are not authorized to create a SuperAdmin.")
            
            # Optional: Allow defining defaults if role is missing in attrs?
            # No, model handles it.

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        # Use create_user to handle password hashing and default model fields (like role='sub_dealer')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

from .models import SubDealerProfile

class UserConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDealerProfile
        fields = [
            'net_balance_limit', 'deposit_commission_rate', 'withdraw_commission_rate',
            'can_receive_deposit', 'can_make_withdraw', 'can_edit_amounts', 'is_active_by_system'
        ]
