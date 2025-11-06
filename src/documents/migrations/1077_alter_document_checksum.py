# Generated migration to allow duplicate documents by removing unique constraint on checksum

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "1076_remove_customfieldinstance_documents_customfieldinstance_unique_document_field_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="checksum",
            field=models.CharField(
                db_index=True,
                editable=False,
                help_text="The checksum of the original document.",
                max_length=32,
                unique=False,
                verbose_name="checksum",
            ),
        ),
    ]

