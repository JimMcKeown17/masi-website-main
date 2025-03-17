import plotly.express as px
import plotly.io as pio

def create_job_title_chart(job_title_counts):
    """Create a pie chart of job titles"""
    if job_title_counts is None or job_title_counts.empty:
        return None
    
    # Create Plotly pie chart
    fig = px.pie(
        values=job_title_counts.values, 
        names=job_title_counts.index, 
        title='Active Youth by Job Title'
    )
    
    # Customize the chart
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        title_x=0.5,  # Center the title
        margin=dict(t=50, b=50, l=50, r=50)
    )
    
    # Convert the Plotly figure to HTML
    return pio.to_html(fig, full_html=False)