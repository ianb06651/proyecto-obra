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

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication

from .serializers import ElementoBIM_GUID_Serializer
from .forms import (
    ReporteMaquinariaForm, ReportePersonalForm, ActividadForm,
    ConsultaClimaForm, AvanceDiarioForm, AvancePorZonaFormSet,
    MetaPorZonaFormSet, SeleccionarElementoForm, CronogramaHibridoForm, CronogramaForm,
    ObservacionForm # <--- IMPORTAR
)
from .services import obtener_y_guardar_clima
from .models import (
    Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal,
    Empresa, Cargo, AreaDeTrabajo, ReporteDiarioMaquinaria, Proyecto,
    AvancePorZona, MetaPorZona, ElementoConstructivo, 
    PasoProcesoTipoElemento, AvanceProcesoElemento, TipoElemento,
    ElementoBIM_GUID, Cronograma, Observacion # <--- IMPORTAR
)

def es_staff(user):
    return user.is_staff

# ... (Las vistas existentes hasta historial_avance_view no cambian) ...
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
                    messages.error(self.request, 'Por favor, corrige los errores en el desglose de metas por zona.')
                    if formset.non_form_errors():
                        messages.warning(self.request, f"Errores generales en el desglose: {formset.non_form_errors()}")
                    return self.form_invalid(form)

                formset.save()
                messages.success(self.request, 'Actividad con metas por zona creada con éxito.')

        except IntegrityError:
            messages.error(self.request, "Error de integridad al guardar la actividad o sus metas.")
            return self.form_invalid(form)
        except Exception as e:
             messages.error(self.request, f"Ocurrió un error inesperado: {e}")
             return self.form_invalid(form)

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'El formulario es inválido. Por favor, revisa los campos marcados en rojo.')
        context = self.get_context_data(form=form)
        if self.request.POST:
            context['formset'] = MetaPorZonaFormSet(self.request.POST)
        return self.render_to_response(context)

    def get_initial(self):
        initial = super().get_initial()
        padre_id = self.request.GET.get('padre')
        if padre_id:
            try:
                initial['padre'] = Actividad.objects.get(pk=padre_id)
            except Actividad.DoesNotExist:
                 messages.warning(self.request, "La categoría padre especificada no existe.")
        return initial


class ActividadUpdateView(UpdateView):
    model = Actividad
    form_class = ActividadForm
    template_name = 'actividades/actividad_form.html'
    success_url = reverse_lazy('actividad_list')

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
                    messages.error(self.request, 'Por favor, corrige los errores en el desglose de metas por zona.')
                    if formset.non_form_errors():
                        messages.warning(self.request, f"Errores generales en el desglose: {formset.non_form_errors()}")
                    return self.form_invalid(form)

                self.object = form.save()
                formset.save()
                
                messages.success(self.request, 'Actividad actualizada con éxito.')

        except IntegrityError:
            messages.error(self.request, "Error de integridad al actualizar la actividad o sus metas.")
            return self.form_invalid(form)
        except Exception as e:
             messages.error(self.request, f"Ocurrió un error inesperado: {e}")
             return self.form_invalid(form)
            
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'El formulario es inválido. Por favor, revisa los campos marcados en rojo.')
        context = self.get_context_data(form=form)
        if self.request.POST:
            context['formset'] = MetaPorZonaFormSet(self.request.POST, instance=self.object)
        return self.render_to_response(context)


