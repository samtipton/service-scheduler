from django.urls import path
from . import views

app_name = "schedules"

urlpatterns = [
    # Add URL patterns here
    path("", views.MonthListView.as_view(), name="index"),
    path("<int:id>/", views.MonthView.as_view(), name="month_view"),
]
