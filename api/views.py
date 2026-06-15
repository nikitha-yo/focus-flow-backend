from rest_framework import viewsets, status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from datetime import date
from .models import Organisation, Task, FocusSession, MoodLog, Streak, Document, Email, Meeting
from .serializers import *

User = get_user_model()

MOOD_RECOMMENDATIONS = {
    'energized': 'Great energy! Tackle your hardest tasks now. Try deep work sessions of 50 mins.',
    'focused': 'You are in the zone! Use Pomodoro 25-min sprints to maximize output.',
    'tired': 'Take it easy. Light tasks only. Consider a 10-min power nap before starting.',
    'stressed': 'Start with a 5-min breathing exercise. Then tackle one small task at a time.',
    'happy': 'Use this positive mood for creative tasks or tasks you have been avoiding!',
}

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    ser = UserRegisterSerializer(data=request.data)
    if ser.is_valid():
        user = ser.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)
    return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get('email')
    password = request.data.get('password')
    try:
        user = User.objects.get(email=email)
        if user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })
        return Response({'error': 'Invalid credentials'}, status=400)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

@api_view(['GET'])
def me(request):
    return Response(UserSerializer(request.user).data)

@api_view(['GET','POST'])
@permission_classes([AllowAny])
def organisations(request):
    if request.method == 'GET':
        orgs = Organisation.objects.all()
        return Response(OrganisationSerializer(orgs, many=True).data)
    ser = OrganisationSerializer(data=request.data)
    if ser.is_valid():
        ser.save()
        return Response(ser.data, status=201)
    return Response(ser.errors, status=400)

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin','manager'] and user.org:
            return Task.objects.filter(org=user.org)
        return Task.objects.filter(user=user)

    def perform_create(self, serializer):
        org = self.request.user.org if self.request.user.org else None
        serializer.save(user=self.request.user, org=org)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status == 'completed' and not instance.completed_at:
            instance.completed_at = timezone.now()
            instance.save()
            # update streak
            try:
                streak = instance.user.streak
                streak.total_tasks_completed += 1
                today = date.today()
                if streak.last_active == today:
                    pass
                elif streak.last_active and (today - streak.last_active).days == 1:
                    streak.current_streak += 1
                    streak.longest_streak = max(streak.current_streak, streak.longest_streak)
                else:
                    streak.current_streak = 1
                streak.last_active = today
                streak.save()
            except:
                pass

class FocusSessionViewSet(viewsets.ModelViewSet):
    serializer_class = FocusSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FocusSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.completed:
            try:
                streak = instance.user.streak
                streak.total_sessions += 1
                streak.save()
            except:
                pass

class MoodLogViewSet(viewsets.ModelViewSet):
    serializer_class = MoodLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MoodLog.objects.filter(user=self.request.user).order_by('-logged_at')

    def perform_create(self, serializer):
        mood = serializer.validated_data.get('mood','focused')
        rec = MOOD_RECOMMENDATIONS.get(mood, '')
        serializer.save(user=self.request.user, recommendation=rec)

@api_view(['GET'])
def dashboard_stats(request):
    user = request.user
    tasks = Task.objects.filter(user=user)
    total = tasks.count()
    completed = tasks.filter(status='completed').count()
    pending = tasks.filter(status='pending').count()
    sessions = FocusSession.objects.filter(user=user)
    total_focus_mins = sum(s.duration_mins for s in sessions.filter(completed=True))
    try:
        streak = user.streak
        streak_data = StreakSerializer(streak).data
    except:
        streak_data = {'current_streak':0,'longest_streak':0,'total_sessions':0,'total_tasks_completed':0}
    
    last_mood = MoodLog.objects.filter(user=user).order_by('-logged_at').first()
    
    # org stats for admin/manager
    org_data = {}
    if user.role in ['admin','manager'] and user.org:
        org_tasks = Task.objects.filter(org=user.org)
        members = User.objects.filter(org=user.org)
        org_data = {
            'total_members': members.count(),
            'org_tasks_total': org_tasks.count(),
            'org_tasks_completed': org_tasks.filter(status='completed').count(),
        }

    return Response({
        'tasks': {'total':total,'completed':completed,'pending':pending,'completion_rate': round(completed/total*100 if total else 0,1)},
        'focus': {'total_sessions': sessions.count(), 'total_focus_mins': total_focus_mins},
        'streak': streak_data,
        'last_mood': MoodLogSerializer(last_mood).data if last_mood else None,
        'org': org_data,
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def org_members(request):
    if not request.user.org:
        return Response({'error':'Not part of an organisation'}, status=400)

    if request.method == 'GET':
        members = User.objects.filter(org=request.user.org)
        return Response(UserSerializer(members, many=True).data)

    if request.user.role not in ['admin', 'manager']:
        return Response({'error': 'Only admins and managers can add team members'}, status=403)

    serializer = OrgMemberCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    data = serializer.validated_data
    if User.objects.filter(email=data['email']).exists():
        return Response({'error': 'Email already exists'}, status=400)
    if User.objects.filter(username=data['username']).exists():
        return Response({'error': 'Username already exists'}, status=400)

    new_member = User(
        username=data['username'],
        email=data['email'],
        role=data['role'],
        org=request.user.org,
    )
    new_member.set_password(data['password'])
    new_member.save()
    Streak.objects.create(user=new_member)

    return Response(UserSerializer(new_member).data, status=201)


class DocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'org_id', None):
            return Document.objects.none()
        return Document.objects.filter(uploaded_by__org=user.org).select_related('uploaded_by').order_by('-uploaded_at')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class EmailListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmailSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'org_id', None):
            return Email.objects.none()
        return Email.objects.filter(sender=user).prefetch_related('to', 'cc', 'attachments').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class MeetingListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeetingSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'org_id', None):
            return Meeting.objects.none()
        return Meeting.objects.filter(
            Q(created_by=user) | Q(participants=user)
        ).distinct().select_related('created_by').prefetch_related('participants').order_by('-scheduled_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