def registrar_avance(request):
    proyecto = Proyecto.objects.first()
    if not proyecto:
        messages.error(request, 'Error: No hay ningún proyecto registrado en el sistema.')
        return redirect('pagina_principal')

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
                        
                        return redirect('registrar_avance')

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
    form = AvanceDiarioForm(request.POST or None, instance=avance)
    formset = AvancePorZonaFormSet(request.POST or None, instance=avance)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                if not form.is_valid() or not formset.is_valid():
                    if not form.is_valid():
                        messages.error(request, 'El formulario principal es inválido. Revisa los campos de actividad, fecha y empresa.')
                    
                    if not formset.is_valid():
                        messages.error(request, 'Por favor, corrige los errores en el desglose.')
                        if formset.non_form_errors():
                            messages.warning(request, f'Errores generales en el desglose: {formset.non_form_errors()}')
                    return render(request, 'actividades/editar_avance.html', {'form': form, 'formset': formset, 'avance': avance})

                avance_diario = form.save()
                formset.save()

                if avance_diario.avances_por_zona.count() == 0:
                    form.add_error(None, "No puedes eliminar todas las zonas. Debe quedar al menos una.")
                    raise ValidationError("Todas las zonas eliminadas")

                messages.success(request, 'El avance diario y su desglose han sido actualizados.')
                return redirect('historial_avance', proyecto_id=avance.actividad.proyecto.id)

        except ValidationError:
            messages.error(request, "No puedes eliminar todas las zonas. Debe quedar al menos una.")
        except IntegrityError:
             messages.error(request, "Error de integridad al actualizar.")
        except Exception as e:
            messages.error(request, f'Ocurrió un error inesperado: {e}')
            
    contexto = {
        'form': form,
        'formset': formset,
        'avance': avance,
    }
    return render(request, 'actividades/editar_avance.html', contexto)


def pagina_principal(request):
    proyectos = Proyecto.objects.all()
    return render(request, 'actividades/principal.html', {'proyectos': proyectos})

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
                messages.error(request, 'No puedes hacer registros para una fecha futura.')
                contexto = {'form': form, 'titulo': "Registrar Nuevo Reporte de Maquinaria"}
                return render(request, 'actividades/reporte_maquinaria_form.html', contexto)
            try:
                form.save()
                messages.success(request, '¡Reporte de maquinaria guardado exitosamente!')
                return redirect('registrar_reporte_maquinaria')
            except IntegrityError:
                messages.error(request, 'Ya existe un registro para esta combinación de maquinaria, fecha, partida, empresa y zona.')
        else:
             messages.error(request, 'Por favor, corrige los errores en el formulario.')

    contexto = {'form': form, 'titulo': "Registrar Nuevo Reporte de Maquinaria"}
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)


def editar_reporte_maquinaria(request, pk):
    reporte = get_object_or_404(ReporteDiarioMaquinaria, pk=pk)
    form = ReporteMaquinariaForm(request.POST or None, instance=reporte)
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, '¡Reporte de maquinaria actualizado exitosamente!')
                return redirect('pagina_principal')
            except IntegrityError:
                 messages.error(request, 'Error de integridad al actualizar. Verifica que la combinación sea única.')
            except Exception as e:
                 messages.error(request, f"Ocurrió un error inesperado: {e}")
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')

    contexto = {'form': form, 'titulo': f"Editar Reporte de Maquinaria del {reporte.fecha}"}
    return render(request, 'actividades/reporte_maquinaria_form.html', contexto)


def registrar_reporte_personal(request):
    form = ReportePersonalForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data.get('fecha')
            if fecha_seleccionada and fecha_seleccionada > date.today():
                 messages.error(request, 'No puedes hacer registros para una fecha futura.')
                 contexto = {'form': form, 'titulo': "Registrar Reporte de Personal"}
                 return render(request, 'actividades/reporte_personal_form.html', contexto)
            try:
                form.save()
                messages.success(request, '¡Reporte de personal guardado exitosamente!')
                return redirect('registrar_reporte_personal')
            except IntegrityError:
                messages.error(request, 'Ya existe un registro de personal para esta combinación.')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')

    contexto = {'form': form, 'titulo': "Registrar Reporte de Personal"}
    return render(request, 'actividades/reporte_personal_form.html', contexto)


