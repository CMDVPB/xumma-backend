from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [

    # ----------------------------
    # CHECKLIST TEMPLATE
    # ----------------------------
    path(
        "vehicles/<int:vehicle_id>/checklist/template/",
        VehicleChecklistTemplateAPIView.as_view(),
        name="vehicle-checklist-template",
    ),

    # ----------------------------
    # CHECKLIST SESSION
    # ----------------------------
    path(
        "vehicles/<str:vehicle_uf>/checklists/start/",
        StartVehicleChecklistAPIView.as_view(),
        name="vehicle-checklist-start",
    ),

    path(
        "checklists/<int:pk>/",
        VehicleChecklistDetailAPIView.as_view(),
        name="vehicle-checklist-detail",
    ),

    path(
        "checklists/<int:checklist_id>/finish/",
        FinishChecklistAPIView.as_view(),
        name="vehicle-checklist-finish",
    ),

    # ----------------------------
    # CHECKLIST ANSWERS
    # ----------------------------
    path(
        "checklist-answers/<int:pk>/",
        VehicleChecklistAnswerAPIView.as_view(),
        name="vehicle-checklist-answer-update",
    ),

    # ----------------------------
    # CHECKLIST PHOTOS
    # ----------------------------
    path(
        "checklist-answers/<int:answer_id>/photos/",
        VehicleChecklistPhotoCreateAPIView.as_view(),
        name="vehicle-checklist-photo-create",
    ),

    # ----------------------------
    # VEHICLE EQUIPMENT
    # ----------------------------
    path(
        "vehicles/<int:vehicle_id>/equipment/",
        VehicleEquipmentListCreateAPIView.as_view(),
        name="vehicle-equipment-list-create",
    ),

    path(
        "equipment/<int:pk>/",
        VehicleEquipmentUpdateAPIView.as_view(),
        name="vehicle-equipment-update",
    ),
]

urlpatterns = format_suffix_patterns(urlpatterns)
