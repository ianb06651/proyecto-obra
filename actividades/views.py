# actividades/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, timedelta
from django.db.models import Q

# Importamos todos los modelos necesarios
from .models import (
    Actividad, Proyecto, AvanceDiario, ReporteDiarioMaquinaria, 
    ReportePersonal, ReporteClima, Observacion, AreaDeTrabajo,
    Cronograma, CronogramaPorZona, ElementoConstructivo, 
    AvanceProcesoElemento
)
# Importamos los forms (asegúrate de que forms.py esté actualizado como vimos antes)
from .forms import (
    CronogramaForm, CronogramaPorZonaForm, ObservacionForm
    # Agrega aquí tus otros forms si los usas (AvanceDiarioForm, etc.)
)

# ==========================================
# SECCIÓN CRONOGRAMA (LÓGICA ACTUALIZADA)
# ==========================================

def vista_cronograma(request):
    """
    Muestra el cronograma filtrado POR ZONA.
    Es vital para ver las fechas correctas de cada área.
    """
    proyecto = Proyecto.objects.first() # Ajustar lógica de proyecto si tienes sesiones
    zonas = AreaDeTrabajo.objects.all()
    
    # 1. Determinar qué zona mostrar
    zona_id = request.GET.get('zona')
    zona_seleccionada = None

    if zona_id:
        zona_seleccionada = get_object_or_404(AreaDeTrabajo, pk=zona_id)
    elif zonas.exists():
        zona_seleccionada = zonas.first()

    # 2. Filtrar actividades (objetos 'CronogramaPorZona')
    actividades_zona = []
    if zona_seleccionada:
        actividades_zona = CronogramaPorZona.objects.filter(
            zona=zona_seleccionada,
            tarea__proyecto=proyecto
        ).select_related('tarea', 'tarea__padre').order_by('fecha_inicio_prog')

    context = {
        'actividades': actividades_zona,
        'zonas': zonas,
        'zona_seleccionada': zona_seleccionada,
        'proyecto': proyecto,
    }
    return render(request, 'actividades/cronograma_list.html', context)

def crear_tarea_cronograma(request):
    """
    Crea una tarea MAESTRA y sus respectivas copias en CronogramaPorZona.
    """
    proyecto = Proyecto.objects.first() 
    
    if request.method == 'POST':
        # Pasamos el proyecto_id al form para filtrar el padre correctamente
        form = CronogramaForm(request.POST, proyecto_id=proyecto.id if proyecto else None)
        if form.is_valid():
            # 1. Guardar la tarea maestra (nombre, padre, jerarquía)
            nueva_tarea = form.save(commit=False)
            if proyecto:
                nueva_tarea.proyecto = proyecto
            nueva_tarea.save()

            # 2. Obtener las zonas donde aplica esta tarea
            zonas_elegidas = form.cleaned_data['zonas_aplicables']

            # 3. Crear los registros de fechas para cada zona
            registros_zona = []
            for zona in zonas_elegidas:
                registros_zona.append(
                    CronogramaPorZona(tarea=nueva_tarea, zona=zona)
                )
            # Bulk create es más eficiente que guardar uno por uno
            CronogramaPorZona.objects.bulk_create(registros_zona)

            messages.success(request, f"Actividad '{nueva_tarea.nombre}' creada y asignada a {len(zonas_elegidas)} zonas.")
            return redirect('actividades:cronograma_list')
    else:
        form = CronogramaForm(proyecto_id=proyecto.id if proyecto else None)

    return render(request, 'actividades/cronograma_crear.html', {'form': form})