def vista_clima(request):
    reporte = None
    form = ConsultaClimaForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data['fecha']
            reporte = obtener_y_guardar_clima(fecha_seleccionada)
            if not reporte:
                 messages.error(request, f"No se pudieron obtener los datos del clima para {fecha_seleccionada}.")
        else:
            messages.error(request, "La fecha seleccionada no es válida. Por favor, corrígela.")

    contexto = {'form': form, 'reporte': reporte}
    return render(request, 'actividades/vista_clima.html', contexto)

# --- VISTAS DE API Y BIM ---

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
        {
            'id': el.id, 
            'text': f"{el.identificador_unico} - {el.tipo_elemento.nombre}"
        }
        for el in elementos
    ]
    return JsonResponse(resultados, safe=False)

@require_GET
def obtener_pasos_y_avance_elemento(request, elemento_id):
    try:
        elemento = ElementoConstructivo.objects.select_related('tipo_elemento').get(pk=elemento_id)
    except ElementoConstructivo.DoesNotExist:
        return JsonResponse({'error': 'Elemento no encontrado'}, status=404)

    pasos_definidos = PasoProcesoTipoElemento.objects.filter(
        tipo_elemento=elemento.tipo_elemento
    ).select_related('proceso').order_by('orden')

    avances_registrados = AvanceProcesoElemento.objects.filter(
        elemento=elemento
    ).values('paso_proceso_id', 'fecha_finalizacion')

    mapa_avances = {avance['paso_proceso_id']: avance['fecha_finalizacion'].strftime('%Y-%m-%d')
                    for avance in avances_registrados if avance['fecha_finalizacion']}

    pasos_data = []
    for paso in pasos_definidos:
        pasos_data.append({
            'paso_id': paso.id,
            'nombre_proceso': paso.proceso.nombre,
            'orden': paso.orden,
            'fecha_guardada': mapa_avances.get(paso.id, None) 
        })

    return JsonResponse({'pasos': pasos_data})

def registrar_avance_bim(request):
    if request.method == 'POST':
        elementos_ids_str = request.POST.get('elementos_ids', '')
        
        if not elementos_ids_str:
            messages.error(request, "No se seleccionó ningún elemento.")
            return redirect('registrar_avance_bim')

        try:
            ids_list = [int(id_str) for id_str in elementos_ids_str.split(',') if id_str.isdigit()]
        except ValueError:
             messages.error(request, "Error en los IDs de los elementos.")
             return redirect('registrar_avance_bim')

        if not ids_list:
             messages.error(request, "Lista de elementos vacía.")
             return redirect('registrar_avance_bim')

        pasos_ids_enviados = request.POST.getlist('paso_id')
        fechas_enviadas = request.POST.getlist('fecha_finalizacion')

        if len(pasos_ids_enviados) != len(fechas_enviadas):
             messages.error(request, "Error en los datos enviados.")
             return redirect('registrar_avance_bim') 

        cantidad_actualizados = 0
        errores_guardado = []

        try:
            with transaction.atomic():
                primer_elemento = ElementoConstructivo.objects.get(pk=ids_list[0])
                tipo_referencia = primer_elemento.tipo_elemento

                elementos_queryset = ElementoConstructivo.objects.filter(pk__in=ids_list)
                
                if elementos_queryset.filter(tipo_elemento=tipo_referencia).count() != len(ids_list):
                    raise ValidationError("Todos los elementos seleccionados deben ser del mismo Tipo (ej. todos Columnas). No mezcles tipos.")

                for elemento in elementos_queryset:
                    cambio_realizado_en_elemento = False
                    for paso_id_str, fecha_str in zip(pasos_ids_enviados, fechas_enviadas):
                        if fecha_str: 
                            try:
                                paso_id = int(paso_id_str)
                                paso = PasoProcesoTipoElemento.objects.get(pk=paso_id, tipo_elemento=tipo_referencia)
                                fecha_obj = date.fromisoformat(fecha_str)
                                
                                if fecha_obj > date.today():
                                    raise ValidationError("La fecha no puede ser futura.")

                                AvanceProcesoElemento.objects.update_or_create(
                                    elemento=elemento,
                                    paso_proceso=paso,
                                    defaults={'fecha_finalizacion': fecha_obj}
                                )
                                cambio_realizado_en_elemento = True

                            except Exception as e:
                                errores_guardado.append(f"Error en {elemento.identificador_unico}: {e}")
                    
                    if cambio_realizado_en_elemento:
                        cantidad_actualizados += 1

                if errores_guardado:
                     raise ValidationError(errores_guardado)

            if cantidad_actualizados > 0:
                messages.success(request, f"¡Éxito! Se actualizaron {cantidad_actualizados} elementos correctamente.")
            else:
                messages.warning(request, "No se realizaron cambios (las fechas estaban vacías).")

            return redirect('registrar_avance_bim')

        except ValidationError as e:
            if hasattr(e, 'message'):
                 messages.error(request, e.message)
            elif hasattr(e, 'messages'):
                 for err in e.messages:
                     messages.error(request, err)
            else:
                 messages.error(request, str(e))
                 
        except ElementoConstructivo.DoesNotExist:
             messages.error(request, "Uno de los elementos seleccionados no existe.")
        except Exception as e: 
            messages.error(request, f"Error inesperado: {e}")

    form = SeleccionarElementoForm()
    context = {
        'form': form,
        'url_buscar_elementos': reverse('api_buscar_elementos'),
        'url_obtener_pasos_base': reverse('api_obtener_pasos', args=['0']), 
    }
    return render(request, 'actividades/registrar_avance_bim.html', context)


