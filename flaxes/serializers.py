from django.contrib.auth.models import User

from rest_framework import serializers

from .models import (
    ActivityLog,
    Design,
    Flax,
    Tree,
    TreeModuleBatch,
    TreeModuleDetail,
    TreeModuleImage,
    FlaxAssignmentHistory,
)

class FlaxAssignmentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FlaxAssignmentHistory
        fields = [
            "id",
            "flax_no",
            "tree_no",
            "tree_name",
            "assigned_on",
            "released_on",
            "removed_on",
            "status",
            "created_at",
        ]
        read_only_fields = fields

# ============================================================
# TREE MODULE DETAIL
# ============================================================

class TreeModuleDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreeModuleDetail
        fields = [
            "id",
            "sl_no",
            "style_no",
            "bag_no",
            "tree_no",
            "tree_wt",
            "purity",
            "colour",
            "require_metal",
            "req_pure_metal",
            "require_alloy",
            "created_on",
        ]

        read_only_fields = [
            "id",
            "created_on",
        ]


# ============================================================
# TREE MODULE IMAGE
# ============================================================

class TreeModuleImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TreeModuleImage
        fields = [
            "id",
            "image",
            "image_url",
            "uploaded_on",
        ]

        read_only_fields = [
            "id",
            "image_url",
            "uploaded_on",
        ]

    def get_image_url(self, obj):
        """
        Return the complete URL of the uploaded image.

        Example:
        http://127.0.0.1:8000/media/tree_module_images/abc.jpg
        """

        if not obj.image:
            return ""

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(
                obj.image.url
            )

        return obj.image.url


# ============================================================
# TREE MODULE BATCH
# ============================================================

class TreeModuleBatchSerializer(serializers.ModelSerializer):
    details = TreeModuleDetailSerializer(
        many=True
    )

    images = TreeModuleImageSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TreeModuleBatch

        fields = [
            "id",
            "submitted_on",
            "details",
            "images",
        ]

        read_only_fields = [
            "id",
            "submitted_on",
            "images",
        ]

    def create(self, validated_data):
        """
        Create one TreeModuleBatch and all of its
        TreeModuleDetail rows.
        """

        details_data = validated_data.pop(
            "details",
            []
        )

        batch = TreeModuleBatch.objects.create(
            **validated_data
        )

        for detail_data in details_data:
            TreeModuleDetail.objects.create(
                batch=batch,
                **detail_data
            )

        return batch


# ============================================================
# LOGIN
# ============================================================

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(
            username=username,
            password=password,
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid username or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        attrs["user"] = user

        return attrs


# ============================================================
# FLAX
# ============================================================

class FlaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flax

        fields = [
            "id",
            "flax_no",
            "flax_size",
            "size_length",
            "size_width",
            "size_unit",
            "design_id",
            "design_name",
            "category",
            "tree_id",
            "tree_no",
            "assignment_status",
            "remarks",
            "process_status",
            "assigned_on",
            "released_on",
            "created_on",
            "updated_on",
        ]

        read_only_fields = [
            "id",
            "created_on",
            "updated_on",
        ]


# ============================================================
# TREE
# ============================================================

class TreeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tree

        fields = "__all__"

        read_only_fields = [
            "id",
            "created_on",
            "updated_on",
        ]


# ============================================================
# DESIGN
# ============================================================

class DesignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Design

        fields = "__all__"

        read_only_fields = [
            "id",
            "created_on",
            "updated_on",
        ]


# ============================================================
# ACTIVITY LOG
# ============================================================

class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog

        fields = "__all__"

        read_only_fields = [
            "id",
            "created_at",
        ]

# ============================================================
# USER (for admin "Add User" management)
# ============================================================

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    # Not a real User model field — we map it to is_staff ourselves.
    role = serializers.CharField(
        write_only=True,
        required=False,
    )

    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "name",
            "role",
            "is_active",
            "date_joined",
            "password",
        ]
        read_only_fields = ["id", "date_joined"]

    def get_name(self, obj):
        full_name = obj.get_full_name().strip()
        return full_name or obj.username

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["role"] = (
            "admin" if (instance.is_staff or instance.is_superuser) else "user"
        )
        return data

    def validate_username(self, value):
        qs = User.objects.filter(username__iexact=value)

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )

        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.pop("role", "user")

        if not password:
            raise serializers.ValidationError(
                {"password": "Password is required."}
            )

        user = User(**validated_data)
        user.is_staff = str(role).strip().lower() == "admin"
        user.set_password(password)
        user.save()

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.pop("role", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if role is not None:
            instance.is_staff = str(role).strip().lower() == "admin"

        if password:
            instance.set_password(password)

        instance.save()

        return instance