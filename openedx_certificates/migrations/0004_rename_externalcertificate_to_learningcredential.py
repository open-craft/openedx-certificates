# Generated by Django 4.2.18 on 2025-03-10 16:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_celery_beat', '0019_alter_periodictasks_options'),
        ('openedx_certificates', '0003_replace_course_key_with_learning_context_key'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ExternalCertificate',
            new_name='LearningCredential',
        ),
        migrations.RenameModel(
            old_name='ExternalCertificateAsset',
            new_name='LearningCredentialAsset',
        ),
        migrations.RenameModel(
            old_name='ExternalCertificateCourseConfiguration',
            new_name='LearningCredentialConfiguration',
        ),
        migrations.RenameModel(
            old_name='ExternalCertificateType',
            new_name='LearningCredentialType',
        ),
    ]