class ElementoStatusAPIView(ListAPIView):
    serializer_class = ElementoBIM_GUID_Serializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ElementoBIM_GUID.objects.select_related(
            'elemento_constructivo',
            'elemento_constructivo__tipo_elemento'
        ).annotate(
            total_pasos=Count(
                'elemento_constructivo__tipo_elemento__pasos_proceso', 
                distinct=True
            ),
            pasos_completados=Count(
                'elemento_constructivo__avances_proceso', 
                distinct=True
            ),
            ultima_fecha=Max('elemento_constructivo__avances_proceso__fecha_finalizacion'),
            primera_fecha=Min('elemento_constructivo__avances_proceso__fecha_finalizacion')
        )
            
@require_GET
def api_generar_rango(request):
    patron = request.GET.get('patron', '')    
    tipo_rango = request.GET.get('tipo', 'numero') 
    inicio = request.GET.get('inicio', '')
    fin = request.GET.get('fin', '')
    usar_ceros = request.GET.get('ceros') == 'true'

    if not patron or not inicio or not fin:
        return JsonResponse({'error': 'Faltan parámetros (patrón, inicio o fin).'}, status=400)
    
    if '{}' not in patron:
         return JsonResponse({'error': 'El patrón debe incluir "{}" donde cambia el valor.'}, status=400)

    candidatos = []

    try:
        if tipo_rango == 'numero':
            start_int = int(inicio)
            end_int = int(fin)
            if start_int > end_int:
                return JsonResponse({'error': 'El inicio numérico debe ser menor al fin.'}, status=400)
            for i in range(start_int, end_int + 1):
                val = str(i).zfill(2) if usar_ceros else str(i)
                candidatos.append(patron.format(val))

        elif tipo_rango == 'letra':
            if len(inicio) != 1 or len(fin) != 1:
                return JsonResponse({'error': 'Para rangos de letras, usa solo un caracter (Ej: A a F).'}, status=400)
            start_ord = ord(inicio.upper())
            end_ord = ord(fin.upper())
            if start_ord > end_ord:
                return JsonResponse({'error': 'La letra inicial debe ir antes que la final en el alfabeto.'}, status=400)
            for i in range(start_ord, end_ord + 1):
                val = chr(i) 
                candidatos.append(patron.format(val))
        else:
             return JsonResponse({'error': 'Tipo de rango no válido.'}, status=400)

    except ValueError:
        return JsonResponse({'error': 'Los valores de inicio/fin no son válidos para el tipo seleccionado.'}, status=400)

    elementos_encontrados = ElementoConstructivo.objects.filter(
        identificador_unico__in=candidatos
    ).values('id', 'identificador_unico')

    data = list(elementos_encontrados)
    resultados_json = [{'id': e['id'], 'text': e['identificador_unico']} for e in data]

    return JsonResponse({
        'encontrados': len(resultados_json),
        'buscados': len(candidatos),
        'resultados': resultados_json
    })


