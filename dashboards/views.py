from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import MentorVisit
from .forms import MentorVisitForm
from .services.airtable_service import fetch_airtable_records
from .services.data_processing import process_airtable_records, get_active_records, count_job_titles
from .visualizations.charts import create_job_title_chart

def dashboard_home(request):
    # Fetch data from Airtable
    records, error = fetch_airtable_records()
    
    if error:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': error,
            'troubleshooting_tips': [
                "Check your .env file is properly formatted",
                "Verify Django is loading your .env file correctly",
                "Make sure the variable names match exactly"
            ]
        })
    
    # Process the records
    df = process_airtable_records(records)
    
    # Check if DataFrame was created successfully
    if df is None or df.empty:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': 'No records found or error processing the data'
        })
    
    # Diagnostic print statements
    print("DataFrame Columns:", list(df.columns))
    print("\nFirst few records:")
    print(df.head())
    
    # Filter for active records
    active_df = get_active_records(df)
    
    # If no active records found
    if active_df is None or active_df.empty:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': 'No active records found. Check your Employment Status column.',
            'diagnostic_info': {
                'columns': list(df.columns),
                'total_records': len(df),
                'status_values': df['Employment Status'].unique().tolist() if 'Employment Status' in df.columns else []
            }
        })
    
    # Count job titles for active records
    job_title_counts = count_job_titles(active_df)
    
    if job_title_counts is None:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': 'Job Title column not found in data',
            'diagnostic_info': {
                'columns': list(active_df.columns),
                'total_records': len(active_df)
            }
        })
    
    # Create visualization
    plot_html = create_job_title_chart(job_title_counts)
    
    # Prepare context to pass to template
    context = {
        'job_title_plot': plot_html,
        'job_title_counts': job_title_counts.to_dict(),
        'total_active_records': len(active_df),
        'total_records': len(df)
    }
    
    return render(request, 'dashboards/dashboard_main.html', context)


@login_required
def mentor_visit(request):
    if request.method == 'POST':
        form = MentorVisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.mentor = request.user
            visit.save()
            messages.success(request, 'Visit report submitted successfully!')
            return redirect('dashboards:visit_list')  # Adjust to your URL pattern
    else:
        form = MentorVisitForm()
    
    return render(request, 'dashboards/mentor_visits.html', {
        'form': form,
        'title': 'Submit School Visit Report'
    })