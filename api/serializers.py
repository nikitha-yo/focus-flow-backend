from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organisation, Task, FocusSession, MoodLog, Streak

User = get_user_model()

class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = '__all__'

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    org_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id','username','email','password','role','org_id']

    def create(self, validated_data):
        org_id = validated_data.pop('org_id', None)
        password = validated_data.pop('password')
        org = None
        if org_id:
            try:
                org = Organisation.objects.get(id=org_id)
            except Organisation.DoesNotExist:
                pass
        user = User(**validated_data, org=org)
        user.set_password(password)
        user.save()
        Streak.objects.create(user=user)
        return user

class UserSerializer(serializers.ModelSerializer):
    org = OrganisationSerializer(read_only=True)
    class Meta:
        model = User
        fields = ['id','username','email','role','org','created_at']

class OrgMemberCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(choices=[('manager', 'Manager'), ('member', 'Member')], default='member')

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

class TaskSerializer(serializers.ModelSerializer):
    assigned_by_name = serializers.SerializerMethodField()
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['user','created_at']

    def get_assigned_by_name(self, obj):
        return obj.assigned_by.username if obj.assigned_by else None

class FocusSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FocusSession
        fields = '__all__'
        read_only_fields = ['user','start_time']

class MoodLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodLog
        fields = '__all__'
        read_only_fields = ['user','logged_at']

class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = '__all__'
