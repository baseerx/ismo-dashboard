"""Put employee names into notifications that were raised before names existed.

`message` is stored as plain text, so rows written earlier keep reading
"ERP 1234 applied for ..." while new ones carry the name. Rewriting them here
means the dropdown reads the same way top to bottom instead of looking as
though only some notifications were fixed.
"""

import re

from django.db import migrations

# "ERP 1234 applied for ..." — the applicant on a request awaiting approval.
APPLICANT = re.compile(r"^ERP (\d+) (applied for )")

# "... has been approved." — a decision that names nobody. Anchored at the end
# so a message already carrying "by <name>." is left alone.
DECISION = re.compile(r"has been (approved|rejected)\.$")


def _names_by_erp_id(Employees):
    """erp_id -> name, preferring the active (flag=1) row of a repeated id."""
    names = {}

    # Ascending flag, so the active row is written last and wins.
    for erp_id, name in Employees.objects.order_by("flag").values_list(
        "erp_id", "name"
    ):
        name = (name or "").strip()
        if name:
            names[erp_id] = name

    return names


def add_names(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    Employees = apps.get_model("users", "Employees")

    names = _names_by_erp_id(Employees)
    updated = []

    for note in Notification.objects.all().iterator():
        original = note.message or ""
        if not original:
            continue

        message = original

        applicant = APPLICANT.match(message)
        if applicant:
            erp_id = int(applicant.group(1))
            name = names.get(erp_id)
            if name:
                message = (
                    f"{name} (ERP {erp_id}) "
                    f"{applicant.group(2)}{message[applicant.end():]}"
                )

        if note.event in ("approved", "rejected"):
            actor = names.get(note.actor_erp_id)
            if actor:
                # Function replacement: a name is not a regex template.
                message = DECISION.sub(
                    lambda m: f"has been {m.group(1)} by {actor}.",
                    message,
                    count=1,
                )

        if message != original:
            note.message = message
            updated.append(note)

    if updated:
        Notification.objects.bulk_update(updated, ["message"], batch_size=200)


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        # The names come out of the employees table.
        ("users", "0001_initial"),
    ]

    operations = [
        # Text only — nothing to undo on the way back down.
        migrations.RunPython(add_names, migrations.RunPython.noop),
    ]
