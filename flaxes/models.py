from django.db import models

# Add these to your existing flaxes/models.py.
#
# DESIGN: a "batch" is one SUBMIT click — it groups every row you ENTERed
# plus whatever images you attached. This matches the screenshot: one
# shared IMAGES box for potentially many table rows, one SUBMIT button.
#
# require_metal / req_pure_metal / require_alloy are plain manual numeric
# fields for now (DecimalField, blank allowed) — no formula wired in yet,
# per your instruction. When you add the formula later, either compute it
# in the serializer's create()/validate() step, or keep accepting manual
# values and add a separate "auto-calculate" endpoint — your call then.

from django.db import models


class TreeModuleBatch(models.Model):
    submitted_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_on"]

    def __str__(self):
        return f"Batch #{self.pk} ({self.submitted_on:%Y-%m-%d %H:%M})"


class TreeModuleImage(models.Model):
    batch = models.ForeignKey(
        TreeModuleBatch,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to="tree_module_images/")
    uploaded_on = models.DateTimeField(auto_now_add=True)


class TreeModuleDetail(models.Model):
    batch = models.ForeignKey(
        TreeModuleBatch,
        related_name="details",
        on_delete=models.CASCADE,
    )

    sl_no = models.PositiveIntegerField()

    style_no = models.CharField(max_length=50, blank=True)
    bag_no = models.CharField(max_length=50, blank=True)

    tree_no = models.CharField(max_length=50, blank=True)
    tree_wt = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )

    purity = models.CharField(max_length=20, blank=True)
    colour = models.CharField(max_length=30, blank=True)

    # Manual for now — no formula yet.
    require_metal = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    req_pure_metal = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    require_alloy = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )

    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sl_no"]

    def __str__(self):
        return f"{self.style_no} / {self.tree_no} (batch #{self.batch_id})"


class Flax(models.Model):

    class AssignmentStatus(models.TextChoices):
        AVAILABLE = "Available", "Available"
        ASSIGNED = "Assigned", "Assigned"
        UNDER_MAINTENANCE = "Under Maintenance", "Under Maintenance"

    class ProcessStatus(models.TextChoices):
        NOT_RELEASED = "Not Released", "Not Released"
        IN_PROCESS = "In Process", "In Process"
        RELEASED = "Released", "Released"

    flax_no = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    flax_size = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    size_length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    size_width = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    size_unit = models.CharField(
        max_length=20,
        blank=True,
    )

    design_id = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    design_name = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
    )

    category = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    tree_id = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    tree_no = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    assignment_status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.AVAILABLE,
        db_index=True,
    )

    remarks = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    process_status = models.CharField(
        max_length=20,
        choices=ProcessStatus.choices,
        default=ProcessStatus.NOT_RELEASED,
        db_index=True,
    )

    assigned_on = models.DateTimeField(
        null=True,
        blank=True,
    )

    released_on = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_on = models.DateTimeField(
        auto_now_add=True,
    )

    updated_on = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["flax_no"]

    def __str__(self):
        return self.flax_no


class Tree(models.Model):

    tree_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    tree_no = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    tree_name = models.CharField(
        max_length=150,
        blank=True,
    )

    category = models.CharField(
        max_length=100,
        blank=True,
    )

    status = models.CharField(
        max_length=50,
        default="Active",
    )

    created_on = models.DateTimeField(
        auto_now_add=True,
    )

    updated_on = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["tree_no"]

    def __str__(self):
        return self.tree_no


class Design(models.Model):

    design_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    design_name = models.CharField(
        max_length=150,
        db_index=True,
    )

    category = models.CharField(
        max_length=100,
        blank=True,
    )

    usage_count = models.PositiveIntegerField(
        default=0,
    )

    status = models.CharField(
        max_length=50,
        default="Active",
    )

    created_on = models.DateTimeField(
        auto_now_add=True,
    )

    updated_on = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["design_name"]

    def __str__(self):
        return self.design_name


class ActivityLog(models.Model):

    activity_type = models.CharField(
        max_length=50,
        db_index=True,
    )

    flax_no = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    tree_no = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    message = models.CharField(
        max_length=255,
    )

    performed_by = models.CharField(
        max_length=100,
        default="Admin",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

class FlaxAssignmentHistory(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "Assigned", "Assigned"
        RELEASED = "Released", "Released"
        REMOVED = "Removed", "Removed"

    flax_no = models.CharField(
        max_length=100,
        db_index=True,
    )

    tree_no = models.CharField(
        max_length=100,
        db_index=True,
    )

    # Snapshot of the tree name at the time of assignment.
    # This keeps historical reports correct even if the tree name changes later.
    tree_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    assigned_on = models.DateTimeField(
        db_index=True,
    )

    released_on = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    removed_on = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-assigned_on"]
        indexes = [
            models.Index(
                fields=["flax_no", "assigned_on"],
                name="flax_hist_flax_date_idx",
            ),
            models.Index(
                fields=["tree_no", "assigned_on"],
                name="flax_hist_tree_date_idx",
            ),
            models.Index(
                fields=["status", "assigned_on"],
                name="flax_hist_status_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.flax_no} → {self.tree_no} "
            f"({self.assigned_on:%Y-%m-%d %H:%M})"
        )