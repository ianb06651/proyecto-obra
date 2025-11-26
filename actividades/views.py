# actividades/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q, Prefetch, Count 
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from datetime import date, timedelta
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError 

# --- Importaciones para la NUEVA API (Paso 6) ---
from rest_framework.generics import ListAPIView
from django.db.models import Count, Max, Min 
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
# --- 1. MODIFICADO: Importar el nuevo Serializer ---
from .serializers import ElementoBIM_GUID_Serializer
# --- Fin importaciones API ---


from .forms import (
    ReporteMaquinariaForm, ReportePersonalForm, ActividadForm,
    ConsultaClimaForm, AvanceDiarioForm, AvancePorZonaFormSet,
    MetaPorZonaFormSet, SeleccionarElementoForm
)
from .services import obtener_y_guardar_clima
from .models import (
    Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal,
    Empresa, Cargo, AreaDeTrabajo, ReporteDiarioMaquinaria, Proyecto,
    AvancePorZona, MetaPorZona, ElementoConstructivo, 
    PasoProcesoTipoElemento, AvanceProcesoElemento, TipoElemento,
    ElementoBIM_GUID # <--- IMPORTAR EL NUEVO MODELO
)

# --- Vistas sin cambios funcionales directos ---
def es_staff(user):
    """
    Función de prueba para el decorador user_passes_test.
    Debe estar definida antes de ser usada.
    """
    return user.is_staff

# ... (El resto de tus vistas: historial_avance_view, etc. no cambian) ...
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
    spi_acumulado = (total_real_ev_acumulado / total_programado_pv_acumulado) if total_programado_pv_acumulado and total_programado_pv_acumulado > 0 else 0

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
                    return self.form_invalid(form) # Llama al método de abajo

                formset.save()
                messages.success(self.request, 'Actividad con metas por zona creada con éxito.')

        except IntegrityError:
            messages.error(self.request, "Error de integridad al guardar la actividad o sus metas.")
            return self.form_invalid(form)
        except Exception as e:
             messages.error(self.request, f"Ocurrió un error inesperado: {e}")
             return self.form_invalid(form)

        return super().form_valid(form)

    # --- MÉTODO AÑADIDO ---
    def form_invalid(self, form):
        """
        Se llama cuando el formulario principal (ActividadForm) no es válido.
        """
        # Añade un mensaje de error general. Los errores específicos de cada campo
        # se mostrarán automáticamente junto a los campos del formulario.
        messages.error(self.request, 'El formulario es inválido. Por favor, revisa los campos marcados en rojo.')
        
        # También nos aseguramos de pasar el formset inválido (si existe) de vuelta a la plantilla
        context = self.get_context_data(form=form)
        if self.request.POST:
            context['formset'] = MetaPorZonaFormSet(self.request.POST)
        
        return self.render_to_response(context)
    # --- FIN MÉTODO AÑADIDO ---

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
                # --- LÓGICA MODIFICADA ---
                # Se simplificó la comprobación de validez
                if not formset.is_valid():
                    messages.error(self.request, 'Por favor, corrige los errores en el desglose de metas por zona.')
                    if formset.non_form_errors():
                        messages.warning(self.request, f"Errores generales en el desglose: {formset.non_form_errors()}")
                    return self.form_invalid(form) # Llama al método de abajo
                # --- FIN LÓGICA MODIFICADA ---

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

    # --- MÉTODO AÑADIDO ---
    def form_invalid(self, form):
        """
        Se llama cuando el formulario principal (ActividadForm) no es válido.
        """
        messages.error(self.request, 'El formulario es inválido. Por favor, revisa los campos marcados en rojo.')
        
        # Aseguramos que el formset se pase correctamente en caso de error
        context = self.get_context_data(form=form)
        if self.request.POST:
            context['formset'] = MetaPorZonaFormSet(self.request.POST, instance=self.object)
        
        return self.render_to_response(context)
    # --- FIN MÉTODO AÑADIDO ---

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
                # --- MENSAJE AÑADIDO ---
                # El form.add_error se mostrará en el formulario, pero añadimos un mensaje global también
                messages.error(request, "Debes registrar el avance para al menos una zona.")
                # --- FIN MENSAJE AÑADIDO ---
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
@user_passes_test(es_staff) # Esta es la línea 318
def editar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    form = AvanceDiarioForm(request.POST or None, instance=avance)
    formset = AvancePorZonaFormSet(request.POST or None, instance=avance)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                if not form.is_valid() or not formset.is_valid():
                    # --- LÓGICA DE MENSAJES AÑADIDA ---
                    if not form.is_valid():
                        messages.error(request, 'El formulario principal es inválido. Revisa los campos de actividad, fecha y empresa.')
                    # --- FIN LÓGICA AÑADIDA ---
                    
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
            # --- MENSAJE AÑADIDO ---
            messages.error(request, "No puedes eliminar todas las zonas. Debe quedar al menos una.")
            # --- FIN MENSAJE AÑADIDO ---
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
        # --- BLOQUE AÑADIDO ---
        else:
            messages.error(request, "La fecha seleccionada no es válida. Por favor, corrígela.")
        # --- FIN BLOQUE AÑADIDO ---

    contexto = {'form': form, 'reporte': reporte}
    return render(request, 'actividades/vista_clima.html', contexto)

