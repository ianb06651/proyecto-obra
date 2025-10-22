# actividades/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from datetime import date, timedelta
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError # Importar ValidationError

from .forms import (
    ReporteMaquinariaForm, ReportePersonalForm, ActividadForm,
    ConsultaClimaForm, AvanceDiarioForm, AvancePorZonaFormSet,
    MetaPorZonaFormSet
)
from .services import obtener_y_guardar_clima
from .models import (
    Actividad, AvanceDiario, Semana, PartidaActividad, ReportePersonal,
    Empresa, Cargo, AreaDeTrabajo, ReporteDiarioMaquinaria, Proyecto,
    AvancePorZona, MetaPorZona
)

# --- Vistas sin cambios funcionales directos ---
def es_staff(user):
    return user.is_staff

# --- Vistas Modificadas para el nuevo modelo de datos ---

def historial_avance_view(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    semanas = Semana.objects.all()
    actividades_filtrables = Actividad.objects.filter(proyecto=proyecto, sub_actividades__isnull=True).order_by('nombre')

    fecha_corte_total = date.today()
    total_programado_pv_acumulado = proyecto.get_valor_planeado_a_fecha(fecha_corte_total)

    avances_totales_acumulados = AvanceDiario.objects.filter(
        actividad__proyecto=proyecto,
        fecha_reporte__lte=fecha_corte_total
    ).prefetch_related('avances_por_zona')

    total_real_ev_acumulado = sum(avance.cantidad_total for avance in avances_totales_acumulados)
    spi_acumulado = (total_real_ev_acumulado / total_programado_pv_acumulado) if total_programado_pv_acumulado and total_programado_pv_acumulado > 0 else 0

    semana_seleccionada_id = request.GET.get('semana_filtro')
    actividad_seleccionada_id = request.GET.get('actividad_filtro')

    avances_para_tabla = AvanceDiario.objects.filter(actividad__proyecto=proyecto).select_related('actividad', 'empresa').prefetch_related('avances_por_zona')

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
            data['formset'] = MetaPorZonaFormSet(self.request.POST, queryset=MetaPorZona.objects.none())
        else:
            data['formset'] = MetaPorZonaFormSet(queryset=MetaPorZona.objects.none())
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']

        if formset.is_valid():
            try:
                with transaction.atomic():
                    self.object = form.save()
                    instances = formset.save(commit=False)
                    zonas_definidas = set()
                    for instance in instances:
                        if instance.zona and instance.meta is not None:
                             if instance.zona in zonas_definidas:
                                 form.add_error(None, f"La zona '{instance.zona}' está duplicada en el desglose.")
                                 return self.form_invalid(form)
                             zonas_definidas.add(instance.zona)
                             instance.actividad = self.object
                             instance.save()

                    formset.save_m2m()
                    for form_to_delete in formset.deleted_forms:
                        if form_to_delete.instance.pk:
                            form_to_delete.instance.delete()

                    messages.success(self.request, 'Actividad con metas por zona creada con éxito.')

            except IntegrityError:
                messages.error(self.request, "Error de integridad al guardar la actividad o sus metas.")
                return self.form_invalid(form)
            except Exception as e:
                 messages.error(self.request, f"Ocurrió un error inesperado: {e}")
                 return self.form_invalid(form)
        else:
            messages.error(self.request, 'Por favor, corrige los errores en el desglose de metas por zona.')
            if formset.non_form_errors():
                # CORREGIDO: Usar self.request
                messages.warning(self.request, f"Errores generales en el desglose: {formset.non_form_errors()}")
            return self.form_invalid(form)

        return super().form_valid(form)

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

        if formset.is_valid():
            try:
                with transaction.atomic():
                    self.object = form.save()
                    instances = formset.save(commit=False)
                    zonas_definidas = set()
                    for instance in instances:
                        if instance.zona and instance.meta is not None:
                            if instance.zona in zonas_definidas:
                                form.add_error(None, f"La zona '{instance.zona}' está duplicada en el desglose.")
                                return self.form_invalid(form)
                            zonas_definidas.add(instance.zona)
                            instance.actividad = self.object
                            instance.save()

                    formset.save_m2m()
                    for form_to_delete in formset.deleted_forms:
                        if form_to_delete.instance.pk:
                            form_to_delete.instance.delete()

                    messages.success(self.request, 'Actividad actualizada con éxito.')

            except IntegrityError:
                messages.error(self.request, "Error de integridad al actualizar la actividad o sus metas.")
                return self.form_invalid(form)
            except Exception as e:
                 messages.error(self.request, f"Ocurrió un error inesperado: {e}")
                 return self.form_invalid(form)
        else:
            messages.error(self.request, 'Por favor, corrige los errores en el desglose de metas por zona.')
            if formset.non_form_errors():
                 # CORREGIDO: Usar self.request
                messages.warning(self.request, f"Errores generales en el desglose: {formset.non_form_errors()}")
            return self.form_invalid(form)

        return super().form_valid(form)


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

    form = AvanceDiarioForm(request.POST or None, actividad_queryset=actividad_queryset)
    formset = AvancePorZonaFormSet(request.POST or None, queryset=AvancePorZona.objects.none())

    if request.method == 'POST':
        if form.is_valid() and formset.is_valid():
            actividad = form.cleaned_data['actividad']
            fecha = form.cleaned_data['fecha_reporte']
            empresa = form.cleaned_data['empresa']

            avance_existente = AvanceDiario.objects.filter(
                actividad=actividad, fecha_reporte=fecha, empresa=empresa
            ).first()

            if avance_existente:
                 messages.warning(request, f"Ya existe un registro para {actividad} el {fecha} por {empresa}. Editando el registro existente.")
                 return redirect('editar_avance', pk=avance_existente.pk)

            try:
                with transaction.atomic():
                    avance_diario = form.save(commit=False)
                    avance_diario.save()

                    instances = formset.save(commit=False)
                    zonas_definidas = set()
                    zonas_guardadas = 0
                    for instance in instances:
                        if instance.zona and instance.cantidad is not None:
                            if instance.zona in zonas_definidas:
                                form.add_error(None, f"La zona '{instance.zona}' está duplicada.")
                                raise ValidationError("Zona duplicada")
                            zonas_definidas.add(instance.zona)
                            instance.avance_diario = avance_diario
                            instance.save()
                            zonas_guardadas += 1

                    if zonas_guardadas == 0:
                        form.add_error(None, "Debes registrar el avance para al menos una zona.")
                        raise ValidationError("Sin zonas")

                    messages.success(request, 'Avance diario por zonas guardado con éxito.')
                    return redirect('registrar_avance')

            # CORREGIDO: Quitar 'as ve'
            except ValidationError:
                pass
            except IntegrityError:
                messages.error(request, "Error de integridad. No se pudo guardar el avance.")
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
        else:
            messages.error(request, 'Por favor, corrige los errores mostrados en el formulario.')
            if formset.errors or formset.non_form_errors():
                 messages.warning(request, f'Errores en el desglose por zonas: {formset.non_form_errors() or formset.errors}')

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

    if request.method == 'POST':
        form = AvanceDiarioForm(request.POST, instance=avance)
        formset = AvancePorZonaFormSet(request.POST, instance=avance)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    avance_diario = form.save()
                    instances = formset.save(commit=False)
                    zonas_definidas = set()
                    zonas_guardadas = 0
                    for instance in instances:
                        if instance.zona and instance.cantidad is not None:
                            if instance.zona in zonas_definidas:
                                form.add_error(None, f"La zona '{instance.zona}' está duplicada.")
                                raise ValidationError("Zona duplicada")
                            zonas_definidas.add(instance.zona)
                            instance.avance_diario = avance_diario
                            instance.save()
                            zonas_guardadas += 1

                    for form_to_delete in formset.deleted_forms:
                        if form_to_delete.instance.pk:
                            form_to_delete.instance.delete()

                    if avance_diario.avances_por_zona.count() == 0 and zonas_guardadas == 0:
                        form.add_error(None, "No puedes eliminar todas las zonas. Debe quedar al menos una.")
                        raise ValidationError("Todas las zonas eliminadas")

                    messages.success(request, 'El avance diario y su desglose han sido actualizados.')
                    return redirect('historial_avance', proyecto_id=avance.actividad.proyecto.id)

            # CORREGIDO: Quitar 'as ve'
            except ValidationError:
                pass
            except IntegrityError:
                 messages.error(request, "Error de integridad al actualizar.")
            except Exception as e:
                messages.error(request, f'Ocurrió un error inesperado: {e}')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario o en el desglose.')
            if formset.errors or formset.non_form_errors():
                 messages.warning(request, f'Errores en el desglose: {formset.non_form_errors() or formset.errors}')

    else:
        form = AvanceDiarioForm(instance=avance)
        formset = AvancePorZonaFormSet(instance=avance)

    contexto = {
        'form': form,
        'formset': formset,
        'avance': avance,
    }
    return render(request, 'actividades/editar_avance.html', contexto)


# --- Vistas restantes sin cambios ---

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

    contexto = {'form': form, 'reporte': reporte}
    return render(request, 'actividades/vista_clima.html', contexto)