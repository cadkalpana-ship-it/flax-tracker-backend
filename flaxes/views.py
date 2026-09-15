from django.db import transaction
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.conf import settings

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework import status

from .models import ActivityLog, Design, Flax, Tree, FlaxAssignmentHistory, TreeModuleBatch, TreeModuleDetail, TreeModuleImage
from .serializers import (
    ActivityLogSerializer,
    DesignSerializer,
    FlaxAssignmentHistorySerializer,
    FlaxSerializer,
    TreeModuleBatchSerializer,
    TreeModuleDetailSerializer,
    TreeModuleImageSerializer,
    TreeSerializer,
    UserSerializer,
)

from datetime import datetime, timedelta

from django.utils import timezone

from rest_framework.parsers import FormParser, MultiPartParser

from rest_framework import permissions

from flaxes import serializers

@api_view(["GET"])
def recent_assignment_history(request):
    rows = (
        FlaxAssignmentHistory.objects
        .order_by("-assigned_on", "-id")[:15]
    )

    return Response(
        FlaxAssignmentHistorySerializer(
            rows,
            many=True,
        ).data
    )


class IsAdminRole(permissions.BasePermission):
    """Only staff/superuser accounts can manage users."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only user management.

        GET/POST   /api/users/
        GET/PATCH/DELETE /api/users/<id>/
    """

    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        qs = super().get_queryset()

        search = self.request.query_params.get("search", "").strip()

        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        return qs

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise serializers.ValidationError(
                "You cannot delete your own account."
            )

        instance.delete()


