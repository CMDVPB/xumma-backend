from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import *


urlpatterns = [

    path("checklists/", VehicleChecklistListAPIView.as_view(),
         name="vehicle-checklist-list"),

    path("vehicles/<int:vehicle_id>/checklist/template/",
         VehicleChecklistTemplateAPIView.as_view(),
         name="vehicle-checklist-template",
         ),

    path("vehicles/<str:vehicle_uf>/checklists/start/",
         StartVehicleChecklistAPIView.as_view(),
         name="vehicle-checklist-start",
         ),

    path("checklists/<int:pk>/", VehicleChecklistDetailAPIView.as_view(),
         name="vehicle-checklist-detail",
         ),

    path("checklists/<int:checklist_id>/finish/",
         FinishChecklistAPIView.as_view(),
         name="vehicle-checklist-finish",
         ),


    path("checklist-answers/<int:pk>/",
         VehicleChecklistAnswerAPIView.as_view(),
         name="vehicle-checklist-answer-update",
         ),

    path("checklist-answers/<int:answer_id>/photos/",
         VehicleChecklistPhotoCreateAPIView.as_view(),
         name="vehicle-checklist-photo-create",
         ),


    path("vehicles/<int:vehicle_id>/equipment/",
         VehicleEquipmentListCreateAPIView.as_view(),
         name="vehicle-equipment-list-create",
         ),

    path("equipment/<int:pk>/",
         VehicleEquipmentUpdateAPIView.as_view(),
         name="vehicle-equipment-update",
         ),

    path("inspection-files/<str:uf>/",
         InspectionFileProxyView.as_view(),
         name="inspection-file-proxy",
         ),

    path("inspection-files/upload/", InspectionFileUploadView.as_view(),
         name="inspection-file-upload"),

    path("inspection-files/<int:pk>/delete/",
         InspectionFileDeleteView.as_view(), name="inspection-file-delete"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