def editar_fechas_cronograma(request, pk):
    """
    Edita las fechas de UNA actividad en UNA zona específica.
    pk: ID de CronogramaPorZona (NO de la tarea maestra)
    """
    registro_zona = get_object_or_404(CronogramaPorZona, pk=pk)

    if request.method == 'POST':
        form = CronogramaPorZonaForm(request.POST, instance=registro_zona)
        if form.is_valid():
            form.save()
            messages.success(request, "Fechas actualizadas correctamente.")
            # Redirigimos a la lista manteniendo el filtro de la zona actual
            return redirect(f"{reverse('actividades:cronograma_list')}?zona={registro_zona.zona.id}")
    else:
        form = CronogramaPorZonaForm(instance=registro_zona)

    return render(request, 'actividades/cronograma_form.html', {
        'form': form,
        'actividad': registro_zona, # Para mostrar "Editando X en Zona Y"
        'titulo': f"Editar {registro_zona.tarea.nombre} - {registro_zona.zona.nombre}"
    })

def eliminar_tarea_cronograma(request, pk):
    """
    Elimina la Tarea Maestra completa.
    Esto borrará la tarea de TODAS las zonas (por el on_delete=CASCADE).
    pk: ID de Cronograma (Tarea Maestra)
    """
    tarea = get_object_or_404(Cronograma, pk=pk)
    
    if request.method == 'POST':
        tarea.delete()
        messages.success(request, "Actividad eliminada de todas las zonas.")
        return redirect('actividades:cronograma_list')

    return render(request, 'actividades/confirmar_borrado.html', {'object': tarea})

# --- APIs del Cronograma (Adaptadas) ---

def api_hijos_cronograma(request, padre_id):
    """Retorna hijos directos. Útil para carga dinámica."""
    hijos = Cronograma.objects.filter(padre_id=padre_id).values('id', 'nombre')
    return JsonResponse(list(hijos), safe=False)

def api_detalle_tarea(request, tarea_id):
    """
    Retorna detalles. Si se pasa 'zona_id', retorna fechas específicas.
    """
    zona_id = request.GET.get('zona_id')
    tarea = get_object_or_404(Cronograma, pk=tarea_id)
    
    data = {'id': tarea.id, 'nombre': tarea.nombre}
    
    if zona_id:
        detalle_zona = CronogramaPorZona.objects.filter(tarea=tarea, zona_id=zona_id).first()
        if detalle_zona:
            data.update({
                'inicio_prog': detalle_zona.fecha_inicio_prog,
                'fin_prog': detalle_zona.fecha_fin_prog,
                'estado': detalle_zona.estado_calculado
            })
    
    return JsonResponse(data)

def vista_cronograma_movil(request):
    """Vista simplificada para móviles."""
    zonas = AreaDeTrabajo.objects.all()
    return render(request, 'actividades/cronograma_actualizar_movil.html', {'zonas': zonas})


# ==========================================
# SECCIÓN OBSERVACIONES (NUEVA)
# ==========================================

def lista_observaciones(request):
    # Ordenamos por no resueltas primero, luego por fecha
    observaciones = Observacion.objects.all().order_by('resuelto', '-fecha')
    return render(request, 'actividades/observacion_list.html', {'observaciones': observaciones})

def crear_observacion(request):
    if request.method == 'POST':
        form = ObservacionForm(request.POST, request.FILES)
        if form.is_valid():
            obs = form.save(commit=False)
            # Si tienes autenticación de usuario: obs.usuario = request.user
            obs.save()
            messages.success(request, "Observación registrada correctamente.")
            return redirect('actividades:lista_observaciones')
    else:
        form = ObservacionForm()
    return render(request, 'actividades/observacion_form.html', {'form': form})

def marcar_observacion_resuelta(request, pk):
    observacion = get_object_or_404(Observacion, pk=pk)
    observacion.resuelto = True
    observacion.fecha_resolucion = timezone.now().date()
    if request.user.is_authenticated:
        observacion.resuelto_por = request.user
    observacion.save()
    messages.success(request, "Observación marcada como resuelta.")
    return redirect('actividades:lista_observaciones')

def eliminar_observacion(request, pk):
    observacion = get_object_or_404(Observacion, pk=pk)
    if request.method == 'POST':
        observacion.delete()
        messages.success(request, "Observación eliminada.")
        return redirect('actividades:lista_observaciones')
    return render(request, 'actividades/observacion_confirmar_borrado.html', {'observacion': observacion})


# ==========================================
# SECCIÓN GENERAL (VIEWS EXISTENTES)
# ==========================================

