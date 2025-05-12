from django.urls import path
from . import views

app_name = "schedules"

urlpatterns = [
    # Add URL patterns here
    path("", views.MonthListView.as_view(), name="index"),
    path("<int:id>/", views.MonthView.as_view(), name="month_view"),
    path("create/", views.create_schedule, name="create_schedule"),
    path(
        "<int:id>/generate",
        views.generate_schedule_assignments,
        name="generate_assignments",
    ),
    path("<int:id>/clear", views.clear_schedule, name="clear_schedule"),
    path("<int:id>/update", views.update_schedule, name="update_schedule"),
    path("<int:id>/pdf", views.pdf, name="pdf"),
]
