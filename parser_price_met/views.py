from django.shortcuts import render
from django.http import HttpResponse
from django.db import connections
import openpyxl
from io import BytesIO
from datetime import datetime

def format_date(date_str):
    if date_str:
        try:
            date_obj = datetime.strptime(str(date_str), '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return str(date_str)
    return ''

def get_stats():
    with connections['platferrum'].cursor() as cursor:
        cursor.execute("SELECT COUNT(DISTINCT name) FROM prices")
        total_items = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM prices")
        total_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(date), MAX(date) FROM prices")
        first_date, last_date = cursor.fetchone()
        
    return {
        'total_items': total_items,
        'total_records': total_records,
        'first_date': format_date(first_date),
        'last_date': format_date(last_date)
    }

def price_analysis(request):
    if request.GET.get('download') == 'true':
        with connections['platferrum'].cursor() as cursor:
            cursor.execute("""
                SELECT name, type, unit_price, sign_nat,
                       strftime('%d.%m.%Y', date) as formatted_date
                FROM prices
                ORDER BY date DESC, name ASC
            """)
            rows = cursor.fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Наименование', 'Тип', 'Цена', 'Ед.изм.', 'Дата'])
        
        for row in rows:
            name, type_, price, sign, date = row
            ws.append([name, type_, price, sign, date])  # date уже отформатирована в SQL

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=prices_full.xlsx'
        return response

    stats = get_stats()
    return render(request, 'parser_price_met/price_analysis.html', {'stats': stats})
