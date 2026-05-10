from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class Organisation(models.Model):
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=50, choices=[('university','University'),('corporate','Corporate'),('other','Other')])
    admin_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('Email required')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [('admin','Admin'),('manager','Manager'),('member','Member'),('individual','Individual')]
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='individual')
    org = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.SET_NULL, related_name='members')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    objects = UserManager()

    def __str__(self):
        return self.email

class Task(models.Model):
    PRIORITY = [('high','High'),('medium','Medium'),('low','Low')]
    STATUS = [('pending','Pending'),('in_progress','In Progress'),('completed','Completed')]
    CATEGORY = [('study','Study'),('work','Work'),('personal','Personal')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    assigned_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tasks')
    org = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY, default='personal')
    priority = models.CharField(max_length=10, choices=PRIORITY, default='medium')
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class FocusSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='focus_sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    duration_mins = models.IntegerField(default=25)
    task_label = models.CharField(max_length=200, blank=True)
    distractions = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)

class MoodLog(models.Model):
    MOODS = [('energized','Energized'),('focused','Focused'),('tired','Tired'),('stressed','Stressed'),('happy','Happy')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mood_logs')
    mood = models.CharField(max_length=50, choices=MOODS)
    energy_level = models.IntegerField(default=3)
    recommendation = models.TextField(blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)

class Streak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_active = models.DateField(null=True, blank=True)
    total_sessions = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
