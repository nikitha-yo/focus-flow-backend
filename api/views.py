from rest_framework import viewsets, status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Organisation, Task, FocusSession, Streak, Document, Email, Meeting,
    Announcement, MoodLog, RecurringTask, RecurringTaskCompletion,
)
from .serializers import *

User = get_user_model()

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
        mood = serializer.validated_data.get('mood', '')
        energy = serializer.validated_data.get('energy_level', 3)
        
        # Generate simple recommendations based on mood and energy
        recommendations = {
            'energized': "You're full of energy! This is a great time for deep focus work. Consider tackling your most challenging task now.",
            'focused': "Your focus is sharp. Perfect time to dive into important work. Set a 25-min Pomodoro and minimize distractions.",
            'happy': "You're in a great mood! Channel this positive energy into collaborative work or creative tasks.",
            'tired': "You're feeling tired. Try a short break, drink some water, or do light tasks. Consider a 5-min power nap if possible.",
            'stressed': "You're stressed. Take a few deep breaths. Try a quick 5-minute meditation or breathing exercise before working.",
        }
        
        recommendation = recommendations.get(mood, f"You're feeling {mood}. Take care of yourself!")
        if energy <= 2:
            recommendation += " Consider taking a break soon."
        elif energy == 5:
            recommendation += " Keep up this momentum!"
        
        serializer.save(user=self.request.user, recommendation=recommendation)

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
    
    # org stats for admin/manager
    org_data = {}
    announcements_data = []
    if user.role in ['admin','manager'] and user.org:
        org_tasks = Task.objects.filter(org=user.org)
        members = User.objects.filter(org=user.org)
        org_data = {
            'total_members': members.count(),
            'org_tasks_total': org_tasks.count(),
            'org_tasks_completed': org_tasks.filter(status='completed').count(),
        }
        # Get latest 3 announcements
        latest_announcements = Announcement.objects.filter(org=user.org).order_by('-created_at')[:3]
        announcements_data = AnnouncementSerializer(latest_announcements, many=True).data
    elif user.org:
        # Members can also see announcements
        latest_announcements = Announcement.objects.filter(org=user.org).order_by('-created_at')[:3]
        announcements_data = AnnouncementSerializer(latest_announcements, many=True).data

    return Response({
        'tasks': {'total':total,'completed':completed,'pending':pending,'completion_rate': round(completed/total*100 if total else 0,1)},
        'focus': {'total_sessions': sessions.count(), 'total_focus_mins': total_focus_mins},
        'streak': streak_data,
        'weekly_task_progress': build_weekly_tracker_data(user, include_tasks=False)['metrics'],
        'org': org_data,
        'announcements': announcements_data,
    })


DEFAULT_RECURRING_TASKS = [
    'Read 10 pages',
    'Exercise',
    'Practice coding',
    'Study for 30 minutes',
    'Meditation',
]


