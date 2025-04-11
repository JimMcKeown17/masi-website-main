from django.shortcuts import render

# Create your views here.
def debug_social(request):
    return render(request, 'debug.html')