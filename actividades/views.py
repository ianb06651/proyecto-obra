# actividades/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q, Prefetch, Count, Max, Min
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from datetime import date, timedelta
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

# --- REST FRAMEWORK ---
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication

# --- IMPORTS LOCALES ---
from .serializers import ElementoBIM_GUID_Serializer
from .forms import (
    ReporteMaquinariaForm, ReportePersonalForm, ActividadForm,
    ConsultaClimaForm, AvanceDiarioForm, AvancePorZonaFormSet,
    MetaPorZonaFormSet, SeleccionarElementoForm, CronogramaPorZonaForm, CronogramaForm,
    ObservacionForm
)
from .services import obtener_y_guardar_clima
from .models import (
    Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal,
    Empresa, Cargo, AreaDeTrabajo, ReporteDiarioMaquinaria, Proyecto,
    AvancePorZona, MetaPorZona, ElementoConstructivo, 
    PasoProcesoTipoElemento, AvanceProcesoElemento, TipoElemento,
    ElementoBIM_GUID, Cronograma, Observacion, CronogramaPorZona
)

def es_staff(user):
    return user.is_staff

# ==========================================
# VISTAS GENERALES
# ==========================================

def pagina_principal(request):
    proyectos = Proyecto.objects.all()
    # Enviamos el primer proyecto como contexto por si se necesita para enlaces directos
    proyecto_activo = proyectos.first() if proyectos.exists() else None
    return render(request, 'actividades/principal.html', {
        'proyectos': proyectos,
        'proyecto': proyecto_activo
    })

# ==========================================
# AVANCES E HISTORIAL (Lógica Compleja)
# ==========================================

