from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_playground", "0004_remove_playgroundstyle_prompt_hint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="playgroundstyle",
            name="name",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
    ]