# --- CRONOGRAMA POR ZONAS (REESCRITO) ---

def vista_cronograma(request):
    """
    Vista reescrita para mostrar tareas filtradas por Zona.
    """
    proyecto = Proyecto.objects.first()
    if not proyecto:
        messages.error(request, "No hay proyectos registrados.")
        return redirect('pagina_principal')

    # 1. Obtener todas las zonas para el selector
    zonas_list = AreaDeTrabajo.objects.all().order_by('nombre')

    # 2. Verificar si hay una zona seleccionada en el GET
    zona_seleccionada_id = request.GET.get('zona_id')
    tareas = None
    zona_obj = None

    if zona_seleccionada_id:
        try:
            zona_obj = AreaDeTrabajo.objects.get(pk=zona_seleccionada_id)
            # 3. Filtrar tareas que tengan ESTA zona asignada
            # Usamos prefetch_related para eficiencia si tuviéramos sub-tareas,
            # pero aquí traemos la lista plana o jerárquica que coincida.
            tareas = Cronograma.objects.filter(
                proyecto=proyecto,
                zonas=zona_obj
            ).order_by('fecha_inicio_prog') 
        except AreaDeTrabajo.DoesNotExist:
            messages.error(request, "La zona seleccionada no existe.")

    context = {
        'proyecto': proyecto,
        'zonas_list': zonas_list,
        'zona_seleccionada': zona_obj,
        'tareas': tareas
    }
    return render(request, 'actividades/cronograma_list.html', context)


def crear_tarea_cronograma(request):
    proyecto = Proyecto.objects.first()
    if not proyecto:
        messages.error(request, "No hay proyecto activo.")
        return redirect('pagina_principal')
    
    padre_id = request.GET.get('padre')
    
    form = CronogramaForm(request.POST or None, initial={'padre': padre_id}, proyecto=proyecto)
    
    if request.method == 'POST':
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.proyecto = proyecto
            tarea.save()
            # Guardamos la relación ManyToMany (zonas)
            form.save_m2m()
            
            messages.success(request, f"Actividad '{tarea.nombre}' creada exitosamente.")
            return redirect('vista_cronograma')
            
    return render(request, 'actividades/cronograma_crear.html', {
        'form': form, 
        'proyecto': proyecto
    })


def editar_fechas_cronograma(request, pk):
    tarea = get_object_or_404(Cronograma, pk=pk)
    form = CronogramaHibridoForm(request.POST or None, instance=tarea)
    
    if request.method == 'POST':
        if form.is_valid():
            tarea_guardada = form.save()
            # El formulario CronogramaHibridoForm no incluía 'zonas' en su definición
            # original, asegúrate de que esté en fields o save_m2m no hará nada nuevo.
            # (Ya lo añadimos en el paso anterior de forms.py)
            
            messages.success(request, f"Actividad '{tarea.nombre}' actualizada.")
            return redirect('vista_cronograma')

    return render(request, 'actividades/cronograma_form.html', {
        'form': form, 
        'tarea': tarea
    })

