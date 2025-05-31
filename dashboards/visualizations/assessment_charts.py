# dashboard/visualizations/assessment_charts.py

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from django.db.models import Avg, Count, Q
from api.models import WELA_assessments

class AssessmentCharts:
    
    @staticmethod
    def get_progress_over_time_chart(year=None, school=None, grade=None):
        """Create a line chart showing average scores across Jan, June, Nov"""
        
        queryset = WELA_assessments.objects.all()
        
        if year:
            queryset = queryset.filter(assessment_year=year)
        if school:
            queryset = queryset.filter(school__icontains=school)
        if grade:
            queryset = queryset.filter(grade=grade)
        
        # Get aggregated data
        jan_avg = queryset.aggregate(avg=Avg('jan_total'))['avg'] or 0
        june_avg = queryset.aggregate(avg=Avg('june_total'))['avg'] or 0
        nov_avg = queryset.aggregate(avg=Avg('nov_total'))['avg'] or 0
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=['January', 'June', 'November'],
            y=[jan_avg, june_avg, nov_avg],
            mode='lines+markers',
            name='Average Scores',
            line=dict(color='#2E86AB', width=3),
            marker=dict(size=10)
        ))
        
        fig.update_layout(
            title='Student Progress Over Academic Year',
            xaxis_title='Assessment Period',
            yaxis_title='Average Total Score',
            template='plotly_white',
            height=400
        )
        
        return fig.to_html(include_plotlyjs=True)
    
    @staticmethod
    def get_school_comparison_chart(year=None):
        """Create bar chart comparing schools by average improvement"""
        
        queryset = WELA_assessments.objects.all()
        if year:
            queryset = queryset.filter(assessment_year=year)
        
        # Calculate improvement by school
        school_data = []
        schools = queryset.values_list('school', flat=True).distinct()
        
        for school in schools:
            school_students = queryset.filter(school=school)
            
            # Calculate average improvement (Nov - Jan)
            improvements = []
            for student in school_students:
                if student.jan_total is not None and student.nov_total is not None:
                    improvements.append(student.nov_total - student.jan_total)
            
            if improvements:
                avg_improvement = sum(improvements) / len(improvements)
                school_data.append({
                    'school': school,
                    'avg_improvement': avg_improvement,
                    'student_count': len(improvements)
                })
        
        if not school_data:
            return "<p>No data available for school comparison</p>"
        
        # Sort by improvement
        school_data.sort(key=lambda x: x['avg_improvement'], reverse=True)
        
        schools = [d['school'] for d in school_data]
        improvements = [d['avg_improvement'] for d in school_data]
        
        fig = go.Figure(data=[
            go.Bar(
                x=schools,
                y=improvements,
                marker_color=['#A23B72' if x >= 0 else '#F18F01' for x in improvements],
                text=[f"+{x:.1f}" if x >= 0 else f"{x:.1f}" for x in improvements],
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title='Average Student Improvement by School',
            xaxis_title='School',
            yaxis_title='Average Score Improvement (Nov - Jan)',
            template='plotly_white',
            height=500,
            xaxis={'tickangle': 45}
        )
        
        return fig.to_html(include_plotlyjs=True)
    
    @staticmethod
    def get_skill_breakdown_chart(year=None, period='nov'):
        """Create radar chart showing average performance by skill area"""
        
        queryset = WELA_assessments.objects.all()
        if year:
            queryset = queryset.filter(assessment_year=year)
        
        # Define skill fields based on period
        skill_fields = {
            'jan': {
                'Letter Sounds': 'jan_letter_sounds',
                'Story Comprehension': 'jan_story_comprehension', 
                'Listen First Sound': 'jan_listen_first_sound',
                'Listen Words': 'jan_listen_words',
                'Writing Letters': 'jan_writing_letters',
                'Read Words': 'jan_read_words',
                'Read Sentences': 'jan_read_sentences',
                'Read Story': 'jan_read_story',
                'Write CVCs': 'jan_write_cvcs',
                'Write Sentences': 'jan_write_sentences',
                'Write Story': 'jan_write_story'
            },
            'june': {
                'Letter Sounds': 'june_letter_sounds',
                'Story Comprehension': 'june_story_comprehension',
                'Listen First Sound': 'june_listen_first_sound',
                'Listen Words': 'june_listen_words', 
                'Writing Letters': 'june_writing_letters',
                'Read Words': 'june_read_words',
                'Read Sentences': 'june_read_sentences',
                'Read Story': 'june_read_story',
                'Write CVCs': 'june_write_cvcs',
                'Write Sentences': 'june_write_sentences',
                'Write Story': 'june_write_story'
            },
            'nov': {
                'Letter Sounds': 'nov_letter_sounds',
                'Story Comprehension': 'nov_story_comprehension',
                'Listen First Sound': 'nov_listen_first_sound',
                'Listen Words': 'nov_listen_words',
                'Writing Letters': 'nov_writing_letters',
                'Read Words': 'nov_read_words',
                'Read Sentences': 'nov_read_sentences',
                'Read Story': 'nov_read_story', 
                'Write CVCs': 'nov_write_cvcs',
                'Write Sentences': 'nov_write_sentences',
                'Write Story': 'nov_write_story'
            }
        }
        
        skills = skill_fields.get(period, skill_fields['nov'])
        
        # Calculate averages for each skill
        averages = []
        labels = []
        
        for skill_name, field_name in skills.items():
            avg = queryset.aggregate(avg=Avg(field_name))['avg']
            if avg is not None:
                averages.append(avg)
                labels.append(skill_name)
        
        if not averages:
            return "<p>No skill data available</p>"
        
        # Create radar chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=averages,
            theta=labels,
            fill='toself',
            name=f'{period.title()} Averages',
            line_color='#2E86AB'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, max(averages) * 1.1] if averages else [0, 100]
                )),
            showlegend=True,
            title=f'Skill Performance Breakdown - {period.title()}',
            height=600
        )
        
        return fig.to_html(include_plotlyjs=True)
    
    @staticmethod
    def get_grade_performance_chart(year=None):
        """Create box plot showing performance distribution by grade"""
        
        queryset = WELA_assessments.objects.all()
        if year:
            queryset = queryset.filter(assessment_year=year)
        
        # Get data by grade
        grades = queryset.values_list('grade', flat=True).distinct()
        
        fig = go.Figure()
        
        for grade in grades:
            grade_students = queryset.filter(grade=grade)
            nov_scores = [s.nov_total for s in grade_students if s.nov_total is not None]
            
            if nov_scores:
                fig.add_trace(go.Box(
                    y=nov_scores,
                    name=grade,
                    boxpoints='outliers'
                ))
        
        fig.update_layout(
            title='Score Distribution by Grade (November Assessment)',
            xaxis_title='Grade',
            yaxis_title='Total Score',
            template='plotly_white',
            height=500
        )
        
        return fig.to_html(include_plotlyjs=True)
    
    @staticmethod
    def get_summary_stats(year=None):
        """Get summary statistics for the dashboard"""
        
        queryset = WELA_assessments.objects.all()
        if year:
            queryset = queryset.filter(assessment_year=year)
        
        total_students = queryset.count()
        
        # Students with improvement data
        students_with_data = queryset.filter(
            jan_total__isnull=False,
            nov_total__isnull=False
        )
        
        # Calculate improvements
        improvements = []
        for student in students_with_data:
            improvement = student.nov_total - student.jan_total
            improvements.append(improvement)
        
        if improvements:
            avg_improvement = sum(improvements) / len(improvements)
            improved_count = len([x for x in improvements if x > 0])
            improvement_rate = (improved_count / len(improvements)) * 100
        else:
            avg_improvement = 0
            improvement_rate = 0
        
        # Get latest averages
        jan_avg = queryset.aggregate(avg=Avg('jan_total'))['avg'] or 0
        nov_avg = queryset.aggregate(avg=Avg('nov_total'))['avg'] or 0
        
        return {
            'total_students': total_students,
            'avg_improvement': round(avg_improvement, 1),
            'improvement_rate': round(improvement_rate, 1),
            'jan_average': round(jan_avg, 1),
            'nov_average': round(nov_avg, 1),
            'schools_count': queryset.values('school').distinct().count(),
            'grades_count': queryset.values('grade').distinct().count()
        }