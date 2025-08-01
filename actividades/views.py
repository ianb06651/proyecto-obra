from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, F 
from datetime import date
from .models import Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal, Empresa, Cargo, AreaDeTrabajo,ReporteDiarioMaquinaria
from .utils import calcular_avance_diario
from .forms import ReporteMaquinariaForm, ReportePersonalForm
from django.db import IntegrityError
from datetime import date, datetime
from .forms import ConsultaClimaForm
from .services import obtener_y_guardar_clima



def es_staff(user):
    return user.is_staff


def registrar_avance(request):
    if request.method == 'POST':
        actividad_id = request.POST.get('actividad')
        fecha_reporte = request.POST.get('fecha_reporte')
        cantidad_realizada = request.POST.get('cantidad_realizada')

        if not all([actividad_id, fecha_reporte, cantidad_realizada]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return redirect('registrar_avance')
        
        fecha_seleccionada = datetime.strptime(fecha_reporte, '%Y-%m-%d').date()
        if fecha_seleccionada > date.today():
         return render(request, 'actividades/error_fecha_futura.html')

        actividad_obj = get_object_or_404(Actividad, pk=actividad_id)     
        meta_programada = calcular_avance_diario(
            actividad_obj.fecha_inicio_programada,
            actividad_obj.fecha_fin_programada,
            actividad_obj.meta_cantidad_total
        )
        
        try:
            AvanceDiario.objects.create(
                actividad=actividad_obj,
                fecha_reporte=fecha_reporte,
                cantidad_programada_dia=meta_programada,
                cantidad_realizada_dia=cantidad_realizada
            )
            messages.success(request, '¡El avance ha sido registrado con éxito!')
            return redirect('registrar_avance')
        except IntegrityError:
            avance_existente = AvanceDiario.objects.get(
                actividad_id=actividad_id,
                fecha_reporte=fecha_reporte
            )
            contexto = {
                'avance_pk': avance_existente.pk,
                'actividad_nombre': avance_existente.actividad.nombre_actividad,
                'fecha': avance_existente.fecha_reporte,
            }
            return render(request, 'actividades/confirmar_sobrescribir_avance.html', contexto)
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
    # --- LÓGICA DE FILTROS ---
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

# ---LÓGICA DE CÁLCULOS AVANZADOS ---

    total_real = avances.aggregate(total=Sum('cantidad_realizada_dia'))['total'] or 0

    total_programado_para_mostrar = avances.filter(
        fecha_reporte__lte=F('actividad__fecha_fin_programada')
    ).aggregate(total=Sum('cantidad_programada_dia'))['total'] or 0

    total_programado_para_spi = avances.filter(
        fecha_reporte__lte=date.today()
    ).aggregate(total=Sum('cantidad_programada_dia'))['total'] or 0
    
    rendimiento = 0
    if total_programado_para_spi > 0:
        rendimiento = (total_real / total_programado_para_spi) * 100

    contexto = {
        'avances': avances.order_by('-fecha_reporte'),
        'semanas': semanas,
        'todas_las_actividades': todas_las_actividades,
        'semana_seleccionada_id': semana_seleccionada_id,
        'actividad_seleccionada_id': actividad_seleccionada_id,
        'total_real_acumulado': total_real,
        'total_programado_acumulado': total_programado_para_mostrar, # <-- Usamos el valor para mostrar
        'unidad_filtrada': unidad_filtrada,
        'rendimiento': rendimiento,
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
    if request.method == 'POST':
        form = ReporteMaquinariaForm(request.POST)
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data.get('fecha')
            if fecha_seleccionada and fecha_seleccionada > date.today():
               return render(request, 'actividades/error_fecha_futura.html')
            try:
                form.save()
                messages.success(request, '¡Reporte de maquinaria guardado exitosamente!')
                return redirect('registrar_reporte_maquinaria')
            except IntegrityError:
                datos = form.cleaned_data
                registro_existente = ReporteDiarioMaquinaria.objects.get(
                    fecha=datos['fecha'],
                    tipo_maquinaria=datos['tipo_maquinaria'],
                    partida=datos['partida'],
                    empresa=datos['empresa'],
                    zona_trabajo=datos['zona_trabajo']
                )
                
                contexto = {
                    'registro_pk': registro_existente.pk,
                }
                return render(request, 'actividades/confirmar_sobrescribir_maquinaria.html', contexto)
    else:
        form = ReporteMaquinariaForm()
    
    return render(request, 'actividades/reporte_maquinaria_form.html', {
        'form': form,
        'titulo': "Registrar Nuevo Reporte de Maquinaria"
    })


def pagina_principal(request):
    """
    Vista para la página principal/dashboard.
    """
    return render(request, 'actividades/principal.html')


def editar_reporte_maquinaria(request, pk):
    reporte = get_object_or_404(ReporteDiarioMaquinaria, pk=pk)
    
    if request.method == 'POST':
        form = ReporteMaquinariaForm(request.POST, instance=reporte)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Reporte de maquinaria actualizado exitosamente!')
            return redirect('pagina_principal') 
    else:
        form = ReporteMaquinariaForm(instance=reporte)
    
    contexto = {
        'form': form,
        'titulo': f"Editar Reporte de Maquinaria del {reporte.fecha}"
    }
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)


def registrar_reporte_personal(request):
    if request.method == 'POST':
        form = ReportePersonalForm(request.POST)
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data.get('fecha')
            if fecha_seleccionada and fecha_seleccionada > date.today():
               return render(request, 'actividades/error_fecha_futura.html')
            try:
                form.save()
                messages.success(request, '¡Reporte de personal guardado exitosamente!')
                return redirect('registrar_reporte_personal')
            except IntegrityError:
                datos = form.cleaned_data
                registro_existente = ReportePersonal.objects.get(
                    fecha=datos['fecha'],
                    empresa=datos['empresa'],
                    cargo=datos['cargo'],
                    partida=datos['partida'],
                    area_de_trabajo=datos['area_de_trabajo']
                )
                contexto = {
                    'registro_pk': registro_existente.pk,
                }
                return render(request, 'actividades/confirmar_sobrescribir_personal.html', contexto)
    else:
        form = ReportePersonalForm()
    
    contexto = {
        'form': form,
        'titulo': "Registrar Reporte de Personal"
    }
    return render(request, 'actividades/reporte_personal_form.html', contexto)

def vista_clima(request):
    reporte = None
    if request.method == 'POST':
        form = ConsultaClimaForm(request.POST)
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data['fecha']
            reporte = obtener_y_guardar_clima(fecha_seleccionada)
    else:
        form = ConsultaClimaForm()
        
    contexto = {
        'form': form,
        'reporte': reporte
    }
    return render(request, 'actividades/vista_clima.html', contexto)