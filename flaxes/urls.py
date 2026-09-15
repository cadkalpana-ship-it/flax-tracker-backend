from django.conf.urls.static import static
from django.urls import path
from rest_framework.routers import DefaultRouter

from django.urls import path

from flax_backend import settings
from flaxes.serializers import TreeModuleBatchSerializer

from .views import (
    ActivityLogViewSet,
    DesignViewSet,
    FlaxViewSet,
    TreeModuleBatchViewSet,
    TreeViewSet,

    dashboard_summary,
    dashboard_overview,
    dashboard_status,
    dashboard_sizes,
    dashboard_size_status,
    flax_assignment_report,
    recent_assignment_history,

    recent_assignments,
    recent_activity,
    top_design_usage,

    size_list,
    category_list,

    UserViewSet,
)

from .views import (
    login_view,
    me_view,
)




router = DefaultRouter()

router.register(
    r"users",
    UserViewSet,
    basename="user",
)

router.register(
    r"flaxes",
    FlaxViewSet,
    basename="flax",
)

router.register(
    r"trees",
    TreeViewSet,
    basename="tree",
)

router.register(
    r"designs",
    DesignViewSet,
    basename="design",
)

router.register(
    r"activity",
    ActivityLogViewSet,
    basename="activity",
)

router.register(
    r"tree-module-batches",
    TreeModuleBatchViewSet,
    basename="tree-module-batch",
)


urlpatterns = [

    # Login

    path("auth/login/", login_view, name="login"),
    path("auth/me/", me_view, name="me"),


    path(
        "assignment-history/recent/",
        recent_assignment_history,
    ),

    

    # -------------------------
    # Dashboard
    # -------------------------

    path(
        "dashboard/summary/",
        dashboard_summary,
    ),

    path(
        "dashboard/overview/",
        dashboard_overview,
    ),

    path(
        "dashboard/status/",
        dashboard_status,
    ),

    path(
        "dashboard/sizes/",
        dashboard_sizes,
    ),

    path(
        "dashboard/size-status/",
        dashboard_size_status,
    ),

    path(
        "dashboard/recent-assignments/",
        recent_assignments,
    ),

    path(
        "dashboard/recent-activity/",
        recent_activity,
    ),

    path(
        "dashboard/top-design-usage/",
        top_design_usage,
    ),

    # -------------------------
    # Dropdown/filter data
    # -------------------------

    path(
        "sizes/",
        size_list,
    ),

    path(
        "categories/",
        category_list,
    ),

    path(
        "reports/flax-assignment/",
        flax_assignment_report,
        name="flax-assignment-report",
    ),
]


urlpatterns += router.urls