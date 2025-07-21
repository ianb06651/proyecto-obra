# En el archivo actividades/admin.py

from django.contrib import admin
from .models import Actividad, AvanceDiario, Semana, Empresa, Cargo, ReportePersonal,TipoMaquinaria,ReporteDiarioMaquinaria

# Register your models here.

admin.site.register(Actividad)
admin.site.register(AvanceDiario)
admin.site.register(Semana)
admin.site.register(Empresa)
admin.site.register(Cargo)
admin.site.register(ReportePersonal)
admin.site.register(TipoMaquinaria)
admin.site.register(ReporteDiarioMaquinaria)

