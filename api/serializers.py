from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organisation, Task, FocusSession, MoodLog, Streak, Document, Email, Meeting

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


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)

    def validate(self, attrs):
        if not getattr(self.context['request'].user, 'org_id', None):
            raise serializers.ValidationError('Organisation account required.')
        return attrs

    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'file_url', 'uploaded_by', 'uploaded_by_name', 'uploaded_at', 'file_type']
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at', 'file_type', 'file_url', 'uploaded_by_name']

    def create(self, validated_data):
        f = validated_data['file']
        name = f.name.lower()
        if name.endswith('.pdf'):
            validated_data['file_type'] = 'pdf'
        elif name.endswith('.docx'):
            validated_data['file_type'] = 'docx'
        elif name.endswith('.xlsx'):
            validated_data['file_type'] = 'xlsx'
        if not validated_data.get('title'):
            validated_data['title'] = f.name.rsplit('/')[-1].rsplit('\\')[-1][:255]
        return super().create(validated_data)

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            return obj.file.url
        return None

    def validate_file(self, value):
        name = value.name.lower()
        if name.endswith('.pdf') or name.endswith('.docx') or name.endswith('.xlsx'):
            return value
        raise serializers.ValidationError('Allowed types: .pdf, .docx, .xlsx')


class EmailSerializer(serializers.ModelSerializer):
    to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)
    cc = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True, required=False)
    attachments = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all(), many=True, required=False)

    class Meta:
        model = Email
        fields = ['id', 'sender', 'to', 'cc', 'subject', 'body', 'status', 'attachments', 'created_at']
        read_only_fields = ['id', 'sender', 'created_at']

    def _org(self):
        return self.context['request'].user.org

    def validate_to(self, users):
        if not users:
            return users
        org = self._org()
        if not org:
            raise serializers.ValidationError('Organisation users only.')
        for u in users:
            if u.org_id != org.id:
                raise serializers.ValidationError('All recipients must be in your organisation.')
        return users

    def validate_cc(self, users):
        if not users:
            return users
        org = self._org()
        if not org:
            raise serializers.ValidationError('Organisation users only.')
        for u in users:
            if u.org_id != org.id:
                raise serializers.ValidationError('All CC recipients must be in your organisation.')
        return users

    def validate_attachments(self, docs):
        if not docs:
            return docs
        org = self._org()
        if not org:
            raise serializers.ValidationError('Organisation account required.')
        for d in docs:
            if d.uploaded_by.org_id != org.id:
                raise serializers.ValidationError('Invalid attachment.')
        return docs

    def validate(self, attrs):
        req = self.context['request'].user
        if not getattr(req, 'org_id', None):
            raise serializers.ValidationError('Organisation account required.')
        if attrs.get('status', 'sent') == 'sent' and not attrs.get('to'):
            raise serializers.ValidationError({'to': 'Add at least one recipient to send.'})
        return attrs

    def create(self, validated_data):
        to_users = validated_data.pop('to')
        cc_users = validated_data.pop('cc', [])
        attachments = validated_data.pop('attachments', [])
        email = Email.objects.create(**validated_data)
        email.to.set(to_users)
        email.cc.set(cc_users)
        email.attachments.set(attachments)
        return email


class MeetingSerializer(serializers.ModelSerializer):
    participants = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'platform', 'scheduled_at', 'duration_minutes',
            'participants', 'agenda', 'meeting_link', 'created_by', 'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def validate_participants(self, users):
        oid = self.context['request'].user.org_id
        if not oid:
            raise serializers.ValidationError('Organisation account required.')
        for u in users:
            if u.org_id != oid:
                raise serializers.ValidationError('All participants must be in your organisation.')
        return users

    def create(self, validated_data):
        participant_users = validated_data.pop('participants')
        meeting = Meeting.objects.create(**validated_data)
        meeting.participants.set(participant_users)
        return meeting
