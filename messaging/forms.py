from django import forms

from messaging.models import EmailTemplate


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ["name", "subject", "body"]
        widgets = {
            "subject": forms.TextInput(attrs={"maxlength": 200}),
            "body": forms.Textarea(attrs={"rows": 12}),
        }
