# En el nuevo archivo actividades/utils.py

from datetime import date, timedelta

def calcular_avance_diario(fecha_inicio, fecha_fin, meta_total):
    dias_habiles = 0
    dias_totales = (fecha_fin - fecha_inicio).days + 1
    
    if dias_totales <= 0:
        return 0

    for i in range(dias_totales):
        dia_actual = fecha_inicio + timedelta(days=i)
        if dia_actual.weekday() != 6: # 6 es Domingo
            dias_habiles += 1
            
    if dias_habiles == 0:
        return 0

    meta_diaria = meta_total / dias_habiles
    return round(meta_diaria, 2)