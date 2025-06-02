from django import forms
from api.models import MentorVisit, School, YeboVisit, ThousandStoriesVisit, WELA_assessments

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

class YeboVisitForm(forms.ModelForm):
    class Meta:
        model = YeboVisit
        fields = ['visit_date', 'school', 'paired_reading_took_place', 'paired_reading_tracking_updated', 
                  'afternoon_session_quality', 'commentary']
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
            'paired_reading_took_place': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'paired_reading_tracking_updated': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'afternoon_session_quality': forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range',
                'min': '1',
                'max': '10',
                'step': '1',
                'value': '5',
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
            'paired_reading_took_place': 'Did paired reading take place?',
            'paired_reading_tracking_updated': 'Paired reading tracking up to date',
            'afternoon_session_quality': 'Afternoon session quality',
            'commentary': 'Commentary',
        }

class ThousandStoriesVisitForm(forms.ModelForm):
    class Meta:
        model = ThousandStoriesVisit
        fields = ['visit_date', 'school', 'library_neat_and_tidy', 'tracking_sheets_up_to_date', 
                  'book_boxes_and_borrowing', 'daily_target_met', 'story_time_quality', 'other_comments']
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
            'library_neat_and_tidy': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'tracking_sheets_up_to_date': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'book_boxes_and_borrowing': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'daily_target_met': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'story_time_quality': forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range',
                'min': '1',
                'max': '10',
                'step': '1',
                'value': '5',
            }),
            'other_comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '5',
                'placeholder': 'Add any additional comments or observations',
                'maxlength': '1000',
            }),
        }
        labels = {
            'visit_date': 'Visit Date',
            'school': 'School Visited',
            'library_neat_and_tidy': 'Is the library neat and tidy?',
            'tracking_sheets_up_to_date': 'Are all tracking sheets up to date?',
            'book_boxes_and_borrowing': 'Is book boxes and book borrowing taking place?',
            'daily_target_met': 'Daily target of stories read is met?',
            'story_time_quality': 'Quality of Story time session',
            'other_comments': 'Other comments',
        }