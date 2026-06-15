# Generated manually for FocusFlow work module

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='documents/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('file_type', models.CharField(choices=[('pdf', 'PDF'), ('docx', 'DOCX'), ('xlsx', 'XLSX')], max_length=10)),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_documents', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Email',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('status', models.CharField(choices=[('sent', 'Sent'), ('draft', 'Draft')], default='sent', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_emails', to=settings.AUTH_USER_MODEL)),
                ('attachments', models.ManyToManyField(blank=True, related_name='emails', to='api.document')),
                ('cc', models.ManyToManyField(blank=True, related_name='cc_emails', to=settings.AUTH_USER_MODEL)),
                ('to', models.ManyToManyField(related_name='received_emails', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Meeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('platform', models.CharField(choices=[('meet', 'Google Meet'), ('zoom', 'Zoom'), ('teams', 'Microsoft Teams')], max_length=10)),
                ('scheduled_at', models.DateTimeField()),
                ('duration_minutes', models.IntegerField()),
                ('agenda', models.TextField(blank=True)),
                ('meeting_link', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_meetings', to=settings.AUTH_USER_MODEL)),
                ('participants', models.ManyToManyField(related_name='meetings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