def vista_cronograma_movil(request):
    proyecto = Proyecto.objects.first() 
    
    if request.method == 'POST':
        tarea_id = request.POST.get('tarea_id')
        inicio_real = request.POST.get('fecha_inicio_real')
        fin_real = request.POST.get('fecha_fin_real')
        
        if tarea_id:
            tarea = get_object_or_404(Cronograma, pk=tarea_id)
            tarea.fecha_inicio_real = inicio_real if inicio_real else None
            tarea.fecha_fin_real = fin_real if fin_real else None
            tarea.save()
            messages.success(request, f"Actualizado: {tarea.nombre}")
            return redirect('cronograma_movil')
        else:
            messages.error(request, "Error: No se seleccionó ninguna tarea.")

    categorias_nivel_1 = Cronograma.objects.filter(
        proyecto=proyecto,
        padre__isnull=True
    ).order_by('id')

    context = {
        'proyecto': proyecto,
        'categorias_nivel_1': categorias_nivel_1
    }
    return render(request, 'actividades/cronograma_actualizar_movil.html', context)


@require_GET
def api_hijos_cronograma(request, padre_id):
    hijos = Cronograma.objects.filter(padre_id=padre_id).values('id', 'nombre').order_by('id')
    return JsonResponse(list(hijos), safe=False)


@require_GET
def api_detalle_tarea(request, tarea_id):
    tarea = get_object_or_404(Cronograma, pk=tarea_id)
    data = {
        'id': tarea.id,
        'nombre': tarea.nombre,
        'fecha_inicio_real': tarea.fecha_inicio_real,
        'fecha_fin_real': tarea.fecha_fin_real,
    }
    return JsonResponse(data)


# --- NUEVAS VISTAS: OBSERVACIONES ---

def lista_observaciones(request):
    """
    Muestra la lista de observaciones con filtros.
    """
    zonas = AreaDeTrabajo.objects.all()
    
    # Filtros
    zona_id = request.GET.get('zona_filtro')
    busqueda = request.GET.get('busqueda')
    
    observaciones = Observacion.objects.all().order_by('-fecha')
    
    if zona_id:
        observaciones = observaciones.filter(zona_id=zona_id)
    if busqueda:
        observaciones = observaciones.filter(nombre__icontains=busqueda)
        
    context = {
        'observaciones': observaciones,
        'zonas': zonas,
        'zona_seleccionada_id': int(zona_id) if zona_id else None,
        'busqueda': busqueda
    }
    return render(request, 'actividades/observacion_list.html', context)

def crear_observacion(request):
    """
    Vista para registrar una nueva observación.
    """
    # CAMBIO AQUI: Añadido request.FILES or None
    form = ObservacionForm(request.POST or None, request.FILES or None)
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Observación registrada correctamente.")
                return redirect('lista_observaciones')
            except IntegrityError:
                messages.error(request, "Ya existe una observación con este nombre en esta zona y fecha.")
        else:
            messages.error(request, "Corrige los errores en el formulario.")
            
    return render(request, 'actividades/observacion_form.html', {'form': form})

@login_required
def marcar_observacion_resuelta(request, pk):
    # ... [CÓDIGO EXISTENTE DE ESTA FUNCIÓN SIN CAMBIOS] ...
    observacion = get_object_or_404(Observacion, pk=pk)
    
    if not observacion.resuelto:
        observacion.resuelto = True
        observacion.resuelto_por = request.user
        observacion.fecha_resolucion = date.today()
        observacion.save()
        messages.success(request, f"Observación '{observacion.nombre}' marcada como resuelta.")
    else:
        observacion.resuelto = False
        observacion.resuelto_por = None
        observacion.fecha_resolucion = None
        observacion.save()
        messages.warning(request, f"Observación '{observacion.nombre}' reabierta.")
        
    next_url = request.META.get('HTTP_REFERER', 'lista_observaciones')
    return redirect(next_url)

# --- NUEVA FUNCIÓN AÑADIDA ---
@login_required
def eliminar_observacion(request, pk):
    """
    Permite borrar una observación. Requiere login.
    """
    observacion = get_object_or_404(Observacion, pk=pk)
    
    if request.method == 'POST':
        observacion.delete()
        messages.success(request, "La observación ha sido eliminada permanentemente.")
        return redirect('lista_observaciones')
    
    return render(request, 'actividades/observacion_confirmar_borrado.html', {'observacion': observacion})