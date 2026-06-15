from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'focus-sessions', views.FocusSessionViewSet, basename='focus')
router.register(r'mood-logs', views.MoodLogViewSet, basename='mood')

urlpatterns = [
    path('auth/register/', views.register),
    path('auth/login/', views.login_view),
    path('auth/me/', views.me),
    path('organisations/', views.organisations),
    path('dashboard/', views.dashboard_stats),
    path('org/members/', views.org_members),
    path('members/', views.org_members),
    path('documents/', views.DocumentListCreateView.as_view()),
    path('meetings/', views.MeetingListCreateView.as_view()),
    path('', include(router.urls)),
]
