from django.shortcuts import render, redirect
from django.http import HttpResponse
import requests
import pandas as pd
from io import BytesIO

ASCON_API_URL = "http://192.168.120.101:3189/v1.0/lm/sessions"

def fetch_ascon_data():
    try:
        resp = requests.get(ASCON_API_URL, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching ASCON data: {e}")
        return None

def process_license_data(data):
    if not data or "sessions" not in data:
        return []
    
    licenses = []
    for s in data["sessions"]:
        license_info = {
            'user': s.get("user", {}).get("name", "unknown"),
            'license_type': s.get("feature", {}).get("name", "unknown"),
            'license_variant': s.get("feature", {}).get("productName", "standard"),
            'host': s.get("host", {}).get("name", "unknown"),
            'ip': s.get("host", {}).get("ip", "unknown"),
            'sessions_count': s.get("feature", {}).get("sessionsCount", 0),
            'max_concurrent': s.get("feature", {}).get("maxConcurrentResource", 0),
            'rest_days': s.get("feature", {}).get("restOfLifeTimeDays", 0)
        }
        licenses.append(license_info)
    return licenses

def index(request):
    return redirect('ascon_lic:licenses')

def licenses_view(request):
    try:
        if request.GET.get('download'):
            data = fetch_ascon_data()
            licenses = process_license_data(data)
            df = pd.DataFrame(licenses)
            excel_file = BytesIO()
            df.to_excel(excel_file, index=False)
            excel_file.seek(0)
            
            response = HttpResponse(content_type='application/vnd.ms-excel')
            response['Content-Disposition'] = 'attachment; filename="licenses.xlsx"'
            response.write(excel_file.getvalue())
            return response
        
        data = fetch_ascon_data()
        licenses = process_license_data(data)
        return render(request, 'ascon_lic/licenses.html', {'licenses': licenses})
    except Exception:
        return redirect('ascon_lic:index')
