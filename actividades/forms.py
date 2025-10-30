# actividades/forms.py

from django import forms
from django.forms import inlineformset_factory
from datetime import date
from .models import (
    ReporteDiarioMaquinaria, ReportePersonal, Actividad,
    PartidaActividad, AvanceDiario, ReporteClima,
    MetaPorZona, AvancePorZona, TipoElemento, ProcesoConstructivo, PasoProcesoTipoElemento,
    ElementoConstructivo, AvanceProcesoElemento,
    AreaDeTrabajo
)

# --- Formularios sin cambios ---
class ReporteMaquinariaForm(forms.ModelForm):
    class Meta:
        model = ReporteDiarioMaquinaria
        fields = [
            'fecha', 'empresa', 'partida', 'tipo_maquinaria', 'zona_trabajo',
            'cantidad_total', 'cantidad_activa', 'cantidad_inactiva', 'observaciones',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'empresa': forms.Select(attrs={'class': 'form-control'}),
            'partida': forms.Select(attrs={'class': 'form-control'}),
            'tipo_maquinaria': forms.Select(attrs={'class': 'form-control'}),
            'zona_trabajo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_activa': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_inactiva': forms.NumberInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'fecha' in self.fields:
            self.fields['fecha'].initial = date.today()

class ReportePersonalForm(forms.ModelForm):
    class Meta:
        model = ReportePersonal
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'fecha' in self.fields:
            self.fields['fecha'].initial = date.today()
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ConsultaClimaForm(forms.Form):
    fecha = forms.DateField(
        label="Selecciona una fecha",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True,
        initial=date.today
    )

# --- Formularios para el modelo Actividad ---

class MetaPorZonaForm(forms.ModelForm):
    class Meta:
        model = MetaPorZona
        fields = ['zona', 'meta', 'fecha_inicio_programada', 'fecha_fin_programada']
        widgets = {
            'zona': forms.Select(attrs={'class': 'form-control'}),
            'meta': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

MetaPorZonaFormSet = inlineformset_factory(
    Actividad,
    MetaPorZona,
    form=MetaPorZonaForm,
    extra=1,
    can_delete=True,
    fk_name='actividad'
)

class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = [
            'nombre', 'padre', 'proyecto', 'partida',
            'unidad_medida', 'fecha_inicio_programada', 'fecha_fin_programada'
        ]
        widgets = {
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in existing_classes:
                    field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

        if not self.instance.pk:
            if 'fecha_inicio_programada' in self.fields:
                self.fields['fecha_inicio_programada'].initial = date.today()
            if 'fecha_fin_programada' in self.fields:
                 self.fields['fecha_fin_programada'].initial = date.today()

        if 'padre' in self.fields:
            queryset = Actividad.objects.all()
            if self.instance and self.instance.pk:
                descendientes_pks = list(self.instance.sub_actividades.values_list('pk', flat=True))
                pks_a_excluir = [self.instance.pk] + descendientes_pks
                queryset = queryset.exclude(pk__in=pks_a_excluir)

            self.fields['padre'].queryset = queryset.order_by('padre__nombre', 'nombre')
            self.fields['padre'].empty_label = "--- Ninguna (Categoría Raíz) ---"

# --- Formularios para el modelo AvanceDiario ---

class AvancePorZonaForm(forms.ModelForm):
    class Meta:
        model = AvancePorZona
        fields = ['zona', 'cantidad']
        widgets = {
            'zona': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
        }

AvancePorZonaFormSet = inlineformset_factory(
    AvanceDiario,
    AvancePorZona,
    form=AvancePorZonaForm,
    extra=1,
    can_delete=True,
    fk_name='avance_diario'
)

# --- FORMULARIO 'AvanceDiarioForm' CORREGIDO ---
class AvanceDiarioForm(forms.ModelForm):
    class Meta:
        model = AvanceDiario
        fields = ['actividad', 'fecha_reporte', 'empresa']
        widgets = {
            'fecha_reporte': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # --- LÓGICA DE CORRECCIÓN ---
        # 1. Sacamos nuestros argumentos personalizados ANTES de llamar a super()
        actividad_queryset = kwargs.pop('actividad_queryset', None)
        self.validate_uniqueness = kwargs.pop('validate_uniqueness', True) # Default a True
        
        super().__init__(*args, **kwargs) # Llamamos al __init__ original

        # --- Lógica original (está bien) ---
        if not self.instance.pk and 'fecha_reporte' in self.fields:
            self.fields['fecha_reporte'].initial = date.today()

        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in existing_classes:
                     field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

        if actividad_queryset is not None:
            self.fields['actividad'].queryset = actividad_queryset
        elif 'actividad' in self.fields:
             self.fields['actividad'].queryset = Actividad.objects.filter(sub_actividades__isnull=True).order_by('nombre')
             
    # --- MÉTODO DE CORRECCIÓN ---
    def validate_unique(self):
        # Sobreescribimos la validación de unicidad
        if self.validate_uniqueness:
            # Si la bandera es True (por defecto, o en editar_avance), validamos
            super().validate_unique()
        # Si la bandera es False (desde registrar_avance), nos saltamos
        # la validación, permitiendo que la vista maneje la unicidad.
        pass
             
             
# --- FORMULARIOS PARA REGISTRO DE AVANCE BIM ---
# (Sin cambios)
class SeleccionarElementoForm(forms.Form):
    elemento = forms.ModelChoiceField(
        queryset=ElementoConstructivo.objects.all(),
        label=("Seleccionar Elemento Constructivo"),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'elemento-select-bim'}),
        help_text=("Escribe parte del identificador para buscar.")
    )

class AvanceProcesoElementoForm(forms.ModelForm):
    fecha_finalizacion = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )

    class Meta:
        model = AvanceProcesoElemento
        fields = ['paso_proceso', 'fecha_finalizacion']
        widgets = {'paso_proceso': forms.HiddenInput()}