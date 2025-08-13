from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, F
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from datetime import date, timedelta, datetime
from django.db import IntegrityError

from .models import (
    Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal, 
    Empresa, Cargo, AreaDeTrabajo, ReporteDiarioMaquinaria, Proyecto
)
from .forms import ReporteMaquinariaForm, ReportePersonalForm, ActividadForm, ConsultaClimaForm
from .services import obtener_y_guardar_clima

def es_staff(user):
    return user.is_staff

def historial_avance_view(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    semanas = Semana.objects.all()
    actividades_filtrables = Actividad.objects.filter(proyecto=proyecto, sub_actividades__isnull=True)
    
    semana_seleccionada_id = request.GET.get('semana_filtro')
    actividad_seleccionada_id = request.GET.get('actividad_filtro')

    avances_reales = AvanceDiario.objects.filter(actividad__proyecto=proyecto)
    
    fecha_corte = date.today()
    actividad_base_calculo = proyecto

    if semana_seleccionada_id:
        try:
            semana_obj = Semana.objects.get(pk=semana_seleccionada_id)
            fecha_corte = semana_obj.fecha_fin
            avances_reales = avances_reales.filter(fecha_reporte__range=[semana_obj.fecha_inicio, semana_obj.fecha_fin])
        except Semana.DoesNotExist:
            pass
    
    actividad_seleccionada = None
    if actividad_seleccionada_id:
        actividad_seleccionada = get_object_or_404(Actividad, pk=actividad_seleccionada_id)
        avances_reales = avances_reales.filter(actividad=actividad_seleccionada)
        actividad_base_calculo = actividad_seleccionada

    total_programado_pv = actividad_base_calculo.get_valor_planeado_a_fecha(fecha_corte)
    total_real_ev = avances_reales.aggregate(total=Sum('cantidad_realizada_dia'))['total'] or 0
    
    rendimiento_spi = (total_real_ev / total_programado_pv * 100) if total_programado_pv > 0 else 0
    
    context = {
        'proyecto': proyecto, 'semanas': semanas, 'actividades_filtrables': actividades_filtrables,
        'semana_seleccionada_id': semana_seleccionada_id, 'actividad_seleccionada_id': actividad_seleccionada_id,
        'actividad_seleccionada': actividad_seleccionada, 'total_programado_pv': total_programado_pv,
        'total_real_ev': total_real_ev, 'rendimiento_spi': rendimiento_spi,
        'fecha_corte': fecha_corte, 'avances_reales': avances_reales.order_by('-fecha_reporte')
    }
    
    return render(request, 'actividades/historial_avance.html', context)

class ActividadListView(ListView):
    model = Actividad
    template_name = 'actividades/actividad_list.html'
    context_object_name = 'actividades'

    def get_queryset(self):
        return Actividad.objects.filter(padre__isnull=True).order_by('nombre')

class ActividadCreateView(CreateView):
    model = Actividad
    form_class = ActividadForm
    template_name = 'actividades/actividad_form.html'
    success_url = reverse_lazy('actividad_list')

    def get_initial(self):
        initial = super().get_initial()
        padre_id = self.request.GET.get('padre')
        if padre_id:
            initial['padre'] = get_object_or_404(Actividad, pk=padre_id)
        return initial

class ActividadUpdateView(UpdateView):
    model = Actividad
    form_class = ActividadForm
    template_name = 'actividades/actividad_form.html'
    success_url = reverse_lazy('actividad_list')

def pagina_principal(request):
    proyectos = Proyecto.objects.all()
    return render(request, 'actividades/principal.html', {'proyectos': proyectos})

def registrar_avance(request):
    if request.method == 'POST':
        actividad_id = request.POST.get('actividad')
        fecha_reporte_str = request.POST.get('fecha_reporte')
        cantidad_realizada = request.POST.get('cantidad_realizada')

        if not all([actividad_id, fecha_reporte_str, cantidad_realizada]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return redirect('registrar_avance')
        
        fecha_reporte = datetime.strptime(fecha_reporte_str, '%Y-%m-%d').date()
        if fecha_reporte > date.today():
           return render(request, 'actividades/error_fecha_futura.html')

        actividad_obj = get_object_or_404(Actividad, pk=actividad_id)
        
        # El cálculo del PV ya no se hace aquí. Solo guardamos el avance real.
        AvanceDiario.objects.update_or_create(
            actividad=actividad_obj, fecha_reporte=fecha_reporte,
            defaults={'cantidad_realizada_dia': cantidad_realizada}
        )
        messages.success(request, '¡El avance ha sido registrado con éxito!')
        return redirect('registrar_avance')
    else:
        partidas = PartidaActividad.objects.all()
        partida_seleccionada_id = request.GET.get('partida_filtro')
        actividades_filtradas = Actividad.objects.none()
        if partida_seleccionada_id:
            actividades_filtradas = Actividad.objects.filter(partida_id=partida_seleccionada_id, sub_actividades__isnull=True).order_by('padre__nombre', 'nombre')

        contexto = {
            'partidas': partidas, 'actividades_filtradas': actividades_filtradas,
            'partida_seleccionada_id': partida_seleccionada_id
        }
        return render(request, 'actividades/registrar_avance.html', contexto)

@login_required
@user_passes_test(es_staff)
def editar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    if request.method == 'POST':
        avance.fecha_reporte = request.POST.get('fecha_reporte', avance.fecha_reporte)
        avance.cantidad_realizada_dia = request.POST.get('cantidad_realizada', avance.cantidad_realizada_dia)
        avance.save()
        messages.success(request, '¡El avance ha sido actualizado con éxito!')
        return redirect('historial_avance', proyecto_id=avance.actividad.proyecto.id)
    
    contexto = {'avance': avance}
    return render(request, 'actividades/editar_avance.html', contexto)

@login_required
@user_passes_test(es_staff)
def borrar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    proyecto_id = avance.actividad.proyecto.id
    if request.method == 'POST':
        avance.delete()
        messages.success(request, 'El registro ha sido eliminado.')
        return redirect('historial_avance', proyecto_id=proyecto_id)

    contexto = {'avance': avance}
    return render(request, 'actividades/confirmar_borrado.html', contexto)

def registrar_reporte_maquinaria(request):
    form = ReporteMaquinariaForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data.get('fecha')
            if fecha_seleccionada and fecha_seleccionada > date.today():
               return render(request, 'actividades/error_fecha_futura.html')
            try:
                form.save()
                messages.success(request, '¡Reporte de maquinaria guardado exitosamente!')
                return redirect('registrar_reporte_maquinaria')
            except IntegrityError:
                messages.error(request, 'Ya existe un registro para esta combinación.')
    
    contexto = {'form': form, 'titulo': "Registrar Nuevo Reporte de Maquinaria"}
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)

def editar_reporte_maquinaria(request, pk):
    reporte = get_object_or_404(ReporteDiarioMaquinaria, pk=pk)
    form = ReporteMaquinariaForm(request.POST or None, instance=reporte)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, '¡Reporte de maquinaria actualizado exitosamente!')
            return redirect('pagina_principal') 
    
    contexto = {'form': form, 'titulo': f"Editar Reporte de Maquinaria del {reporte.fecha}"}
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)

def registrar_reporte_personal(request):
    form = ReportePersonalForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data.get('fecha')
            if fecha_seleccionada and fecha_seleccionada > date.today():
               return render(request, 'actividades/error_fecha_futura.html')
            try:
                form.save()
                messages.success(request, '¡Reporte de personal guardado exitosamente!')
                return redirect('registrar_reporte_personal')
            except IntegrityError:
                messages.error(request, 'Ya existe un registro para esta combinación.')
    
    contexto = {'form': form, 'titulo': "Registrar Reporte de Personal"}
    return render(request, 'actividades/reporte_personal_form.html', contexto)

def vista_clima(request):
    reporte = None
    form = ConsultaClimaForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data['fecha']
            reporte = obtener_y_guardar_clima(fecha_seleccionada)
            
    contexto = {'form': form, 'reporte': reporte}
    return render(request, 'actividades/vista_clima.html', contexto)