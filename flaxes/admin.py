from django.contrib import admin

from .models import ActivityLog, Design, Flax, Tree


@admin.register(Flax)
class FlaxAdmin(admin.ModelAdmin):

    list_display = (
        "flax_no",
        "flax_size",
        "design_name",
        "tree_no",
        "assignment_status",
        "process_status",
        "updated_on",
    )

    list_filter = (
        "assignment_status",
        "process_status",
        "flax_size",
        "category",
    )

    search_fields = (
        "flax_no",
        "flax_size",
        "design_name",
        "tree_no",
        "category",
    )

    ordering = ("flax_no",)


@admin.register(Tree)
class TreeAdmin(admin.ModelAdmin):

    list_display = (
        "tree_no",
        "tree_name",
        "category",
        "status",
        "updated_on",
    )

    list_filter = (
        "status",
        "category",
    )

    search_fields = (
        "tree_no",
        "tree_name",
        "category",
    )

    ordering = ("tree_no",)


@admin.register(Design)
class DesignAdmin(admin.ModelAdmin):

    list_display = (
        "design_id",
        "design_name",
        "category",
        "usage_count",
        "status",
        "updated_on",
    )

    list_filter = (
        "status",
        "category",
    )

    search_fields = (
        "design_id",
        "design_name",
        "category",
    )

    ordering = ("design_name",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):

    list_display = (
        "activity_type",
        "flax_no",
        "tree_no",
        "performed_by",
        "created_at",
    )

    list_filter = (
        "activity_type",
    )

    search_fields = (
        "flax_no",
        "tree_no",
        "message",
        "performed_by",
    )

    ordering = (
        "-created_at",
    )
