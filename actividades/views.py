from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from datetime import date, timedelta 
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError # Importar ValidationError

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
    
    # --- CÁLCULOS PARA LAS TARJETAS (ACUMULATIVO TOTAL HASTA HOY) ---
    fecha_corte_total = date.today()
    
    # 1. PV Acumulado: Valor planeado para todo el proyecto hasta la fecha actual.
    total_programado_pv_acumulado = proyecto.get_valor_planeado_a_fecha(fecha_corte_total)

    # 2. EV Acumulado: Suma de TODOS los avances reales registrados en la historia del proyecto hasta hoy.
    avances_totales_acumulados = AvanceDiario.objects.filter(
        actividad__proyecto=proyecto,
        fecha_reporte__lte=fecha_corte_total
    ).prefetch_related('avances_por_zona')
    total_real_ev_acumulado = sum(avance.cantidad_total for avance in avances_totales_acumulados)

    # 3. SPI Acumulado: El KPI global que coincidirá con Power BI.
    spi_acumulado = (total_real_ev_acumulado / total_programado_pv_acumulado) if total_programado_pv_acumulado > 0 else 0

    # --- LÓGICA DE FILTRADO SOLO PARA LA TABLA DE ABAJO ---
    semana_seleccionada_id = request.GET.get('semana_filtro')
    actividad_seleccionada_id = request.GET.get('actividad_filtro')
    
    # Empezamos con todos los avances y luego filtramos
    avances_para_tabla = AvanceDiario.objects.filter(actividad__proyecto=proyecto).select_related('actividad', 'empresa').prefetch_related('avances_por_zona')
    
    if actividad_seleccionada_id:
        avances_para_tabla = avances_para_tabla.filter(actividad_id=actividad_seleccionada_id)

    # Si se selecciona una semana, la tabla muestra esa semana
    if semana_seleccionada_id:
        semana_obj = get_object_or_404(Semana, pk=semana_seleccionada_id)
        avances_para_tabla = avances_para_tabla.filter(fecha_reporte__range=[semana_obj.fecha_inicio, semana_obj.fecha_fin])
    # Si no, la tabla muestra las últimas 2 semanas por defecto
    else:
        fecha_inicio_filtro_tabla = date.today() - timedelta(weeks=2)
        avances_para_tabla = avances_para_tabla.filter(fecha_reporte__gte=fecha_inicio_filtro_tabla)
    
    context = {
        'proyecto': proyecto,
        'semanas': semanas,
        'actividades_filtrables': actividades_filtrables,
        'semana_seleccionada_id': semana_seleccionada_id,
        'actividad_seleccionada_id': actividad_seleccionada_id,
        
        # Se pasan los valores ACUMULADOS a las tarjetas de resumen
        'total_programado_pv': total_programado_pv_acumulado,
        'total_real_ev': total_real_ev_acumulado,
        'rendimiento_spi': spi_acumulado,
        'fecha_corte': fecha_corte_total,
        
        # La tabla de abajo sigue usando la lista FILTRADA de avances
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

    # Se preparan las instancias del form y formset para ambos casos (GET y POST fallido)
    form = AvanceDiarioForm()
    formset = AvancePorZonaFormSet(queryset=AvancePorZona.objects.none())

    if request.method == 'POST':
        instance = None
        actividad_id = request.POST.get('actividad')
        fecha_reporte = request.POST.get('fecha_reporte')
        empresa_id = request.POST.get('empresa')

        if actividad_id and fecha_reporte and empresa_id:
            instance = AvanceDiario.objects.filter(
                actividad_id=actividad_id,
                fecha_reporte=fecha_reporte,
                empresa_id=empresa_id
            ).first()

        form = AvanceDiarioForm(request.POST, instance=instance)
        formset = AvancePorZonaFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    avance_diario = form.save()
                    tipo_registro = form.cleaned_data.get('tipo_registro')
                    
                    if tipo_registro == 'por_zona':
                        # Limpiamos el campo general para mantener la consistencia
                        avance_diario.cantidad_general = None
                        avance_diario.save(update_fields=['cantidad_general'])

                        # --- LÓGICA ADITIVA ---
                        # Iteramos sobre los datos limpios del formset
                        for subform_data in formset.cleaned_data:
                            # Nos aseguramos de que la fila no esté vacía y tenga datos
                            if subform_data and subform_data.get('zona') and subform_data.get('cantidad') is not None:
                                zona = subform_data['zona']
                                cantidad = subform_data['cantidad']
                                
                                # Actualiza la zona si ya existe, o la crea si es nueva.
                                AvancePorZona.objects.update_or_create(
                                    avance_diario=avance_diario,
                                    zona=zona,
                                    defaults={'cantidad': cantidad}
                                )
                        
                        # Manejamos las filas que el usuario marcó para eliminar en el formset
                        for form_to_delete in formset.deleted_forms:
                           if form_to_delete.instance.pk:
                               form_to_delete.instance.delete()
                        
                        messages.success(request, 'Desglose por zonas guardado/actualizado con éxito.')

                    else: # tipo_registro == 'general'
                        avance_diario.avances_por_zona.all().delete()
                        messages.success(request, 'Avance general guardado con éxito.')

                    return redirect('registrar_avance')

            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
        else:
            messages.error(request, 'Por favor, corrige los errores mostrados en el formulario.')
            if formset.errors:
                messages.warning(request, f'Errores en el desglose: {formset.non_form_errors() or formset.errors}')

    # --- Lógica de Contexto (sin cambios) ---
    actividad_queryset = Actividad.objects.filter(
        proyecto=proyecto, sub_actividades__isnull=True
    ).order_by('nombre')
    
    partidas = PartidaActividad.objects.all()
    partida_seleccionada_id = request.GET.get('partida_filtro')
    
    if partida_seleccionada_id:
        actividad_queryset = actividad_queryset.filter(partida_id=partida_seleccionada_id)

    form.fields['actividad'].queryset = actividad_queryset

    contexto = {
        'form': form,
        'formset': formset,
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