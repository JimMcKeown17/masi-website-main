from django import forms
from api.models import MentorVisit

class MentorVisitForm(forms.ModelForm):
    class Meta:
        model = MentorVisit
        fields = ['visit_date', 'school', 'letter_trackers_correct', 'reading_trackers_correct', 
                  'sessions_correct', 'admin_correct', 'quality_rating', 'supplies_needed', 'commentary']
        widgets = {
            'visit_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': True,
            }),
            'school': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'letter_trackers_correct': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'reading_trackers_correct': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'sessions_correct': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'admin_correct': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'quality_rating': forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range',
                'min': '1',
                'max': '10',
                'step': '1',
                'value': '5',
            }),
            'supplies_needed': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '4',
                'placeholder': 'List any supplies that are needed at this school',
                'maxlength': '500',
            }),
            'commentary': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '5',
                'placeholder': 'Add any additional comments or observations',
                'maxlength': '1000',
            }),
        }
        labels = {
            'visit_date': 'Visit Date',
            'school': 'School Visited',
            'letter_trackers_correct': 'Letter trackers correct',
            'reading_trackers_correct': 'Reading trackers correct',
            'sessions_correct': 'Sessions correct',
            'admin_correct': 'Admin correct',
            'quality_rating': 'Quality Rating',
            'supplies_needed': 'Supplies Needed',
            'commentary': 'Commentary',
        }