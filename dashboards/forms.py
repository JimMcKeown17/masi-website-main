from django import forms
from .models import MentorVisit, School
from django.utils import timezone

class MentorVisitForm(forms.ModelForm):
    visit_date = forms.DateField(
        initial=timezone.now,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    school = forms.ModelChoiceField(
        queryset=School.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    letter_trackers_correct = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    reading_trackers_correct = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    sessions_correct = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    admin_correct = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    quality_rating = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control-range',
            'type': 'range',
            'min': '1',
            'max': '10',
            'step': '1',
            'value': '5'
        })
    )
    
    supplies_needed = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'List any supplies that are needed at this school'
        })
    )
    
    commentary = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Add any additional comments or observations'
        })
    )
    
    class Meta:
        model = MentorVisit
        fields = [
            'visit_date', 
            'school', 
            'letter_trackers_correct', 
            'reading_trackers_correct',
            'sessions_correct',
            'admin_correct',
            'quality_rating',
            'supplies_needed',
            'commentary'
        ]
        
    def __init__(self, *args, **kwargs):
        super(MentorVisitForm, self).__init__(*args, **kwargs)
        # Add Bootstrap form-group classes to all fields
        for field_name, field in self.fields.items():
            if field_name not in ['letter_trackers_correct', 'reading_trackers_correct', 'sessions_correct', 'admin_correct']:
                field.widget.attrs['class'] = 'form-control'