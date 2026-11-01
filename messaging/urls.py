from django.urls import path

from messaging import views

app_name = "messaging"

urlpatterns = [
    path("", views.messaging_home, name="home"),
    path("email/new/", views.new_email, name="new_email"),
    path("email/compose/", views.compose, name="compose"),
    path("email/preview/", views.preview, name="preview"),
    path("email/send/", views.send, name="send"),
    path("email/send-test/", views.send_test, name="send_test"),
    path("email/templates/", views.template_list, name="template_list"),
    path("email/templates/new/", views.template_create, name="template_create"),
    path("email/templates/<int:pk>/", views.template_edit, name="template_edit"),
    path("email/sent/", views.sent_list, name="sent_list"),
    path("email/sent/<int:pk>/", views.sent_detail, name="sent_detail"),
    path("email/reminders/", views.reminders, name="reminders"),
]