def pagina_principal(request):
    # Obtenemos el primer proyecto disponible (asumiendo que solo trabajas con uno a la vez)
    proyecto = Proyecto.objects.first()
    
    context = {
        'proyecto': proyecto
    }
    return render(request, 'actividades/principal.html', context)

def vista_clima(request):
    reportes = ReporteClima.objects.all().order_by('-fecha')[:7]
    return render(request, 'actividades/vista_clima.html', {'reportes': reportes})

# --- WBS / Actividad (Vistas basadas en clases - CBV) ---
class ActividadListView(ListView):
    model = Actividad
    template_name = 'actividades/actividad_list.html'

class ActividadCreateView(CreateView):
    model = Actividad
    fields = ['nombre', 'padre', 'proyecto', 'unidad_medida'] # Ajustar campos según modelo
    template_name = 'actividades/actividad_form.html'
    success_url = reverse_lazy('actividades:actividad_list')

class ActividadUpdateView(UpdateView):
    model = Actividad
    fields = ['nombre', 'padre', 'unidad_medida']
    template_name = 'actividades/actividad_form.html'
    success_url = reverse_lazy('actividades:actividad_list')

# --- Avances y Reportes (Stubs funcionales) ---
# Nota: Si tenías forms personalizados para esto, impórtalos arriba.

def registrar_avance(request):
    # Lógica estándar de registro de avance
    return render(request, 'actividades/registrar_avance.html')

def editar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    # Lógica de edición
    return render(request, 'actividades/editar_avance.html', {'avance': avance})

def borrar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    if request.method == 'POST':
        avance.delete()
        return redirect('actividades:historial_avance', proyecto_id=avance.actividad.proyecto.id)
    return render(request, 'actividades/confirmar_borrado.html', {'object': avance})

def historial_avance_view(request, proyecto_id):
    avances = AvanceDiario.objects.filter(actividad__proyecto_id=proyecto_id).order_by('-fecha_reporte')
    return render(request, 'actividades/historial_avance.html', {'avances': avances})

def registrar_reporte_maquinaria(request):
    # Lógica de reporte maquinaria
    return render(request, 'actividades/reporte_maquinaria_form.html')

def editar_reporte_maquinaria(request, pk):
    reporte = get_object_or_404(ReporteDiarioMaquinaria, pk=pk)
    return render(request, 'actividades/reporte_maquinaria_form.html', {'reporte': reporte})

def registrar_reporte_personal(request):
    # Lógica de reporte personal
    return render(request, 'actividades/reporte_personal_form.html')


# ==========================================
# SECCIÓN BIM (APIs y Vistas)
# ==========================================

def registrar_avance_bim(request):
    return render(request, 'actividades/registrar_avance_bim.html')

from django.views import View
class ElementoStatusAPIView(View):
    def get(self, request):
        return JsonResponse({'status': 'ok'})

def buscar_elementos_constructivos(request):
    q = request.GET.get('q', '')
    elementos = ElementoConstructivo.objects.filter(
        Q(identificador_unico__icontains=q) | Q(guids_bim__identificador_bim__icontains=q)
    ).distinct()[:20]
    data = [{'id': e.id, 'text': e.identificador_unico} for e in elementos]
    return JsonResponse({'results': data})

def obtener_pasos_y_avance_elemento(request, elemento_id):
    elemento = get_object_or_404(ElementoConstructivo, pk=elemento_id)
    pasos = elemento.tipo_elemento.pasos_proceso.all().order_by('orden')
    avances = {av.paso_proceso_id: av.fecha_finalizacion for av in elemento.avances_proceso.all()}
    
    data_pasos = []
    for paso in pasos:
        data_pasos.append({
            'id': paso.id,
            'nombre': paso.proceso.nombre,
            'completado': paso.id in avances,
            'fecha': avances.get(paso.id)
        })
    return JsonResponse({'elemento': elemento.identificador_unico, 'pasos': data_pasos})

def api_generar_rango(request):
    return JsonResponse({'status': 'not_implemented'})