# --- VISTAS DE API PARA FORMULARIO BIM DINÁMICO ---

# --- 2. MODIFICAR buscar_elementos_constructivos ---
@require_GET
def buscar_elementos_constructivos(request):
    query = request.GET.get('term', '')
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Lógica de búsqueda OR actualizada
    # Busca en 'identificador_unico' O en la relación 'guids_bim__identificador_bim'
    elementos = ElementoConstructivo.objects.filter(
        Q(identificador_unico__icontains=query) |
        Q(guids_bim__identificador_bim__icontains=query)
    ).select_related('tipo_elemento').distinct()[:10] # .distinct() es clave
    
    # El texto de resultado ahora solo muestra el ID legible (código de ejes)
    resultados = [
        {
            'id': el.id, 
            'text': f"{el.identificador_unico} - {el.tipo_elemento.nombre}"
        }
        for el in elementos
    ]
    return JsonResponse(resultados, safe=False)
# --- FIN MODIFICACIÓN ---

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
        elemento_id = request.POST.get('elemento_id_hidden')
        if not elemento_id:
            messages.error(request, ("No se seleccionó ningún elemento constructivo."))
            return redirect('registrar_avance_bim')

        try:
            elemento = ElementoConstructivo.objects.get(pk=elemento_id)
        except ElementoConstructivo.DoesNotExist:
            messages.error(request, ("El elemento constructivo seleccionado ya no existe."))
            return redirect('registrar_avance_bim')

        pasos_ids_enviados = request.POST.getlist('paso_id')
        fechas_enviadas = request.POST.getlist('fecha_finalizacion')

        if len(pasos_ids_enviados) != len(fechas_enviadas):
             messages.error(request, ("Error en los datos enviados. Inténtalo de nuevo."))
             return redirect('registrar_avance_bim') 

        errores_guardado = []
        try:
            with transaction.atomic(): 
                for paso_id_str, fecha_str in zip(pasos_ids_enviados, fechas_enviadas):
                    try:
                        paso_id = int(paso_id_str)
                        paso = PasoProcesoTipoElemento.objects.get(pk=paso_id, tipo_elemento=elemento.tipo_elemento)

                        if fecha_str: 
                            try:
                                fecha_obj = date.fromisoformat(fecha_str)
                                if fecha_obj > date.today():
                                     raise ValidationError(("La fecha para '%(paso)s' no puede ser futura.") % {'paso': paso.proceso.nombre})

                                avance, created = AvanceProcesoElemento.objects.update_or_create(
                                    elemento=elemento,
                                    paso_proceso=paso,
                                    defaults={'fecha_finalizacion': fecha_obj}
                                )
                            except ValueError:
                                errores_guardado.append(("Formato de fecha inválido para '%(paso)s'. Use AAAA-MM-DD.") % {'paso': paso.proceso.nombre})
                            except ValidationError as e:
                                errores_guardado.append(e.message)

                        else: 
                            AvanceProcesoElemento.objects.filter(elemento=elemento, paso_proceso=paso).delete()

                    except (ValueError, PasoProcesoTipoElemento.DoesNotExist):
                        errores_guardado.append(("Paso de proceso inválido o incompatible encontrado (ID: %(id)s).") % {'id': paso_id_str})
                    except Exception as e: 
                        errores_guardado.append(f"Error inesperado al procesar paso {paso_id_str}: {e}")

                if errores_guardado:
                     raise ValidationError(errores_guardado) 

            messages.success(request, ("Avance para el elemento '%(elemento)s' guardado correctamente.") % {'elemento': elemento})
            return redirect('registrar_avance_bim')

        except ValidationError as e:
            for error_msg in e.messages:
                 messages.error(request, error_msg)
            form = SeleccionarElementoForm(initial={'elemento': elemento})
        except Exception as e: 
            messages.error(request, f"Error al guardar los datos: {e}")
            form = SeleccionarElementoForm() 

    else:
        form = SeleccionarElementoForm()

    context = {
        'form': form,
        'url_buscar_elementos': reverse('api_buscar_elementos'),
        'url_obtener_pasos_base': reverse('api_obtener_pasos', args=['0']), 
    }
    return render(request, 'actividades/registrar_avance_bim.html', context)


# --- 3. MODIFICAR VISTA DE API (ElementoStatusAPIView) ---
class ElementoStatusAPIView(ListAPIView):
    """
    API de solo lectura para exponer el estado y fechas de los elementos constructivos.
    """
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
            # Ya tenías la última fecha (Fin)
            ultima_fecha=Max('elemento_constructivo__avances_proceso__fecha_finalizacion'),
            
            # [2] AGREGAMOS LA PRIMERA FECHA (Inicio)
            primera_fecha=Min('elemento_constructivo__avances_proceso__fecha_finalizacion')
        )