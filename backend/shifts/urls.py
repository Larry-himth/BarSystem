from django.urls import path

from .views import (
    OpenShiftView,
    ShiftApproveView,
    ShiftCloseView,
    ShiftCountView,
    ShiftDisputeView,
    ShiftListView,
    ShiftMomoConfirmView,
    ShiftReportView,
    ShiftSubmitView,
)

urlpatterns = [
    path("", ShiftListView.as_view(), name="shift-list"),
    path("open/", OpenShiftView.as_view(), name="open-shift"),
    path("<int:pk>/count/", ShiftCountView.as_view(), name="shift-count"),
    path("<int:pk>/submit/", ShiftSubmitView.as_view(), name="shift-submit"),
    path("<int:pk>/close/", ShiftCloseView.as_view(), name="shift-close"),
    path("<int:pk>/approve/", ShiftApproveView.as_view(), name="shift-approve"),
    path("<int:pk>/dispute/", ShiftDisputeView.as_view(), name="shift-dispute"),
    path("<int:pk>/momo-confirm/", ShiftMomoConfirmView.as_view(), name="shift-momo-confirm"),
    path("<int:pk>/report/", ShiftReportView.as_view(), name="shift-report"),
]