def historial_avance_view(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    semanas = Semana.objects.all()
    actividades_filtrables = Actividad.objects.filter(proyecto=proyecto, sub_actividades__isnull=True).order_by('nombre')

    fecha_corte_total = date.today()
    total_programado_pv_acumulado = proyecto.get_valor_planeado_a_fecha(fecha_corte_total)

    prefetch_zonas_anidadas = Prefetch(
        'avances_por_zona',
        queryset=AvancePorZona.objects.select_related('zona')
    )

    avances_totales_acumulados = AvanceDiario.objects.filter(
        actividad__proyecto=proyecto,
        fecha_reporte__lte=fecha_corte_total
    ).prefetch_related(prefetch_zonas_anidadas) 

    total_real_ev_acumulado = sum(avance.cantidad_total for avance in avances_totales_acumulados)

    if total_programado_pv_acumulado and total_programado_pv_acumulado > 0:
        spi_calculado = total_real_ev_acumulado / total_programado_pv_acumulado
        spi_acumulado = min(spi_calculado, 2.0) 
    else:
        spi_acumulado = 0

    semana_seleccionada_id = request.GET.get('semana_filtro')
    actividad_seleccionada_id = request.GET.get('actividad_filtro')

    avances_para_tabla = AvanceDiario.objects.filter(
        actividad__proyecto=proyecto
    ).select_related(
        'actividad', 'empresa'
    ).prefetch_related(
        prefetch_zonas_anidadas
    )

    if actividad_seleccionada_id:
        avances_para_tabla = avances_para_tabla.filter(actividad_id=actividad_seleccionada_id)

    if semana_seleccionada_id:
        try:
            semana_obj = Semana.objects.get(pk=semana_seleccionada_id)
            avances_para_tabla = avances_para_tabla.filter(fecha_reporte__range=[semana_obj.fecha_inicio, semana_obj.fecha_fin])
        except Semana.DoesNotExist:
            messages.warning(request, "La semana seleccionada no es válida.")
            semana_seleccionada_id = None
            fecha_inicio_filtro_tabla = date.today() - timedelta(weeks=2)
            avances_para_tabla = avances_para_tabla.filter(fecha_reporte__gte=fecha_inicio_filtro_tabla)

    elif not semana_seleccionada_id:
        fecha_inicio_filtro_tabla = date.today() - timedelta(weeks=2)
        avances_para_tabla = avances_para_tabla.filter(fecha_reporte__gte=fecha_inicio_filtro_tabla)

    context = {
        'proyecto': proyecto,
        'semanas': semanas,
        'actividades_filtrables': actividades_filtrables,
        'semana_seleccionada_id': semana_seleccionada_id,
        'actividad_seleccionada_id': actividad_seleccionada_id,
        'total_programado_pv': total_programado_pv_acumulado,
        'total_real_ev': total_real_ev_acumulado,
        'rendimiento_spi': spi_acumulado, 
        'fecha_corte': fecha_corte_total,
        'avances_reales': avances_para_tabla.order_by('-fecha_reporte')
    }

    return render(request, 'actividades/historial_avance.html', context)

def registrar_avance(request):
    proyecto = Proyecto.objects.first()
    if not proyecto:
        messages.error(request, 'Error: No hay ningún proyecto registrado en el sistema.')
        return redirect('actividades:pagina_principal')

    partida_seleccionada_id = request.GET.get('partida_filtro')
    actividad_queryset = Actividad.objects.filter(
        proyecto=proyecto, sub_actividades__isnull=True
    ).order_by('nombre')
    
    if partida_seleccionada_id:
        actividad_queryset = actividad_queryset.filter(partida_id=partida_seleccionada_id)

    formset = None 

    if request.method == 'POST':
        form = AvanceDiarioForm(request.POST, actividad_queryset=actividad_queryset, validate_uniqueness=False)

        if form.is_valid():
            actividad = form.cleaned_data['actividad']
            fecha = form.cleaned_data['fecha_reporte']
            empresa = form.cleaned_data['empresa']

            try:
                with transaction.atomic():
                    avance_diario_obj, creado = AvanceDiario.objects.get_or_create(
                        actividad=actividad,
                        fecha_reporte=fecha,
                        empresa=empresa,
                        defaults={}
                    )
                    formset = AvancePorZonaFormSet(request.POST, instance=avance_diario_obj)

                    if formset.is_valid():
                        formset.save()

                        zonas_validas = 0
                        for subform in formset:
                            if subform.cleaned_data and subform.cleaned_data.get('cantidad', 0) > 0 and not subform.cleaned_data.get('DELETE'):
                                zonas_validas += 1

                        if zonas_validas == 0 and avance_diario_obj.avances_por_zona.count() == 0:
                            form.add_error(None, "Debes registrar el avance para al menos una zona.")
                            raise ValidationError("Sin zonas válidas")

                        if creado and zonas_validas > 0:
                            messages.success(request, "¡Avance registrado con éxito!")
                        elif not creado:
                            messages.success(request, "¡Avance editado con éxito!")

                        return redirect('actividades:registrar_avance')

                    else:
                        messages.error(request, 'Por favor, corrige los errores en el desglose por zonas.')

            except ValidationError:
                messages.error(request, "Debes registrar el avance para al menos una zona.")
            except IntegrityError:
                messages.error(request, "Error de integridad. No se pudo guardar el avance.")
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")

        else:
            messages.error(request, 'Por favor, corrige los errores en los campos principales.')
            formset = AvancePorZonaFormSet(request.POST) 

    else:
        form = AvanceDiarioForm(actividad_queryset=actividad_queryset, validate_uniqueness=False)
        formset = AvancePorZonaFormSet() 

    if formset is None:
        formset = AvancePorZonaFormSet()

    partidas = PartidaActividad.objects.all()
    contexto = {
        'form': form,
        'formset': formset,
        'proyecto': proyecto,
        'partidas': partidas,
        'partida_seleccionada_id': partida_seleccionada_id,
    }
    return render(request, 'actividades/registrar_avance.html', contexto)

@login_required
@user_passes_test(es_staff)
def editar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    form = AvanceDiarioForm(request.POST or None, instance=avance, validate_uniqueness=False)
    formset = AvancePorZonaFormSet(request.POST or None, instance=avance)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                if not form.is_valid() or not formset.is_valid():
                    if not form.is_valid():
                        messages.error(request, 'El formulario principal es inválido.')
                    if not formset.is_valid():
                        messages.error(request, 'Errores en el desglose.')
                    return render(request, 'actividades/editar_avance.html', {'form': form, 'formset': formset, 'avance': avance})

                avance_diario = form.save()
                formset.save()

                if avance_diario.avances_por_zona.count() == 0:
                    form.add_error(None, "No puedes eliminar todas las zonas.")
                    raise ValidationError("Todas las zonas eliminadas")

                messages.success(request, 'Avance actualizado.')
                return redirect('actividades:historial_avance', proyecto_id=avance.actividad.proyecto.id)

        except ValidationError:
            messages.error(request, "No puedes eliminar todas las zonas.")
        except Exception as e:
            messages.error(request, f'Ocurrió un error: {e}')

    contexto = {
        'form': form,
        'formset': formset,
        'avance': avance,
    }
    return render(request, 'actividades/editar_avance.html', contexto)

@login_required
@user_passes_test(es_staff)
def borrar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    proyecto_id = avance.actividad.proyecto.id
    if request.method == 'POST':
        avance.delete()
        messages.success(request, 'El registro ha sido eliminado.')
        return redirect('actividades:historial_avance', proyecto_id=proyecto_id)

    contexto = {'avance': avance}
    return render(request, 'actividades/confirmar_borrado.html', contexto)

# ==========================================
# ACTIVIDADES (Vistas Basadas en Clases - CRUD)
# ==========================================

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
    # CORRECCIÓN: Namespace añadido
    success_url = reverse_lazy('actividades:actividad_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = MetaPorZonaFormSet(self.request.POST)
        else:
            data['formset'] = MetaPorZonaFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        try:
            with transaction.atomic():
                self.object = form.save()
                formset.instance = self.object
                if not formset.is_valid():
                    messages.error(self.request, 'Corrige los errores en las metas por zona.')
                    return self.form_invalid(form)
                formset.save()
                messages.success(self.request, 'Actividad creada con éxito.')
        except Exception as e:
             messages.error(self.request, f"Error: {e}")
             return self.form_invalid(form)
        return super().form_valid(form)
    
    def get_initial(self):
        initial = super().get_initial()
        padre_id = self.request.GET.get('padre')
        if padre_id:
            try:
                initial['padre'] = Actividad.objects.get(pk=padre_id)
            except Actividad.DoesNotExist:
                pass
        return initial

class ActividadUpdateView(UpdateView):
    model = Actividad
    form_class = ActividadForm
    template_name = 'actividades/actividad_form.html'
    # CORRECCIÓN: Namespace añadido
    success_url = reverse_lazy('actividades:actividad_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = MetaPorZonaFormSet(self.request.POST, instance=self.object)
        else:
            data['formset'] = MetaPorZonaFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        try:
            with transaction.atomic():
                if not formset.is_valid():
                    messages.error(self.request, 'Corrige los errores en las metas.')
                    return self.form_invalid(form)
                self.object = form.save()
                formset.save()
                messages.success(self.request, 'Actividad actualizada.')
        except Exception as e:
             messages.error(self.request, f"Error: {e}")
             return self.form_invalid(form)
        return super().form_valid(form)

# ==========================================
# REPORTES (MAQUINARIA, PERSONAL, CLIMA)
# ==========================================

def registrar_reporte_maquinaria(request):
    form = ReporteMaquinariaForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data.get('fecha')
            if fecha_seleccionada and fecha_seleccionada > date.today():
                messages.error(request, 'No puedes hacer registros para una fecha futura.')
            else:
                try:
                    form.save()
                    messages.success(request, '¡Reporte de maquinaria guardado!')
                    return redirect('actividades:registrar_reporte_maquinaria')
                except IntegrityError:
                    messages.error(request, 'Ya existe un registro igual.')
        else:
             messages.error(request, 'Corrige los errores.')

    contexto = {'form': form, 'titulo': "Registrar Nuevo Reporte de Maquinaria"}
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)

def editar_reporte_maquinaria(request, pk):
    reporte = get_object_or_404(ReporteDiarioMaquinaria, pk=pk)
    form = ReporteMaquinariaForm(request.POST or None, instance=reporte)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Actualizado.')
            return redirect('actividades:pagina_principal')
        except IntegrityError:
             messages.error(request, 'Error de integridad (duplicado).')

    contexto = {'form': form, 'titulo': f"Editar Reporte: {reporte.fecha}"}
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)

def registrar_reporte_personal(request):
    proyecto = Proyecto.objects.first()
    form = ReportePersonalForm(request.POST or None)
    
    if request.method == 'POST':
        if form.is_valid():
            fecha = form.cleaned_data.get('fecha')
            if fecha and fecha > date.today():
                 messages.error(request, 'Fecha futura no permitida.')
            else:
                try:
                    reporte = form.save(commit=False)
                    if not reporte.proyecto and proyecto:
                        reporte.proyecto = proyecto
                    reporte.save()
                    messages.success(request, '¡Personal registrado!')
                    return redirect('actividades:registrar_reporte_personal')
                except IntegrityError:
                    messages.error(request, 'Registro duplicado.')
        else:
            messages.error(request, 'Corrige los errores.')

    contexto = {'form': form, 'titulo': "Registrar Reporte de Personal"}
    return render(request, 'actividades/reporte_personal_form.html', contexto)

def historial_personal(request):
    proyecto = Proyecto.objects.first()
    reportes = ReportePersonal.objects.filter(proyecto=proyecto).order_by('-fecha')
    resumen = reportes.values('cargo__nombre').annotate(total=Sum('cantidad')).order_by('-total')
    semanas = Semana.objects.all().order_by('-numero_semana')[:5]
    areas = AreaDeTrabajo.objects.all()

    context = {
        'proyecto': proyecto,
        'reportes': reportes,
        'resumen_personal': resumen,
        'semanas': semanas,
        'areas': areas
    }
    return render(request, 'actividades/historial_personal.html', context)

def vista_clima(request):
    reporte = None
    form = ConsultaClimaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        fecha = form.cleaned_data['fecha']
        reporte = obtener_y_guardar_clima(fecha)
        if not reporte:
             messages.error(request, f"No se pudo obtener clima para {fecha}.")
    
    return render(request, 'actividades/vista_clima.html', {'form': form, 'reporte': reporte})

# ==========================================
# BIM Y APIs (Logic Completa Restaurada)
# ==========================================

@require_GET
def buscar_elementos_constructivos(request):
    query = request.GET.get('term', '')
    if len(query) < 2:
        return JsonResponse([], safe=False)

    elementos = ElementoConstructivo.objects.filter(
        Q(identificador_unico__icontains=query) |
        Q(guids_bim__identificador_bim__icontains=query)
    ).select_related('tipo_elemento').distinct()[:10] 

    resultados = [
        {'id': el.id, 'text': f"{el.identificador_unico} - {el.tipo_elemento.nombre}"}
        for el in elementos
    ]
    return JsonResponse({'results': resultados}, safe=False)

@require_GET
def obtener_pasos_y_avance_elemento(request, elemento_id):
    try:
        elemento = ElementoConstructivo.objects.select_related('tipo_elemento').get(pk=elemento_id)
    except ElementoConstructivo.DoesNotExist:
         return JsonResponse({'error': 'No encontrado'}, status=404)

    pasos = PasoProcesoTipoElemento.objects.filter(tipo_elemento=elemento.tipo_elemento).select_related('proceso').order_by('orden')
    avances = AvanceProcesoElemento.objects.filter(elemento=elemento).values('paso_proceso_id', 'fecha_finalizacion')
    
    mapa_avances = {av['paso_proceso_id']: av['fecha_finalizacion'].strftime('%Y-%m-%d') for av in avances if av['fecha_finalizacion']}
    
    pasos_data = []
    for paso in pasos:
        pasos_data.append({
            'paso_id': paso.id,
            'nombre_proceso': paso.proceso.nombre,
            'orden': paso.orden,
            'fecha_guardada': mapa_avances.get(paso.id, None) 
        })
    return JsonResponse({'pasos': pasos_data, 'elemento': elemento.identificador_unico})

def registrar_avance_bim(request):
    # Contexto con las URLs correctas (usando namespace)
    context = {
        'url_buscar_elementos': reverse('actividades:api_buscar_elementos'),
        'url_obtener_pasos_base': reverse('actividades:api_obtener_pasos', args=['0']), 
    }

    if request.method == 'POST':
        elementos_ids_str = request.POST.get('elementos_ids', '')
        if not elementos_ids_str:
            messages.error(request, "No se seleccionó ningún elemento.")
            return redirect('actividades:registrar_avance_bim')

        try:
            ids_list = [int(id_str) for id_str in elementos_ids_str.split(',') if id_str.isdigit()]
        except ValueError:
             messages.error(request, "Error en los IDs.")
             return redirect('actividades:registrar_avance_bim')

        pasos_ids = request.POST.getlist('paso_id')
        fechas = request.POST.getlist('fecha_finalizacion')

        if len(pasos_ids) != len(fechas):
             messages.error(request, "Datos corruptos.")
             return redirect('actividades:registrar_avance_bim')

        cant_ok = 0
        try:
            with transaction.atomic():
                elementos = ElementoConstructivo.objects.filter(pk__in=ids_list)
                if not elementos.exists():
                     raise ValidationError("Elementos no encontrados.")

                # Verificar mismo tipo
                primer_tipo = elementos.first().tipo_elemento
                if elementos.exclude(tipo_elemento=primer_tipo).exists():
                     raise ValidationError("Todos los elementos deben ser del mismo tipo.")

                for elemento in elementos:
                    hubo_cambio = False
                    for p_id, f_str in zip(pasos_ids, fechas):
                        if f_str:
                            fecha_obj = date.fromisoformat(f_str)
                            if fecha_obj > date.today():
                                 raise ValidationError("No se permiten fechas futuras.")

                            paso = PasoProcesoTipoElemento.objects.get(pk=p_id)
                            AvanceProcesoElemento.objects.update_or_create(
                                elemento=elemento, paso_proceso=paso,
                                defaults={'fecha_finalizacion': fecha_obj}
                            )
                            hubo_cambio = True
                    if hubo_cambio: cant_ok += 1
            
            if cant_ok > 0:
                messages.success(request, f"Actualizados {cant_ok} elementos.")
            else:
                messages.warning(request, "Sin cambios.")
                
        except Exception as e:
            messages.error(request, f"Error: {e}")

        return redirect('actividades:registrar_avance_bim')

    # GET
    form = SeleccionarElementoForm()
    context['form'] = form
    return render(request, 'actividades/registrar_avance_bim.html', context)

class ElementoStatusAPIView(ListAPIView):
    # Restaurado del archivo original
    serializer_class = ElementoBIM_GUID_Serializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ElementoBIM_GUID.objects.select_related(
            'elemento_constructivo', 'elemento_constructivo__tipo_elemento'
        ).annotate(
            total_pasos=Count('elemento_constructivo__tipo_elemento__pasos_proceso', distinct=True),
            pasos_completados=Count('elemento_constructivo__avances_proceso', distinct=True),
            ultima_fecha=Max('elemento_constructivo__avances_proceso__fecha_finalizacion')
        )

@require_GET
def api_generar_rango(request):
    patron = request.GET.get('patron', '')    
    tipo = request.GET.get('tipo', 'numero') 
    inicio = request.GET.get('inicio', '')
    fin = request.GET.get('fin', '')
    usar_ceros = request.GET.get('ceros') == 'true'

    if not (patron and inicio and fin):
        return JsonResponse({'error': 'Faltan datos.'}, status=400)

    try:
        candidatos = []
        if tipo == 'numero':
            start, end = int(inicio), int(fin)
            for i in range(start, end + 1):
                val = str(i).zfill(2) if usar_ceros else str(i)
                candidatos.append(patron.replace('{}', val))
        elif tipo == 'letra':
            start, end = ord(inicio.upper()[0]), ord(fin.upper()[0])
            for i in range(start, end + 1):
                candidatos.append(patron.replace('{}', chr(i)))
        
        elementos = ElementoConstructivo.objects.filter(identificador_unico__in=candidatos)
        data = [{'id': e.id, 'text': e.identificador_unico} for e in elementos]
        return JsonResponse({'resultados': data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ==========================================
# CRONOGRAMA (Modificado con Filtro de Zonas)
# ==========================================

def vista_cronograma(request):
    proyecto = Proyecto.objects.first()
    if not proyecto:
        messages.error(request, "No hay proyectos.")
        return redirect('actividades:pagina_principal')

    zonas_list = AreaDeTrabajo.objects.all().order_by('nombre')
    zona_id = request.GET.get('zona_id') # Antes era 'zona', ahora usamos 'zona_id' para ser consistentes
    
    # Si viene 'zona' en el GET (del html antiguo), lo usamos
    if not zona_id:
        zona_id = request.GET.get('zona')

    detalles = None
    zona_obj = None

    if zona_id:
        try:
            zona_obj = AreaDeTrabajo.objects.get(pk=zona_id)
            detalles = CronogramaPorZona.objects.filter(
                tarea__proyecto=proyecto, 
                zona=zona_obj
            ).select_related('tarea').order_by('fecha_inicio_prog')
        except AreaDeTrabajo.DoesNotExist:
            messages.error(request, "Zona no válida.")

    context = {
        'proyecto': proyecto,
        'zonas': zonas_list,       # <--- CORRECCIÓN: Cambiado de 'zonas_list' a 'zonas'
        'zona_seleccionada': zona_obj,
        'actividades': detalles    # <--- CORRECCIÓN: El HTML usa 'actividades', no 'detalles'
    }
    return render(request, 'actividades/cronograma_list.html', context)

def crear_tarea_cronograma(request):
    proyecto = Proyecto.objects.first()
    form = CronogramaForm(request.POST or None, initial={'padre': request.GET.get('padre')}, proyecto=proyecto)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                tarea = form.save(commit=False)
                tarea.proyecto = proyecto
                tarea.save()
                
                # Guardar las zonas manualmente creando CronogramaPorZona
                zonas = form.cleaned_data['zonas_aplicables']
                for zona in zonas:
                    CronogramaPorZona.objects.create(tarea=tarea, zona=zona)
                    
            messages.success(request, "Tarea creada y asignada a las zonas.")
            
            # CORRECCIÓN: Cambiado 'vista_cronograma' por 'cronograma_list'
            return redirect('actividades:cronograma_list')
            
        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")

    return render(request, 'actividades/cronograma_crear.html', {'form': form, 'proyecto': proyecto})

def editar_fechas_cronograma(request, pk):
    # OJO: Aquí 'pk' debe ser el ID de CronogramaPorZona, no de la tarea maestra
    registro = get_object_or_404(CronogramaPorZona, pk=pk)
    
    # Usamos el formulario correcto para el modelo correcto
    form = CronogramaPorZonaForm(request.POST or None, instance=registro)
    
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Fechas actualizadas.")
        
        # CORRECCIÓN: Cambiado 'vista_cronograma' por 'cronograma_list'
        url_base = reverse('actividades:cronograma_list')
        return redirect(f"{url_base}?zona_id={registro.zona.id}")
    
    return render(request, 'actividades/cronograma_form.html', {
        'form': form, 
        'tarea': registro.tarea, 
        'zona': registro.zona
    })

def eliminar_tarea_cronograma(request, pk):
    # Restaurada del archivo original
    tarea = get_object_or_404(Cronograma, pk=pk)
    if request.method == 'POST':
        tarea.delete()
        messages.success(request, "Tarea eliminada.")
        return redirect('actividades:vista_cronograma')
    return render(request, 'actividades/confirmar_borrado.html', {'object': tarea})

def vista_cronograma_movil(request):
    proyecto = Proyecto.objects.first()
    
    if request.method == 'POST':
        tarea_id = request.POST.get('tarea_id')
        zona_id = request.POST.get('zona_id') # <--- Idealmente necesitamos esto del form
        inicio = request.POST.get('fecha_inicio_real')
        fin = request.POST.get('fecha_fin_real')

        if tarea_id:
            try:
                # Opción A: Si el formulario envía la zona (Lo ideal)
                if zona_id:
                    detalle = get_object_or_404(CronogramaPorZona, tarea_id=tarea_id, zona_id=zona_id)
                else:
                    # Opción B: Si no envía zona, buscamos los registros asociados a esa tarea
                    # (Esto asume que quieres actualizar la fecha en donde sea que esté esa tarea)
                    detalles = CronogramaPorZona.objects.filter(tarea_id=tarea_id)
                    if detalles.exists():
                        detalle = detalles.first() # Tomamos el primero (o iteramos si quieres actualizar todos)
                    else:
                        messages.error(request, "Esta tarea no está asignada a ninguna zona.")
                        return redirect('actividades:vista_cronograma_movil')

                # Actualizamos las fechas en el modelo CORRECTO (CronogramaPorZona)
                if inicio:
                    detalle.fecha_inicio_real = inicio
                if fin:
                    detalle.fecha_fin_real = fin
                
                detalle.save()
                messages.success(request, f"Actualizado: {detalle.tarea.nombre} ({detalle.zona.nombre})")

            except Exception as e:
                messages.error(request, f"Error al actualizar: {e}")
        else:
             messages.error(request, "No se seleccionó ninguna tarea.")

        return redirect('actividades:vista_cronograma_movil')

    # GET: Mostrar la interfaz
    categorias = Cronograma.objects.filter(proyecto=proyecto, padre__isnull=True)
    # También pasamos las zonas por si quieres agregarlas a un select en el HTML
    zonas = AreaDeTrabajo.objects.all() 
    return render(request, 'actividades/cronograma_actualizar_movil.html', {
        'categorias_nivel_1': categorias,
        'zonas': zonas
    })

@require_GET
def api_hijos_cronograma(request, padre_id):
    hijos = Cronograma.objects.filter(padre_id=padre_id).values('id', 'nombre').order_by('id')
    return JsonResponse(list(hijos), safe=False)

@require_GET
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
                # CORRECCIÓN CRÍTICA: Enviar las fechas reales con los nombres que espera el JS
                'fecha_inicio_real': detalle_zona.fecha_inicio_real,
                'fecha_fin_real': detalle_zona.fecha_fin_real,
                
                # Datos extra informativos
                'inicio_prog': detalle_zona.fecha_inicio_prog,
                'fin_prog': detalle_zona.fecha_fin_prog,
                'estado': detalle_zona.estado_calculado
            })
    
    return JsonResponse(data)

# ==========================================
# OBSERVACIONES
# ==========================================

def lista_observaciones(request):
    zonas = AreaDeTrabajo.objects.all()
    zona_id = request.GET.get('zona_filtro')
    busqueda = request.GET.get('busqueda')
    observaciones = Observacion.objects.all().order_by('-fecha')

    if zona_id: observaciones = observaciones.filter(zona_id=zona_id)
    if busqueda: observaciones = observaciones.filter(nombre__icontains=busqueda)

    context = {
        'observaciones': observaciones,
        'zonas': zonas,
        'zona_seleccionada_id': int(zona_id) if zona_id else None,
        'busqueda': busqueda
    }
    return render(request, 'actividades/observacion_list.html', context)

def crear_observacion(request):
    form = ObservacionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, "Observación registrada.")
            return redirect('actividades:lista_observaciones')
        except IntegrityError:
            messages.error(request, "Duplicada.")
    return render(request, 'actividades/observacion_form.html', {'form': form})

@login_required
def marcar_observacion_resuelta(request, pk):
    obs = get_object_or_404(Observacion, pk=pk)
    if not obs.resuelto:
        obs.resuelto = True
        obs.resuelto_por = request.user
        obs.fecha_resolucion = date.today()
        messages.success(request, "Resuelta.")
    else:
        obs.resuelto = False
        obs.resuelto_por = None
        obs.fecha_resolucion = None
        messages.warning(request, "Reabierta.")
    obs.save()
    # Redirigir a donde estaba el usuario
    next_url = request.META.get('HTTP_REFERER', 'actividades:lista_observaciones')
    return redirect(next_url)

@login_required
def eliminar_observacion(request, pk):
    obs = get_object_or_404(Observacion, pk=pk)
    if request.method == 'POST':
        obs.delete()
        messages.success(request, "Eliminada.")
        return redirect('actividades:lista_observaciones')
    return render(request, 'actividades/observacion_confirmar_borrado.html', {'observacion': obs})