from django.db import models

# Create your models here.
class AssignRightsModel(models.Model):
    user_id = models.IntegerField()
    main_menu = models.IntegerField()
    sub_menu = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assign_rights'


class ChatbotVisibilityModel(models.Model):
    """Who sees the HR Assistant launcher — one row, edited from Assign Rights.

    A single row rather than a per-user flag, because the common cases are
    "everybody" and "nobody" and neither should mean writing four hundred rows.
    `mode` decides how the companion table is read:

        all       every signed-in user sees it; the table is ignored
        specific  only the users listed in ChatbotVisibilityUserModel
        none      nobody

    The check itself lives in the frontend widget. Nothing here changes how the
    assistant answers - it only decides whether the launcher is rendered.
    """

    MODE_ALL = "all"
    MODE_SPECIFIC = "specific"
    MODE_NONE = "none"
    MODES = (MODE_ALL, MODE_SPECIFIC, MODE_NONE)

    mode = models.CharField(max_length=10, default=MODE_ALL)
    updated_at = models.DateTimeField(auto_now=True)
    # auth_user.id of the administrator who last changed it, for accountability.
    updated_by = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'chatbot_visibility'


class ChatbotVisibilityUserModel(models.Model):
    """A user allowed to see the launcher while mode is "specific"."""

    # auth_user.id, the same identifier assign_rights uses.
    user_id = models.IntegerField(db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chatbot_visibility_users'
