from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, F 
from datetime import date
from .models import Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal, Empresa, Cargo, AreaDeTrabajo,ReporteDiarioMaquinaria
from .utils import calcular_avance_diario
from .forms import ReporteMaquinariaForm

# --- Función de Ayuda para Seguridad ---
def es_staff(user):
    return user.is_staff

# --- Vistas para Avances de Actividades ---

def registrar_avance(request):
    if request.method == 'POST':
        actividad_id = request.POST.get('actividad')
        fecha_reporte = request.POST.get('fecha_reporte')
        cantidad_realizada = request.POST.get('cantidad_realizada')

        if not all([actividad_id, fecha_reporte, cantidad_realizada]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return redirect('registrar_avance')

        actividad_obj = get_object_or_404(Actividad, pk=actividad_id)
        
        meta_programada = calcular_avance_diario(
            actividad_obj.fecha_inicio_programada,
            actividad_obj.fecha_fin_programada,
            actividad_obj.meta_cantidad_total
        )
        AvanceDiario.objects.create(
            actividad=actividad_obj,
            fecha_reporte=fecha_reporte,
            cantidad_programada_dia=meta_programada,
            cantidad_realizada_dia=cantidad_realizada
        )
        messages.success(request, '¡El avance ha sido registrado con éxito!')
        return redirect('registrar_avance')
    else:
        partidas = PartidaActividad.objects.all()
        partida_seleccionada_id = request.GET.get('partida_filtro')

        actividades_filtradas = None
        if partida_seleccionada_id:
            actividades_filtradas = Actividad.objects.filter(partida_id=partida_seleccionada_id)

        contexto = {
            'partidas': partidas,
            'actividades': actividades_filtradas,
            'partida_seleccionada_id': partida_seleccionada_id,
        }
        return render(request, 'actividades/registrar_avance.html', contexto)


def lista_avances(request):
    # --- LÓGICA DE FILTROS (sin cambios) ---
    semanas = Semana.objects.all()
    todas_las_actividades = Actividad.objects.all()
    semana_seleccionada_id = request.GET.get('semana_filtro')
    actividad_seleccionada_id = request.GET.get('actividad_filtro')
    
    avances = AvanceDiario.objects.all().order_by('-fecha_reporte')
    unidad_filtrada = None

    if semana_seleccionada_id:
        try:
            semana_obj = Semana.objects.get(pk=semana_seleccionada_id)
            avances = avances.filter(fecha_reporte__gte=semana_obj.fecha_inicio, fecha_reporte__lte=semana_obj.fecha_fin)
        except Semana.DoesNotExist: pass
    
    if actividad_seleccionada_id:
        avances = avances.filter(actividad_id=actividad_seleccionada_id)
        try:
            unidad_filtrada = Actividad.objects.get(pk=actividad_seleccionada_id).unidad_medida
        except Actividad.DoesNotExist: pass

    # --- CÁLCULO DE TOTALES (sin cambios) ---
    total_real = avances.aggregate(total=Sum('cantidad_realizada_dia'))['total'] or 0
    avances_para_programado = avances.filter(fecha_reporte__lte=F('actividad__fecha_fin_programada'))
    total_programado_a_la_fecha = avances_para_programado.filter(fecha_reporte__lte=date.today()).aggregate(total=Sum('cantidad_programada_dia'))['total'] or 0

    # --- NUEVO: CÁLCULO DEL RENDIMIENTO ---
    rendimiento = 0
    if total_programado_a_la_fecha > 0:
        rendimiento = (total_real / total_programado_a_la_fecha) * 100
    # ------------------------------------

    contexto = {
        'avances': avances,
        'semanas': semanas,
        'todas_las_actividades': todas_las_actividades,
        'semana_seleccionada_id': semana_seleccionada_id,
        'actividad_seleccionada_id': actividad_seleccionada_id,
        'total_real_acumulado': total_real,
        'total_programado_acumulado': total_programado_a_la_fecha,
        'unidad_filtrada': unidad_filtrada,
        'rendimiento': rendimiento, # Añadimos el rendimiento al contexto
    }
    
    return render(request, 'actividades/lista_avances.html', contexto)


@login_required
@user_passes_test(es_staff)
def editar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    if request.method == 'POST':
        avance.fecha_reporte = request.POST['fecha_reporte']
        avance.cantidad_realizada_dia = request.POST['cantidad_realizada']
        avance.save()
        messages.success(request, '¡El avance ha sido actualizado con éxito!')
        return redirect('lista_avances')
    
    contexto = {'avance': avance}
    return render(request, 'actividades/editar_avance.html', contexto)


@login_required
@user_passes_test(es_staff)
def borrar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    if request.method == 'POST':
        avance.delete()
        messages.success(request, 'El registro ha sido eliminado.')
        return redirect('lista_avances')

    contexto = {'avance': avance}
    return render(request, 'actividades/confirmar_borrado.html', contexto)

def registrar_reporte_maquinaria(request):
    # Si el usuario está enviando el formulario (método POST)
    if request.method == 'POST':
        # Creamos una instancia del formulario con los datos enviados
        form = ReporteMaquinariaForm(request.POST)
        
        # Verificamos si los datos son válidos
        if form.is_valid():
            # Guardamos el nuevo reporte en la base de datos
            form.save() 
            # Añadimos un mensaje de éxito (opcional pero recomendado)
            messages.success(request, '¡Reporte de maquinaria guardado exitosamente!')
            # Redirigimos al mismo formulario para que puedan cargar otro
            return redirect('registrar_reporte_maquinaria')
    
    # Si es la primera vez que se carga la página (método GET)
    else:
        # Creamos un formulario vacío
        form = ReporteMaquinariaForm()

    # Renderizamos la plantilla HTML, pasándole el formulario
    return render(request, 'actividades/reporte_maquinaria_form.html', {
        'form': form,
        'titulo': "Registrar Nuevo Reporte de Maquinaria"
    })