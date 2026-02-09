from django.db import migrations


def remove_visit_permission_toggles(apps, schema_editor):
    PermissionToggle = apps.get_model("accounts", "PermissionToggle")
    PermissionToggle.objects.filter(
        key__in=["delete_visit_media", "edit_completed_visits"],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_permissiontoggle_key"),
    ]

    operations = [
        migrations.RunPython(remove_visit_permission_toggles, migrations.RunPython.noop),
    ]