class TreeModuleBatchViewSet(viewsets.ModelViewSet):
    """
    Tree Module API.

    Normal batch API:

        GET  /api/tree-module-batches/
        POST /api/tree-module-batches/

    Available Tree Numbers for Flax assignment:

        GET /api/tree-module-batches/available-trees/

    Upload images:

        POST /api/tree-module-batches/<batch_id>/images/
    """

    queryset = (
        TreeModuleBatch.objects
        .prefetch_related(
            "details",
            "images",
        )
        .all()
    )

    serializer_class = TreeModuleBatchSerializer

    permission_classes = [
        IsAuthenticated
    ]

    # ========================================================
    # QUERYSET
    # ========================================================

    def get_queryset(self):
        return (
            TreeModuleBatch.objects
            .prefetch_related(
                "details",
                "images",
            )
            .order_by(
                "-submitted_on"
            )
        )

    # ========================================================
    # AVAILABLE TREES
    # ========================================================

    @action(
        detail=False,
        methods=["get"],
        url_path="available-trees",
    )
    def available_trees(self, request):
        """
        Return Tree Module Tree Numbers that are available
        for new Flax assignment.

        IMPORTANT:

        A Tree Number can only ever be assigned ONCE. Once it has
        been used for an assignment — even after that Flax is later
        released or the assignment is removed — it is permanently
        excluded from this list. TreeModuleDetail records themselves
        are NEVER deleted; we just never offer an already-used tree
        number again.
        """

        # ----------------------------------------------------
        # Find Tree Numbers that have EVER been assigned.
        #
        # We look at FlaxAssignmentHistory for ANY status
        # (Assigned / Released / Removed) — a tree that has been
        # used even once, and later released, still counts as used.
        # ----------------------------------------------------

        used_tree_numbers = (
            FlaxAssignmentHistory.objects
            .exclude(tree_no__isnull=True)
            .exclude(tree_no__exact="")
            .values_list("tree_no", flat=True)
            .distinct()
        )

        used_tree_numbers = {
            str(tree_no).strip()
            for tree_no in used_tree_numbers
            if tree_no
        }

        # Safety net: also exclude anything currently marked as
        # Assigned on the Flax table itself, in case a record was
        # ever created without a matching history row.
        currently_assigned_tree_numbers = (
            Flax.objects
            .filter(
                assignment_status__iexact="Assigned"
            )
            .exclude(
                tree_no__isnull=True
            )
            .exclude(
                tree_no__exact=""
            )
            .values_list(
                "tree_no",
                flat=True,
            )
        )

        used_tree_numbers.update(
            str(tree_no).strip()
            for tree_no in currently_assigned_tree_numbers
            if tree_no
        )

        # ----------------------------------------------------
        # Get Tree Module records
        # ----------------------------------------------------

        details = (
            TreeModuleDetail.objects
            .select_related("batch")
            .order_by(
                "tree_no",
                "-created_on",
                "-id",
            )
        )

        available_details = []

        # Prevent duplicate Tree Numbers in dropdown
        seen_tree_numbers = set()

        for detail in details:

            tree_no = (
                str(detail.tree_no).strip()
                if detail.tree_no
                else ""
            )

            # Ignore empty Tree Numbers
            if not tree_no:
                continue

            # ------------------------------------------------
            # ALREADY USED (assigned at least once, ever)
            # ------------------------------------------------
            #
            # Keep the record in DB but don't return it, even
            # after release/removal.
            #

            if tree_no in used_tree_numbers:
                continue

            # ------------------------------------------------
            # DUPLICATE
            # ------------------------------------------------

            if tree_no in seen_tree_numbers:
                continue

            seen_tree_numbers.add(tree_no)

            available_details.append(
                detail
            )

        serializer = TreeModuleDetailSerializer(
            available_details,
            many=True,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
    # ========================================================
    # UPLOAD IMAGES
    # ========================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="images",
        parser_classes=[
            MultiPartParser,
            FormParser,
        ],
    )
    def upload_images(
        self,
        request,
        pk=None,
    ):
        batch = self.get_object()

        files = request.FILES.getlist(
            "images"
        )

        # Also support single image
        if not files:

            single_image = request.FILES.get(
                "image"
            )

            if single_image:
                files = [
                    single_image
                ]

        if not files:
            return Response(
                {
                    "detail":
                    "No images were uploaded."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_images = []

        for image in files:

            created = (
                TreeModuleImage.objects.create(
                    batch=batch,
                    image=image,
                )
            )

            created_images.append(
                created
            )

        serializer = TreeModuleImageSerializer(
            created_images,
            many=True,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
    
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    from django.contrib.auth import authenticate

    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {
                "error": "Username and password are required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(
        username=username,
        password=password,
    )

    if user is None:
        return Response(
            {
                "error": "Invalid username or password."
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {
                "error": "This account is inactive."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    token, created = Token.objects.get_or_create(
        user=user
    )

    if user.is_staff or user.is_superuser:
        role = "admin"
    else:
        role = "user"

    full_name = user.get_full_name().strip()

    if not full_name:
        full_name = user.username

    return Response(
        {
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "name": full_name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": role,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            },
        },
        status=status.HTTP_200_OK,
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user

    if user.is_staff or user.is_superuser:
        role = "admin"
    else:
        role = "user"

    full_name = user.get_full_name().strip()

    if not full_name:
        full_name = user.username

    return Response(
        {
            "id": user.id,
            "username": user.username,
            "name": full_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": role,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        }
    )

class IsAdminUser(BasePermission):
    """
    Only Django staff/superuser accounts are considered Admin.
    """

    message = "Only Admin can create Flax."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_staff
                or request.user.is_superuser
            )
        )

class FlaxViewSet(viewsets.ModelViewSet):
    queryset = Flax.objects.all()
    serializer_class = FlaxSerializer
    lookup_field = "flax_no"

    def get_permissions(self):
        """
        Only Admin can create Flax.
        Other authenticated users can continue
        using the existing Flax API.
        """

        if self.action == "create":
            return [IsAdminUser()]

        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()

        search = self.request.query_params.get(
            "search", ""
        ).strip()

        size = self.request.query_params.get(
            "size", ""
        ).strip()

        assignment_status = self.request.query_params.get(
            "assignment_status", ""
        ).strip()

        process_status = self.request.query_params.get(
            "process_status", ""
        ).strip()

        category = self.request.query_params.get(
            "category", ""
        ).strip()

        design_id = self.request.query_params.get(
            "design_id", ""
        ).strip()

        tree_no = self.request.query_params.get(
            "tree_no", ""
        ).strip()

        condition = self.request.query_params.get(
            "condition", ""
        ).strip()

        # -----------------------------
        # Search
        # -----------------------------

        if search:
            qs = qs.filter(
                Q(flax_no__icontains=search)
                | Q(flax_size__icontains=search)
                | Q(design_id__icontains=search)
                | Q(design_name__icontains=search)
                | Q(tree_no__icontains=search)
                | Q(tree_id__icontains=search)
                | Q(category__icontains=search)
            )

        # -----------------------------
        # Size filter
        # -----------------------------

        if size:
            qs = qs.filter(
                flax_size__iexact=size
            )

        # -----------------------------
        # Assignment status
        # -----------------------------

        if assignment_status:
            qs = qs.filter(
                assignment_status__iexact=assignment_status
            )

        # -----------------------------
        # Condition filter
        # -----------------------------

        if condition:
            if condition.lower() == "active":
                qs = qs.filter(
                    assignment_status__in=[
                        Flax.AssignmentStatus.AVAILABLE,
                        Flax.AssignmentStatus.ASSIGNED,
                    ]
                )

            elif condition.lower() == "inactive":
                qs = qs.filter(
                    assignment_status=Flax.AssignmentStatus.UNDER_MAINTENANCE
                )

        # -----------------------------
        # Process status
        # -----------------------------

        if process_status:
            qs = qs.filter(
                process_status__iexact=process_status
            )

        # -----------------------------
        # Category
        # -----------------------------

        if category:
            qs = qs.filter(
                category__iexact=category
            )

        # -----------------------------
        # Design
        # -----------------------------

        if design_id:
            qs = qs.filter(
                design_id__iexact=design_id
            )

        # -----------------------------
        # Tree
        # -----------------------------

        if tree_no:
            qs = qs.filter(
                tree_no__iexact=tree_no
            )

        return qs

    @action(
    detail=True,
    methods=["delete"],
    url_path="remove-assignment",
)
    def remove_assignment(self, request, flax_no=None):
        confirmation_code = str(
            request.data.get("confirmation_code", "")
        ).strip()

        required_code = str(
            getattr(settings, "FLAX_ASSIGNMENT_REMOVE_CODE", "")
        ).strip()

        if not required_code:
            return Response(
                {
                    "error": (
                        "Assignment removal is not configured"
                    )
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if confirmation_code != required_code:
            return Response(
                {
                    "error": "Invalid confirmation code"
                },
                status=http_status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            flax = (
                Flax.objects
                .select_for_update()
                .get(flax_no=flax_no)
            )

            if flax.assignment_status != Flax.AssignmentStatus.ASSIGNED:
                return Response(
                    {
                        "error": (
                            f"{flax.flax_no} is not currently assigned"
                        )
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            old_tree_no = flax.tree_no
            removed_time = timezone.now()

            # Close the currently open assignment history.
            history = (
                FlaxAssignmentHistory.objects
                .filter(
                    flax_no=flax.flax_no,
                    status=FlaxAssignmentHistory.Status.ASSIGNED,
                    released_on__isnull=True,
                    removed_on__isnull=True,
                )
                .order_by("-assigned_on")
                .first()
            )

            if history:
                history.removed_on = removed_time
                history.status = FlaxAssignmentHistory.Status.REMOVED

                history.save(
                    update_fields=[
                        "removed_on",
                        "status",
                    ]
                )

            # Return flax to Available.
            flax.assignment_status = Flax.AssignmentStatus.AVAILABLE
            flax.tree_no = ""
            flax.tree_id = ""
            flax.assigned_on = None

            # IMPORTANT:
            # Do not change process_status or released_on here.
            # This preserves your existing behaviour.
            flax.save()

            # Activity log.
            ActivityLog.objects.create(
                activity_type="ASSIGNMENT_REMOVED",
                flax_no=flax.flax_no,
                tree_no=old_tree_no,
                message=(
                    f"{flax.flax_no} assignment removed "
                    f"from tree {old_tree_no}"
                ),
            )

        return Response(
            FlaxSerializer(flax).data,
            status=http_status.HTTP_200_OK,
        )
    # --------------------------------------------------
    # Change assignment status
    # --------------------------------------------------

    @action(
    detail=True,
    methods=["patch"],
    url_path="set-status",
)
    def set_status(self, request, flax_no=None):

        flax = self.get_object()

        new_status = request.data.get("assignment_status")
        remarks = str(
            request.data.get("remarks", "")
        ).strip()

        valid_statuses = [
            choice.value
            for choice in Flax.AssignmentStatus
        ]

        if new_status not in valid_statuses:
            return Response(
                {
                    "error": (
                        "assignment_status must be "
                        "Available, Assigned or Under Maintenance"
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

       

        old_status = flax.assignment_status

        flax.assignment_status = new_status

        if new_status == Flax.AssignmentStatus.ASSIGNED:

            flax.assigned_on = timezone.now()

        elif new_status == Flax.AssignmentStatus.AVAILABLE:

            flax.assigned_on = None
            flax.tree_no = ""
            flax.tree_id = ""

            # Clear old maintenance reason
            flax.remarks = ""

        elif new_status == Flax.AssignmentStatus.UNDER_MAINTENANCE:

            flax.assigned_on = None
            flax.tree_no = ""
            flax.tree_id = ""

            flax.remarks = remarks

        flax.save()

        ActivityLog.objects.create(
            activity_type="STATUS_CHANGED",
            flax_no=flax.flax_no,
            tree_no=flax.tree_no,
            message=(
                f"{flax.flax_no} status changed "
                f"from {old_status} to {new_status}"
                + (
                    f" - Reason: {remarks}"
                    if remarks
                    else ""
                )
            ),
        )

        return Response(
            FlaxSerializer(flax).data
        )

    # --------------------------------------------------
    # Assign Flax to Tree
    # --------------------------------------------------

    # --------------------------------------------------
# Assign Flax to Tree
# --------------------------------------------------

    @action(
        detail=True,
        methods=["patch"],
        url_path="assign",
    )
    def assign(self, request, flax_no=None):

        tree_no = str(
            request.data.get("tree_no", "")
        ).strip()

        tree_id = str(
            request.data.get("tree_id", "")
        ).strip()

        # --------------------------------------------------
        # Validate tree number
        # --------------------------------------------------

        if not tree_no:
            return Response(
                {
                    "error": "tree_no is required"
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():

            # --------------------------------------------------
            # Get flax
            # --------------------------------------------------

            try:
                flax = (
                    Flax.objects
                    .select_for_update()
                    .get(flax_no=flax_no)
                )
            except Flax.DoesNotExist:
                return Response(
                    {
                        "error": (
                            f"Flax '{flax_no}' does not exist"
                        )
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # --------------------------------------------------
            # Check flax availability
            # --------------------------------------------------

            if (
                flax.assignment_status
                != Flax.AssignmentStatus.AVAILABLE
            ):
                return Response(
                    {
                        "error": (
                            f"{flax.flax_no} is not available "
                            f"for assignment. Current status: "
                            f"{flax.assignment_status}"
                        )
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # --------------------------------------------------
            # Assignment time
            # --------------------------------------------------

            assigned_time = timezone.now()

            # --------------------------------------------------
            # Update current flax
            # --------------------------------------------------

            flax.tree_no = tree_no
            flax.tree_id = tree_id

            flax.assignment_status = (
                Flax.AssignmentStatus.ASSIGNED
            )

            flax.process_status = (
                Flax.ProcessStatus.NOT_RELEASED
            )

            flax.assigned_on = assigned_time

            flax.save()

            # --------------------------------------------------
            # Create assignment history
            # --------------------------------------------------

            FlaxAssignmentHistory.objects.create(
                flax_no=flax.flax_no,
                tree_no=tree_no,
                tree_name="",
                assigned_on=assigned_time,
                released_on=None,
                removed_on=None,
                status=(
                    FlaxAssignmentHistory.Status.ASSIGNED
                ),
            )

            # --------------------------------------------------
            # Activity log
            # --------------------------------------------------

            ActivityLog.objects.create(
                activity_type="FLAX_ASSIGNED",
                flax_no=flax.flax_no,
                tree_no=tree_no,
                message=(
                    f"{flax.flax_no} assigned to "
                    f"tree {tree_no}"
                ),
            )

        return Response(
            FlaxSerializer(flax).data,
            status=http_status.HTTP_200_OK,
        )
        # --------------------------------------------------
        # Release Flax
        # --------------------------------------------------

    @action(detail=True, methods=["patch"], url_path="release")
    def release(self, request, flax_no=None):
        with transaction.atomic():
            flax = (
                Flax.objects
                .select_for_update()
                .get(flax_no=flax_no)
            )

            if flax.assignment_status != Flax.AssignmentStatus.ASSIGNED:
                return Response(
                    {
                        "error": (
                            f"{flax.flax_no} is not currently assigned"
                        )
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            old_tree_no = flax.tree_no
            released_time = timezone.now()

            # Close the currently open history record.
            history = (
                FlaxAssignmentHistory.objects
                .filter(
                    flax_no=flax.flax_no,
                    status=FlaxAssignmentHistory.Status.ASSIGNED,
                    released_on__isnull=True,
                    removed_on__isnull=True,
                )
                .order_by("-assigned_on")
                .first()
            )

            if history:
                history.released_on = released_time
                history.status = FlaxAssignmentHistory.Status.RELEASED
                history.save(
                    update_fields=[
                        "released_on",
                        "status",
                    ]
                )

            # Update current flax state.
            flax.assignment_status = Flax.AssignmentStatus.AVAILABLE
            flax.process_status = Flax.ProcessStatus.RELEASED

            flax.tree_no = ""
            flax.tree_id = ""

            flax.released_on = released_time

            flax.save()

            # Activity log.
            ActivityLog.objects.create(
                activity_type="FLAX_RELEASED",
                flax_no=flax.flax_no,
                tree_no=old_tree_no,
                message=(
                    f"{flax.flax_no} released from tree "
                    f"{old_tree_no}"
                ),
            )

        return Response(
            FlaxSerializer(flax).data,
            status=http_status.HTTP_200_OK,
        )

    # --------------------------------------------------
    # Change process status
    # --------------------------------------------------

    @action(
        detail=True,
        methods=["patch"],
        url_path="process-status",
    )
    def process_status(self, request, flax_no=None):

        flax = self.get_object()

        new_status = request.data.get(
            "process_status"
        )

        valid_statuses = [
            choice.value
            for choice in Flax.ProcessStatus
        ]

        if new_status not in valid_statuses:
            return Response(
                {
                    "error": (
                        "process_status must be "
                        "Not Released, In Process or Released"
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        old_status = flax.process_status

        flax.process_status = new_status

        if new_status == Flax.ProcessStatus.RELEASED:
            flax.released_on = timezone.now()

        flax.save()

        ActivityLog.objects.create(
            activity_type="PROCESS_STATUS_CHANGED",
            flax_no=flax.flax_no,
            tree_no=flax.tree_no,
            message=(
                f"{flax.flax_no} process status changed "
                f"from {old_status} to {new_status}"
            ),
        )

        return Response(
            FlaxSerializer(flax).data
        )


# ======================================================
# TREE
# ======================================================

class TreeViewSet(viewsets.ModelViewSet):

    queryset = Tree.objects.all()
    serializer_class = TreeSerializer
    lookup_field = "tree_no"

    def get_queryset(self):

        qs = super().get_queryset()

        search = self.request.query_params.get(
            "search", ""
        ).strip()

        status_param = self.request.query_params.get(
            "status", ""
        ).strip()

        category = self.request.query_params.get(
            "category", ""
        ).strip()

        if search:
            qs = qs.filter(
                Q(tree_no__icontains=search)
                | Q(tree_id__icontains=search)
                | Q(tree_name__icontains=search)
                | Q(category__icontains=search)
            )

        if status_param:
            qs = qs.filter(
                status__iexact=status_param
            )

        if category:
            qs = qs.filter(
                category__iexact=category
            )

        return qs


# ======================================================
# DESIGN
# ======================================================

class DesignViewSet(viewsets.ModelViewSet):

    queryset = Design.objects.all()
    serializer_class = DesignSerializer
    lookup_field = "design_id"

    def get_queryset(self):

        qs = super().get_queryset()

        search = self.request.query_params.get(
            "search", ""
        ).strip()

        category = self.request.query_params.get(
            "category", ""
        ).strip()

        status_param = self.request.query_params.get(
            "status", ""
        ).strip()

        if search:
            qs = qs.filter(
                Q(design_id__icontains=search)
                | Q(design_name__icontains=search)
                | Q(category__icontains=search)
            )

        if category:
            qs = qs.filter(
                category__iexact=category
            )

        if status_param:
            qs = qs.filter(
                status__iexact=status_param
            )

        return qs


# ======================================================
# ACTIVITY
# ======================================================

class ActivityLogViewSet(
    viewsets.ReadOnlyModelViewSet
):

    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer


# ======================================================
# DASHBOARD SUMMARY
# ======================================================

@api_view(["GET"])
def dashboard_summary(request):

    total = Flax.objects.count()

    assigned = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.ASSIGNED
    ).count()

    available = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.AVAILABLE
    ).count()

    under_maintenance = Flax.objects.filter(assignment_status=Flax.AssignmentStatus.UNDER_MAINTENANCE).count()

    return Response(
        {
            "total_flax": total,
            "assigned_flax": assigned,
            "available_flax": available,
            "under_maintenance_flax": under_maintenance,

            "assigned_percent": (
                round(
                    assigned / total * 100,
                    1,
                )
                if total
                else 0
            ),

            "available_percent": (
                round(
                    available / total * 100,
                    1,
                )
                if total
                else 0
            ),

            "under_maintenance_percent": (
                round(
                    under_maintenance / total * 100,
                    1,
                )
                if total
                else 0
            ),
        }
    )


# ======================================================
# DASHBOARD OVERVIEW
# ======================================================

@api_view(["GET"])
def dashboard_overview(request):

    total = Flax.objects.count()

    assigned = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.ASSIGNED
    ).count()

    available = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.AVAILABLE
    ).count()

    under_maintenance = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.UNDER_MAINTENANCE
    ).count()

    not_released = Flax.objects.filter(
        process_status=Flax.ProcessStatus.NOT_RELEASED
    ).count()

    in_process = Flax.objects.filter(
        process_status=Flax.ProcessStatus.IN_PROCESS
    ).count()

    released = Flax.objects.filter(
        process_status=Flax.ProcessStatus.RELEASED
    ).count()

    return Response(
        {
            "total": total,
            "assigned": assigned,
            "available": available,
            "under_maintenance": under_maintenance,
            "not_released": not_released,
            "in_process": in_process,
            "released": released,
        }
    )


# ======================================================
# DASHBOARD STATUS
# ======================================================

@api_view(["GET"])
def dashboard_status(request):

    total = Flax.objects.count()

    assigned = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.ASSIGNED
    ).count()

    available = Flax.objects.filter(
        assignment_status=Flax.AssignmentStatus.AVAILABLE
    ).count()

    return Response(
        {
            "total_flax": total,
            "assigned_flax": assigned,
            "available_flax": available,
        }
    )


# ======================================================
# SIZE SUMMARY
# ======================================================

@api_view(["GET"])
def dashboard_sizes(request):

    rows = (
        Flax.objects
        .values("flax_size")
        .annotate(count=Count("id"))
        .order_by("flax_size")
    )

    return Response(list(rows))


# ======================================================
# ASSIGNMENT BY SIZE
# ======================================================

@api_view(["GET"])
def dashboard_size_status(request):

    rows = (
        Flax.objects
        .values(
            "flax_size",
            "assignment_status",
        )
        .annotate(count=Count("id"))
        .order_by(
            "flax_size",
            "assignment_status",
        )
    )

    return Response(list(rows))


# ======================================================
# RECENT ASSIGNMENTS
# ======================================================

@api_view(["GET"])
def recent_assignments(request):

    rows = (
        Flax.objects
        .exclude(assigned_on=None)
        .order_by("-assigned_on")[:10]
    )

    return Response(
        FlaxSerializer(
            rows,
            many=True,
        ).data
    )


# ======================================================
# RECENT ACTIVITY
# ======================================================

@api_view(["GET"])
def recent_activity(request):

    rows = ActivityLog.objects.all()[:10]

    return Response(
        ActivityLogSerializer(
            rows,
            many=True,
        ).data
    )


# ======================================================
# TOP DESIGN USAGE
# ======================================================

@api_view(["GET"])
def top_design_usage(request):

    rows = (
        Flax.objects
        .exclude(design_name="")
        .values("design_id", "design_name")
        .annotate(
            count=Count("id")
        )
        .order_by(
            "-count",
            "design_name",
        )[:10]
    )

    return Response(list(rows))


# ======================================================
# SIZE LIST
# ======================================================

@api_view(["GET"])
def size_list(request):

    sizes = (
        Flax.objects
        .exclude(flax_size="")
        .values_list(
            "flax_size",
            flat=True,
        )
        .distinct()
        .order_by("flax_size")
    )

    return Response(list(sizes))


# ======================================================
# CATEGORY LIST
# ======================================================

@api_view(["GET"])
def category_list(request):

    categories = (
        Flax.objects
        .exclude(category="")
        .values_list(
            "category",
            flat=True,
        )
        .distinct()
        .order_by("category")
    )

    return Response(list(categories))


# ======================================================
# FLAX ASSIGNMENT REPORT
# ======================================================

@api_view(["GET"])
def flax_assignment_report(request):
    """
    Flax assignment history report.

    Supported periods:
        daily
        weekly
        monthly
        yearly
        selected

    For selected period:
        ?period=selected&start_date=2026-09-01&end_date=2026-09-11
    """

    period = (
        str(request.query_params.get("period", "daily"))
        .strip()
        .lower()
    )

    today = timezone.localdate()

    # ---------------------------------------------------------
    # Determine report date range
    # ---------------------------------------------------------

    if period == "daily":
        start_date = today
        end_date = today

    elif period == "weekly":
        # Monday -> Sunday
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)

    elif period == "monthly":
        start_date = today.replace(day=1)

        if start_date.month == 12:
            next_month = start_date.replace(
                year=start_date.year + 1,
                month=1,
                day=1,
            )
        else:
            next_month = start_date.replace(
                month=start_date.month + 1,
                day=1,
            )

        end_date = next_month - timedelta(days=1)

    elif period == "yearly":
        start_date = today.replace(
            month=1,
            day=1,
        )
        end_date = today.replace(
            month=12,
            day=31,
        )

    elif period == "selected":
        start_date_raw = request.query_params.get("start_date")
        end_date_raw = request.query_params.get("end_date")

        if not start_date_raw or not end_date_raw:
            return Response(
                {
                    "error": (
                        "For selected period, "
                        "start_date and end_date are required. "
                        "Format: YYYY-MM-DD"
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_date = datetime.strptime(
                start_date_raw,
                "%Y-%m-%d",
            ).date()

            end_date = datetime.strptime(
                end_date_raw,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            return Response(
                {
                    "error": (
                        "Invalid date format. "
                        "Use YYYY-MM-DD"
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if start_date > end_date:
            return Response(
                {
                    "error": (
                        "start_date cannot be after end_date"
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    else:
        return Response(
            {
                "error": (
                    "Invalid period. Use "
                    "daily, weekly, monthly, yearly "
                    "or selected."
                )
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # Convert date range to timezone-aware datetimes
    # ---------------------------------------------------------

    report_start = timezone.make_aware(
        datetime.combine(
            start_date,
            datetime.min.time(),
        )
    )

    report_end = timezone.make_aware(
        datetime.combine(
            end_date,
            datetime.max.time(),
        )
    )

    # ---------------------------------------------------------
    # Find assignments that OVERLAP the report period
    #
    # assigned_on <= report_end
    #
    # AND
    #
    # released_on is NULL OR released_on >= report_start
    #
    # This is important because an assignment can start before
    # the selected report period and still be active during it.
    # ---------------------------------------------------------

    histories = (
        FlaxAssignmentHistory.objects
        .filter(
            assigned_on__lte=report_end,
        )
        .filter(
            models.Q(released_on__isnull=True)
            | models.Q(released_on__gte=report_start),
        )
        .order_by(
            "-assigned_on",
            "-id",
        )
    )

    # ---------------------------------------------------------
    # Fetch current flax information
    # ---------------------------------------------------------

    flax_numbers = histories.values_list(
        "flax_no",
        flat=True,
    )

    flaxes = {
        flax.flax_no: flax
        for flax in Flax.objects.filter(
            flax_no__in=flax_numbers
        )
    }

    # ---------------------------------------------------------
    # Build report
    # ---------------------------------------------------------

    results = []

    total_assignments = 0
    released_count = 0
    currently_assigned_count = 0
    removed_count = 0

    unique_flaxes = set()
    unique_trees = set()

    total_duration_seconds = 0
    completed_duration_count = 0

    now = timezone.now()

    for history in histories:
        total_assignments += 1

        unique_flaxes.add(history.flax_no)
        unique_trees.add(history.tree_no)

        flax = flaxes.get(history.flax_no)

        # ---------------------------------------------
        # Status
        # ---------------------------------------------

        if history.status == FlaxAssignmentHistory.Status.RELEASED:
            status_value = "Released"
            released_count += 1

        elif history.status == FlaxAssignmentHistory.Status.REMOVED:
            status_value = "Removed"
            removed_count += 1

        else:
            status_value = "Assigned"
            currently_assigned_count += 1

        # ---------------------------------------------
        # Duration
        # ---------------------------------------------

        end_time = (
            history.released_on
            or history.removed_on
            or now
        )

        duration_seconds = max(
            0,
            int(
                (
                    end_time - history.assigned_on
                ).total_seconds()
            ),
        )

        total_duration_seconds += duration_seconds

        if (
            history.released_on is not None
            or history.removed_on is not None
        ):
            completed_duration_count += 1

        duration_days = duration_seconds // 86400
        remaining = duration_seconds % 86400

        duration_hours = remaining // 3600
        remaining %= 3600

        duration_minutes = remaining // 60

        duration_text = (
            f"{duration_days}d "
            f"{duration_hours}h "
            f"{duration_minutes}m"
        )

        # ---------------------------------------------
        # Flax details
        # ---------------------------------------------

        flax_size = ""
        design_name = ""
        design_id = ""
        category = ""

        if flax:
            flax_size = str(
                getattr(flax, "flax_size", "") or ""
            )

            design_name = str(
                getattr(flax, "design_name", "") or ""
            )

            design_id = str(
                getattr(flax, "design_id", "") or ""
            )

            category = str(
                getattr(flax, "category", "") or ""
            )

        results.append(
            {
                "flax_no": history.flax_no,
                "flax_size": flax_size,
                "design_id": design_id,
                "design_name": design_name,
                "category": category,
                "tree_no": history.tree_no,
                "tree_name": history.tree_name,
                "assigned_on": history.assigned_on,
                "released_on": history.released_on,
                "removed_on": history.removed_on,
                "duration": duration_text,
                "duration_days": round(
                    duration_seconds / 86400,
                    2,
                ),
                "status": status_value,
            }
        )

    # ---------------------------------------------------------
    # Average duration
    # ---------------------------------------------------------

    if completed_duration_count:
        average_duration_seconds = (
            total_duration_seconds
            / completed_duration_count
        )
    else:
        average_duration_seconds = 0

    average_duration_days = round(
        average_duration_seconds / 86400,
        2,
    )

    # ---------------------------------------------------------
    # Return response
    # ---------------------------------------------------------

    return Response(
        {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),

            "summary": {
                "total_assignments": total_assignments,
                "released": released_count,
                "currently_assigned": currently_assigned_count,
                "removed": removed_count,
                "unique_flaxes": len(unique_flaxes),
                "unique_trees": len(unique_trees),
                "average_assignment_days": (
                    average_duration_days
                ),
            },

            "results": results,
        }
    )