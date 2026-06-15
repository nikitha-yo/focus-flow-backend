from django.test import TestCase

# Create your tests here.
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from .models import RecurringTask, RecurringTaskCompletion, Streak, User
from .views import sunday_for


class WeeklyTrackerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='tracker@example.com',
            username='tracker',
            password='password123',
        )
        Streak.objects.create(user=self.user)
        self.client.force_authenticate(self.user)

    def test_create_task_and_toggle_completion(self):
        response = self.client.post('/api/weekly-tracker/', {
            'title': 'Exercise',
            'scheduled_days': [0, 2, 4],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        task = RecurringTask.objects.get(user=self.user)
        completion_date = sunday_for(timezone.localdate()) + timedelta(days=2)

        response = self.client.post(
            f'/api/weekly-tracker/tasks/{task.id}/toggle/',
            {'date': completion_date.isoformat()},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(RecurringTaskCompletion.objects.filter(task=task, completed_date=completion_date).exists())
        self.assertGreater(response.data['metrics']['completion_rate'], 0)

        response = self.client.post(
            f'/api/weekly-tracker/tasks/{task.id}/toggle/',
            {'date': completion_date.isoformat()},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RecurringTaskCompletion.objects.filter(task=task, completed_date=completion_date).exists())

    def test_unscheduled_day_cannot_be_completed(self):
        task = RecurringTask.objects.create(user=self.user, title='Read', scheduled_days=[1])
        sunday = sunday_for(timezone.localdate())
        response = self.client.post(
            f'/api/weekly-tracker/tasks/{task.id}/toggle/',
            {'date': sunday.isoformat()},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_includes_weekly_progress(self):
        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('weekly_task_progress', response.data)
        self.assertEqual(response.data['weekly_task_progress']['current_streak'], 0)
