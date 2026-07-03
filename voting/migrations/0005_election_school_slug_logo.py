import django.db.models.deletion
from django.db import migrations, models


def populate_school_slugs(apps, schema_editor):
    """Populate school_slug for all existing elections from school_name."""
    from django.utils.text import slugify
    Election = apps.get_model("voting", "Election")
    used_slugs = {}
    for election in Election.objects.all().order_by("created_at"):
        base_slug = slugify(election.school_name) or "school"
        slug = base_slug
        counter = 1
        # Handle multiple elections for the same school (same slug is OK)
        # Only add counter if the slug was used by a DIFFERENT school_name
        while slug in used_slugs and used_slugs[slug] != election.school_name:
            slug = f"{base_slug}-{counter}"
            counter += 1
        election.school_slug = slug
        election.save()
        used_slugs[slug] = election.school_name


class Migration(migrations.Migration):

    dependencies = [
        ("voting", "0004_userprofile"),
    ]

    operations = [
        # Step 1: Add school_slug as nullable first so we can populate it
        migrations.AddField(
            model_name="election",
            name="school_slug",
            field=models.SlugField(
                blank=True,
                max_length=100,
                help_text="Auto-generated from school name. Used in kiosk URL: /vote/<slug>/",
            ),
        ),
        # Step 2: Add logo field
        migrations.AddField(
            model_name="election",
            name="logo",
            field=models.ImageField(
                blank=True,
                upload_to="elections/logos/",
                help_text="Optional school logo shown in the kiosk header.",
            ),
        ),
        # Step 3: Populate slugs for existing rows
        migrations.RunPython(populate_school_slugs, migrations.RunPython.noop),
    ]
