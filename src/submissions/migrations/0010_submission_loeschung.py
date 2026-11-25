# Umbenennung nach dem Glossar (Issue #66): Felder der Löschung umbenennen, Daten bleiben
# erhalten (RenameField); dazu die neuen Beschriftungen.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0009_belichtungsangaben"),
    ]

    operations = [
        migrations.RenameField(
            model_name="submission",
            old_name="withdrawn_at",
            new_name="deleted_at",
        ),
        migrations.RenameField(
            model_name="submission",
            old_name="withdrawn_by",
            new_name="deleted_by",
        ),
        migrations.AlterModelOptions(
            name="submission",
            options={
                "ordering": ["created_at"],
                "verbose_name": "Submission",
                "verbose_name_plural": "Submissions",
            },
        ),
        migrations.AlterField(
            model_name="campaign",
            name="quota",
            field=models.PositiveBigIntegerField(verbose_name="Quote je Submission (Bytes)"),
        ),
        migrations.AlterField(
            model_name="consent",
            name="kind",
            field=models.CharField(
                choices=[
                    ("project_use", "Nutzung im Projekt"),
                    ("publish_credit", "Namensnennung"),
                ],
                max_length=32,
                verbose_name="Art",
            ),
        ),
        migrations.AlterField(
            model_name="master",
            name="rejection_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("format", "falsches Format"),
                    ("float32", "kein 32-Bit-Gleitkomma"),
                    ("planes", "falsche Ebenen für den Kanal"),
                    ("damaged", "beschädigt oder unvollständig"),
                    ("size", "Größe weicht ab"),
                    ("duplicate", "Dublette in derselben Submission"),
                ],
                max_length=16,
                verbose_name="Art der Ablehnung",
            ),
        ),
        migrations.AlterField(
            model_name="submission",
            name="credit_name",
            field=models.CharField(blank=True, max_length=120, verbose_name="Namensnennung"),
        ),
        migrations.AlterField(
            model_name="submission",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="gelöscht am"),
        ),
        migrations.AlterField(
            model_name="submission",
            name="deleted_by",
            field=models.CharField(
                blank=True,
                choices=[("participant", "Teilnehmende"), ("operator", "Betreiber")],
                max_length=16,
                verbose_name="gelöscht durch",
            ),
        ),
        migrations.AlterField(
            model_name="submission",
            name="reference",
            field=models.CharField(max_length=16, unique=True, verbose_name="Submission-ID"),
        ),
    ]
