from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from datetime import date
from django.db import IntegrityError, transaction

# MODIFICADO: Se importan los nuevos FormSets y modelos.
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
    
    semana_seleccionada_id = request.GET.get('semana_filtro')
    actividad_seleccionada_id = request.GET.get('actividad_filtro')

    avances_reales = AvanceDiario.objects.filter(actividad__proyecto=proyecto).select_related('actividad', 'empresa').prefetch_related('avances_por_zona')
    
    total_programado_pv = 0
    fecha_corte = date.today()
    
    actividad_base_calculo = proyecto
    actividad_seleccionada = None

    if actividad_seleccionada_id:
        actividad_seleccionada = get_object_or_404(Actividad, pk=actividad_seleccionada_id)
        avances_reales = avances_reales.filter(actividad=actividad_seleccionada)
        actividad_base_calculo = actividad_seleccionada

    if semana_seleccionada_id:
        try:
            semana_obj = Semana.objects.get(pk=semana_seleccionada_id)
            avances_reales = avances_reales.filter(fecha_reporte__range=[semana_obj.fecha_inicio, semana_obj.fecha_fin])
            total_programado_pv = actividad_base_calculo.get_valor_planeado_en_rango(
                semana_obj.fecha_inicio, semana_obj.fecha_fin
            )
            fecha_corte = semana_obj.fecha_fin
        except Semana.DoesNotExist:
            total_programado_pv = actividad_base_calculo.get_valor_planeado_a_fecha(fecha_corte)
    else:
        total_programado_pv = actividad_base_calculo.get_valor_planeado_a_fecha(fecha_corte)

    # MODIFICADO: El cálculo del total real ahora usa la propiedad `cantidad_total`.
    # Se realiza en Python porque la propiedad no puede ser agregada directamente en la BD.
    total_real_ev = sum(avance.cantidad_total for avance in avances_reales)
    
    rendimiento_spi = (total_real_ev / total_programado_pv * 100) if total_programado_pv > 0 else 0
    
    context = {
        'proyecto': proyecto,
        'semanas': semanas,
        'actividades_filtrables': actividades_filtrables,
        'semana_seleccionada_id': semana_seleccionada_id,
        'actividad_seleccionada_id': actividad_seleccionada_id,
        'actividad_seleccionada': actividad_seleccionada,
        'total_programado_pv': total_programado_pv,
        'total_real_ev': total_real_ev,
        'rendimiento_spi': rendimiento_spi,
        'fecha_corte': fecha_corte,
        'avances_reales': avances_reales.order_by('-fecha_reporte')
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

    # MODIFICADO: Se añade el formset al contexto
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = MetaPorZonaFormSet(self.request.POST, queryset=MetaPorZona.objects.none())
        else:
            data['formset'] = MetaPorZonaFormSet(queryset=MetaPorZona.objects.none())
        return data

    # MODIFICADO: Se añade la lógica para procesar el formset
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        tipo_registro = form.cleaned_data.get('tipo_registro_meta')

        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                
                if tipo_registro == 'por_zona':
                    if formset.is_valid():
                        self.object.save()
                        instances = formset.save(commit=False)
                        for instance in instances:
                            instance.actividad = self.object
                            instance.save()
                        messages.success(self.request, 'Actividad con metas por zona creada con éxito.')
                    else:
                        return self.form_invalid(form)
                else: # tipo_registro == 'general'
                    self.object.save()
                    messages.success(self.request, 'Actividad con meta general creada con éxito.')

        except IntegrityError:
            messages.error(self.request, "Error de integridad. Ya existe una actividad con esa configuración.")
            return self.form_invalid(form)
        
        return super().form_valid(form)

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

    # MODIFICADO: Se añade el formset con datos existentes al contexto
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = MetaPorZonaFormSet(self.request.POST, instance=self.object)
        else:
            data['formset'] = MetaPorZonaFormSet(instance=self.object)
        return data

    # MODIFICADO: Lógica de guardado para el formset
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        tipo_registro = form.cleaned_data.get('tipo_registro_meta')

        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                
                if tipo_registro == 'por_zona':
                    if formset.is_valid():
                        # Primero se eliminan las metas por zona anteriores
                        MetaPorZona.objects.filter(actividad=self.object).delete()
                        self.object.save()
                        instances = formset.save(commit=False)
                        for instance in instances:
                            instance.actividad = self.object
                            instance.save()
                        messages.success(self.request, 'Actividad actualizada con éxito.')
                    else:
                        return self.form_invalid(form)
                else: # tipo_registro == 'general'
                    # Si se cambia a general, se borran los desgloses existentes
                    MetaPorZona.objects.filter(actividad=self.object).delete()
                    self.object.save()
                    messages.success(self.request, 'Actividad actualizada con éxito.')

        except IntegrityError:
            messages.error(self.request, "Error de integridad al actualizar.")
            return self.form_invalid(form)
            
        return super().form_valid(form)


# --- VISTA "registrar_avance" TOTALMENTE REESCRITA ---
def registrar_avance(request):
    proyecto = Proyecto.objects.first()
    if not proyecto:
        messages.error(request, 'Error: No hay ningún proyecto registrado en el sistema.')
        return redirect('pagina_principal')

    if request.method == 'POST':
        form = AvanceDiarioForm(request.POST)
        formset = AvancePorZonaFormSet(request.POST, queryset=AvancePorZona.objects.none())

        if form.is_valid():
            tipo_registro = form.cleaned_data.get('tipo_registro')
            
            try:
                with transaction.atomic():
                    avance_diario = form.save(commit=False)
                    
                    # Lógica para guardar el desglose por zona
                    if tipo_registro == 'por_zona':
                        if formset.is_valid() and formset.has_changed():
                            avance_diario.save() # Guardar el objeto principal para obtener un ID
                            
                            # Vincular y guardar cada formulario del formset
                            instances = formset.save(commit=False)
                            for instance in instances:
                                instance.avance_diario = avance_diario
                                instance.save()
                            
                            messages.success(request, '¡Avance por zonas registrado con éxito!')
                            return redirect('registrar_avance')
                        else:
                            # Si el formset no es válido, se muestra el error
                            messages.error(request, 'Por favor, corrige los errores en el desglose por zonas.')
                    
                    # Lógica para guardar el avance general
                    else: # tipo_registro == 'general'
                        avance_diario.save()
                        messages.success(request, '¡Avance general registrado con éxito!')
                        return redirect('registrar_avance')

            except IntegrityError:
                messages.error(request, 'Error: Ya existe un registro para esta actividad, fecha y empresa.')
            except Exception as e:
                messages.error(request, f'Ocurrió un error inesperado: {e}')
    else:
        form = AvanceDiarioForm()
        formset = AvancePorZonaFormSet(queryset=AvancePorZona.objects.none())

    # Lógica para filtrar actividades (sin cambios)
    form.fields['actividad'].queryset = Actividad.objects.filter(
        proyecto=proyecto,
        sub_actividades__isnull=True
    ).order_by('nombre')
    
    partidas = PartidaActividad.objects.all()
    partida_seleccionada_id = request.GET.get('partida_filtro')
    
    if partida_seleccionada_id:
        form.fields['actividad'].queryset = form.fields['actividad'].queryset.filter(
            partida_id=partida_seleccionada_id
        )

    contexto = {
        'form': form,
        'formset': formset, # Añadir el formset al contexto
        'proyecto': proyecto,
        'partidas': partidas,
        'partida_seleccionada_id': partida_seleccionada_id,
    }
    return render(request, 'actividades/registrar_avance.html', contexto)


# --- VISTA "editar_avance" TOTALMENTE REESCRITA ---
@login_required
@user_passes_test(es_staff)
def editar_avance(request, pk):
    avance = get_object_or_404(AvanceDiario, pk=pk)
    tiene_desglose = avance.avances_por_zona.exists()

    if request.method == 'POST':
        form = AvanceDiarioForm(request.POST, instance=avance)
        formset = AvancePorZonaFormSet(request.POST, queryset=avance.avances_por_zona.all())

        # El campo 'tipo_registro' no se envía, así que lo eliminamos de la validación
        if 'tipo_registro' in form.fields:
            del form.fields['tipo_registro']

        try:
            with transaction.atomic():
                # Verificamos si se enviaron datos del formset
                if 'form-TOTAL_FORMS' in request.POST:
                    if formset.is_valid():
                        formset.save()
                        messages.success(request, 'El desglose por zonas ha sido actualizado.')
                        return redirect('historial_avance', proyecto_id=avance.actividad.proyecto.id)
                    else:
                        messages.error(request, 'Por favor, corrige los errores en el desglose.')
                else:
                    if form.is_valid():
                        avance.avances_por_zona.all().delete()
                        form.save()
                        messages.success(request, 'El avance general ha sido actualizado.')
                        return redirect('historial_avance', proyecto_id=avance.actividad.proyecto.id)
                    else:
                        messages.error(request, 'Por favor, corrige los errores en el formulario.')
        except Exception as e:
            messages.error(request, f'Ocurrió un error inesperado: {e}')
    else:
        form = AvanceDiarioForm(instance=avance)
        formset = AvancePorZonaFormSet(queryset=avance.avances_por_zona.all())
        # Eliminamos el campo que no se usa en la plantilla de edición
        if 'tipo_registro' in form.fields:
            del form.fields['tipo_registro']
    
    contexto = {
        'form': form,
        'formset': formset,
        'avance': avance,
        'tiene_desglose': tiene_desglose
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