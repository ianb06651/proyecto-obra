import requests
from datetime import datetime, time
from django.conf import settings
from .models import ReporteClima

# Definimos el horario laboral
HORA_INICIO_LABORAL = time(8, 0)
HORA_FIN_LABORAL = time(18, 0)

def obtener_y_guardar_clima(fecha):
    """
    Obtiene el clima para una fecha dada desde el API, lo procesa y lo guarda en la BD.
    Si ya existe un registro para esa fecha, lo devuelve directamente.
    """
    # 1. Revisa si ya tenemos los datos en nuestra base
    try:
        reporte = ReporteClima.objects.get(fecha=fecha)
        print(f"Datos para {fecha} encontrados en la base de datos.")
        return reporte
    except ReporteClima.DoesNotExist:
        print(f"No hay datos para {fecha}. Consultando API...")

    # 2. Si no, consulta el API
    date_str = fecha.strftime('%Y-%m-%d')
    params = {
        'key': settings.WEATHER_API_KEY, 
        'q': '19.31418,-97.86485',
        'dt': date_str
    }
    
    try:
        response = requests.get('http://api.weatherapi.com/v1/history.json', params=params)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f'Error al obtener datos del API para {date_str}: {e}')
        return None

    # 3. Procesa los datos del JSON
    forecast_day = data['forecast']['forecastday'][0]['day']
    hourly_data = data['forecast']['forecastday'][0]['hour']
    
    precip_laboral = 0
    precip_no_laboral = 0
    sensacion_max_laboral = -100 # Empezamos con un número muy bajo

    for hora in hourly_data:
        hora_actual = datetime.strptime(hora['time'], '%Y-%m-%d %H:%M').time()
        
        if HORA_INICIO_LABORAL <= hora_actual <= HORA_FIN_LABORAL:
            precip_laboral += hora['precip_mm']
            if hora['feelslike_c'] > sensacion_max_laboral:
                sensacion_max_laboral = hora['feelslike_c']
        else:
            precip_no_laboral += hora['precip_mm']
            
    # 4. Guarda el nuevo reporte en la base de datos
    nuevo_reporte = ReporteClima.objects.create(
        fecha=fecha,
        temp_max_c=forecast_day['maxtemp_c'],
        temp_min_c=forecast_day['mintemp_c'],
        sensacion_max_c=sensacion_max_laboral,
        precipitacion_total_mm=forecast_day['totalprecip_mm'],
        precipitacion_laboral_mm=precip_laboral,
        precipitacion_no_laboral_mm=precip_no_laboral,
        condicion_texto=forecast_day['condition']['text'],
        condicion_icono=forecast_day['condition']['icon']
    )
    print(f"Datos para {fecha} guardados en la base de datos.")
    return nuevo_reporte