def sunday_for(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def completion_streaks(completed_dates, today):
    completed_dates = {day for day in completed_dates if day <= today}
    current = 0
    cursor = today
    while cursor in completed_dates:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    running = 0
    previous = None
    for completed_day in sorted(completed_dates):
        if previous and completed_day == previous + timedelta(days=1):
            running += 1
        else:
            running = 1
        longest = max(longest, running)
        previous = completed_day
    return current, longest


def build_weekly_tracker_data(user, include_tasks=True):
    today = timezone.localdate()
    week_start = sunday_for(today)
    week_end = week_start + timedelta(days=6)
    trend_start = week_start - timedelta(weeks=3)
    tasks = list(RecurringTask.objects.filter(user=user, is_active=True))
    completions = RecurringTaskCompletion.objects.filter(
        task__user=user,
        completed_date__range=(trend_start, week_end),
    ).select_related('task')
    completion_lookup = {(item.task_id, item.completed_date) for item in completions}

    days = []
    scheduled_total = 0
    completed_total = 0
    productive_dates = set()
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        scheduled = sum(offset in task.scheduled_days for task in tasks)
        completed = sum(
            offset in task.scheduled_days and (task.id, day) in completion_lookup
            for task in tasks
        )
        scheduled_total += scheduled
        completed_total += completed
        if completed:
            productive_dates.add(day)
        days.append({
            'date': day.isoformat(),
            'label': day.strftime('%a'),
            'scheduled': scheduled,
            'completed': completed,
        })

    all_completion_dates = set(
        RecurringTaskCompletion.objects.filter(
            task__user=user,
            completed_date__lte=today,
        ).values_list('completed_date', flat=True)
    )
    current_streak, longest_streak = completion_streaks(all_completion_dates, today)

    trends = []
    for week_offset in range(4):
        trend_week_start = trend_start + timedelta(weeks=week_offset)
        trend_completed = 0
        trend_scheduled = 0
        consistent_days = 0
        for day_offset in range(7):
            day = trend_week_start + timedelta(days=day_offset)
            scheduled = sum(day_offset in task.scheduled_days and task.created_at.date() <= day for task in tasks)
            completed = sum((task.id, day) in completion_lookup for task in tasks)
            trend_scheduled += scheduled
            trend_completed += completed
            if scheduled and completed == scheduled:
                consistent_days += 1
        trends.append({
            'week': trend_week_start.strftime('%b %d'),
            'completed': trend_completed,
            'consistency': round(consistent_days / 7 * 100, 1),
            'completion_rate': round(trend_completed / trend_scheduled * 100, 1) if trend_scheduled else 0,
        })

    data = {
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'today': today.isoformat(),
        'days': days,
        'metrics': {
            'completion_rate': round(completed_total / scheduled_total * 100, 1) if scheduled_total else 0,
            'productive_days': len(productive_dates),
            'current_streak': current_streak,
            'longest_streak': longest_streak,
        },
        'trends': trends,
        'presets': DEFAULT_RECURRING_TASKS,
    }
    if include_tasks:
        data['tasks'] = [
            {
                **RecurringTaskSerializer(task).data,
                'completions': [
                    day.isoformat()
                    for day in (week_start + timedelta(days=offset) for offset in range(7))
                    if (task.id, day) in completion_lookup
                ],
            }
            for task in tasks
        ]
    return data


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def weekly_tracker(request):
    if request.method == 'GET':
        return Response(build_weekly_tracker_data(request.user))

    serializer = RecurringTaskSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(build_weekly_tracker_data(request.user), status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def weekly_tracker_task(request, pk):
    try:
        task = RecurringTask.objects.get(pk=pk, user=request.user)
    except RecurringTask.DoesNotExist:
        return Response({'error': 'Recurring task not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        task.delete()
        return Response(build_weekly_tracker_data(request.user))

    serializer = RecurringTaskSerializer(task, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(build_weekly_tracker_data(request.user))
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def weekly_tracker_toggle(request, pk):
    try:
        task = RecurringTask.objects.get(pk=pk, user=request.user, is_active=True)
    except RecurringTask.DoesNotExist:
        return Response({'error': 'Recurring task not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        completed_date = date.fromisoformat(request.data.get('date', ''))
    except ValueError:
        return Response({'error': 'A valid completion date is required.'}, status=status.HTTP_400_BAD_REQUEST)

    week_start = sunday_for(timezone.localdate())
    if completed_date < week_start or completed_date > week_start + timedelta(days=6):
        return Response({'error': 'Only dates in the current week can be changed.'}, status=status.HTTP_400_BAD_REQUEST)
    day_index = (completed_date - week_start).days
    if day_index not in task.scheduled_days:
        return Response({'error': 'This task is not scheduled for that day.'}, status=status.HTTP_400_BAD_REQUEST)

    completion, created = RecurringTaskCompletion.objects.get_or_create(
        task=task,
        completed_date=completed_date,
    )
    if not created:
        completion.delete()
    return Response(build_weekly_tracker_data(request.user))

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
        meeting = serializer.save(created_by=self.request.user)
        # Automatically create an announcement for the meeting
        if self.request.user.org:
            platform_names = {
                'meet': 'Google Meet',
                'zoom': 'Zoom',
                'teams': 'Microsoft Teams'
            }
            platform_name = platform_names.get(meeting.platform, meeting.platform)
            
            # Format the message with meeting details
            participants_list = ', '.join([p.username for p in meeting.participants.all()])
            message = f"""
Platform: {platform_name}
Date: {meeting.scheduled_at.strftime('%Y-%m-%d')}
Time: {meeting.scheduled_at.strftime('%H:%M')}
Duration: {meeting.duration_minutes} minutes
Participants: {participants_list}
Agenda: {meeting.agenda or 'No agenda'}
Meeting Link: {meeting.meeting_link}
"""
            Announcement.objects.create(
                org=self.request.user.org,
                title=f"Meeting: {meeting.title}",
                message=message.strip(),
                priority='high',
                announcement_type='meeting',
                created_by=self.request.user,
                meeting=meeting
            )


class AnnouncementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'org_id', None):
            return Announcement.objects.none()
        # Filter expired announcements
        return Announcement.objects.filter(
            org=user.org
        ).select_related('created_by', 'meeting').order_by('-created_at')

    def perform_create(self, serializer):
        if self.request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admins and managers can create announcements'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(org=self.request.user.org, created_by=self.request.user)


class AnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'org_id', None):
            return Announcement.objects.none()
        return Announcement.objects.filter(org=user.org).select_related('created_by', 'meeting')

    def perform_update(self, serializer):
        if self.request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admins and managers can update announcements'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admins and managers can delete announcements'}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()
