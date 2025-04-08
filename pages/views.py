from django.shortcuts import render

def home(request):
    return render(request, 'pages/home.html')

def about(request):
    return render(request, 'pages/about.html')

def children(request):
    return render(request, 'pages/children.html')

def youth(request):
    return render(request, 'pages/youth.html')

def impact(request):
    return render(request, 'pages/impact.html')

def data(request):
    return render(request, 'pages/data.html')

# pages/views.py
def donate(request):
    logos = [
        {'filename': 'logo-dgmt.jpg', 'name': 'DGMT'},
        {'filename': 'logo-MIT.png', 'name': 'MIT'},
        {'filename': 'logo-DoE.png', 'name': 'Department of Education'},
        {'filename': 'logo-tlt.png', 'name': 'TLT'},
        {'filename': 'logo-vw.png', 'name': 'VW'},
        {'filename': 'logo-DoE-national.jpeg', 'name': 'DoE National'},
        {'filename': 'logo-dd.png', 'name': 'DD'},
        {'filename': 'logo-yebo.png', 'name': 'Yebo'},
        {'filename': 'logo-fh.png', 'name': 'FH'},
        {'filename': 'logo-khipu.png', 'name': 'Khipu'},
        {'filename': 'logo-kwf.png', 'name': 'KWF'},
        {'filename': 'logo-masifunde.png', 'name': 'Masifunde'},
        {'filename': 'logo-nlc.png', 'name': 'NLC'},
        {'filename': 'logo-shine.png', 'name': 'Shine'},
        {'filename': 'logo-tdh.png', 'name': 'TDH'},
        {'filename': 'logo-tsi.png', 'name': 'TSI'},
        {'filename': 'logo-uts.png', 'name': 'UTS'},
    ]
    return render(request, 'pages/donate.html', {'logos': logos})

def top_learner(request):
    return render(request, 'pages/top_learner.html')

def apply(request):
    return render(request, 'pages/apply.html')

def where(request):
    return render(request, 'pages/where.html')

def masi_map_satellite(request):
    return render(request, 'pages/masi_map_satellite.html')