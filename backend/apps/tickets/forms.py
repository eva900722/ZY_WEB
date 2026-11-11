from django import forms
from apps.accounts.models import User


class TicketForm(forms.Form):
    title = forms.CharField(label="問題摘要", max_length=200)
    description = forms.CharField(
        label="問題描述", max_length=20000, widget=forms.Textarea
    )
    office = forms.CharField(label="辦公室", max_length=100, required=False)
    anydesk = forms.CharField(label="AnyDesk ID", max_length=50, required=False)
    reporter = forms.ModelChoiceField(label="報修人", queryset=User.objects.none())

    def __init__(self, *args, user, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reporter"].queryset = User.objects.filter(
            company=company,
            is_active=True,
            deleted_at__isnull=True,
            role__in=["reporter", "company_admin"],
        )
        if user.role == "reporter":
            self.fields["reporter"].queryset = self.fields["reporter"].queryset.filter(
                pk=user.pk
            )
            self.fields["reporter"].initial = user
            self.fields["reporter"].disabled = True
        elif user.company_id == company.pk:
            self.fields["reporter"].initial = user
        self.fields["office"].initial = user.office


class EntryForm(forms.Form):
    body = forms.CharField(label="補充說明", max_length=20000, widget=forms.Textarea)
    internal = forms.BooleanField(label="僅贊耀公司可見（內部備註）", required=False)
    revision = forms.IntegerField(widget=forms.HiddenInput)


class AssignmentForm(forms.Form):
    engineer = forms.ModelChoiceField(
        label="負責人",
        queryset=User.objects.filter(
            role="it_admin", is_active=True, deleted_at__isnull=True
        ),
    )
    reason = forms.CharField(label="交接原因", max_length=500)
    revision = forms.IntegerField(widget=forms.HiddenInput)


class StatusForm(forms.Form):
    status = forms.ChoiceField(label="新狀態", choices=[])
    reason = forms.CharField(label="處理說明", max_length=10000, widget=forms.Textarea)
    revision = forms.IntegerField(widget=forms.HiddenInput)
