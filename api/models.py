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
    MOOD_CHOICES = [
        ('focused', 'Focused'),
        ('energized', 'Energized'),
        ('tired', 'Tired'),
        ('stressed', 'Stressed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='focus_sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    duration_mins = models.IntegerField(default=25)
    task_label = models.CharField(max_length=200, blank=True)
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, null=True, blank=True)
    distractions = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)


class MoodLog(models.Model):
    """Separate mood logging for the Mood page (with energy level tracking)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mood_logs')
    mood = models.CharField(max_length=50)
    energy_level = models.IntegerField(default=3)
    recommendation = models.TextField(blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user} - {self.mood}"

class Streak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_active = models.DateField(null=True, blank=True)
    total_sessions = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)


class RecurringTask(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_tasks')
    title = models.CharField(max_length=255)
    scheduled_days = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.title


class RecurringTaskCompletion(models.Model):
    task = models.ForeignKey(RecurringTask, on_delete=models.CASCADE, related_name='completions')
    completed_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['task', 'completed_date'],
                name='unique_recurring_task_completion',
            )
        ]
        ordering = ['completed_date']


class Document(models.Model):
    FILE_TYPES = [('pdf', 'PDF'), ('docx', 'DOCX'), ('xlsx', 'XLSX')]
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)

    def __str__(self):
        return self.title


class Email(models.Model):
    STATUS = [('sent', 'Sent'), ('draft', 'Draft')]
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_emails')
    to = models.ManyToManyField(User, related_name='received_emails')
    cc = models.ManyToManyField(User, related_name='cc_emails', blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS, default='sent')
    attachments = models.ManyToManyField(Document, blank=True, related_name='emails')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject


class Meeting(models.Model):
    PLATFORMS = [('meet', 'Google Meet'), ('zoom', 'Zoom'), ('teams', 'Microsoft Teams')]
    title = models.CharField(max_length=255)
    platform = models.CharField(max_length=10, choices=PLATFORMS)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.IntegerField()
    participants = models.ManyToManyField(User, related_name='meetings')
    agenda = models.TextField(blank=True)
    meeting_link = models.URLField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_meetings')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Announcement(models.Model):
    PRIORITY_CHOICES = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
    ANNOUNCEMENT_TYPE = [('announcement', 'Announcement'), ('meeting', 'Meeting')]
    
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPE, default='announcement')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    meeting = models.OneToOneField(Meeting, null=True, blank=True, on_delete=models.SET_NULL, related_name='announcement')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
