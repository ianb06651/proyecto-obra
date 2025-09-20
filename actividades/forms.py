from django import forms
from django.forms import modelformset_factory
from datetime import date
from .models import (
    # Modelos existentes
    ReporteDiarioMaquinaria, ReportePersonal, Actividad,
    PartidaActividad, AvanceDiario, ReporteClima,
    # Nuevos modelos para el desglose
    MetaPorZona, AvancePorZona
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

# --- Formularios Modificados y Nuevos ---

# --- 1. Formularios para el modelo Actividad ---

class MetaPorZonaForm(forms.ModelForm):
    class Meta:
        model = MetaPorZona
        # Añadir los nuevos campos de fecha
        fields = ['zona', 'meta', 'fecha_inicio_programada', 'fecha_fin_programada']
        # Añadir widgets para que aparezca el selector de calendario
        widgets = {
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date'}),
        }

# FormSet para manejar múltiples metas por zona
MetaPorZonaFormSet = modelformset_factory(
    MetaPorZona,
    form=MetaPorZonaForm,
    extra=1,
    can_delete=True
)

class ActividadForm(forms.ModelForm):
    # NUEVO: Campo para seleccionar el tipo de registro de meta
    TIPO_REGISTRO_CHOICES = [
        ('general', 'Registrar Meta General'),
        ('por_zona', 'Desglosar Meta por Zona'),
    ]
    tipo_registro_meta = forms.ChoiceField(
        choices=TIPO_REGISTRO_CHOICES,
        widget=forms.RadioSelect,
        initial='general',
        label="Tipo de Registro de Meta"
    )

    class Meta:
        model = Actividad
        # MODIFICADO: Se cambia 'meta_cantidad_total' por 'meta_general'
        # y se añade el nuevo campo de control 'tipo_registro_meta'.
        fields = [
            'nombre', 'padre', 'proyecto', 'partida', 'tipo_registro_meta', 'meta_general',
            'unidad_medida', 'fecha_inicio_programada', 'fecha_fin_programada'
        ]
        widgets = {
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

        if not self.instance.pk:
            self.fields['fecha_inicio_programada'].initial = date.today()
            self.fields['fecha_fin_programada'].initial = date.today()

        if 'padre' in self.fields:
            queryset = Actividad.objects.all()
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            self.fields['padre'].queryset = queryset.order_by('padre__nombre', 'nombre')

    # NUEVO: Lógica de validación para el modelo híbrido
    def clean(self):
        cleaned_data = super().clean()
        tipo_registro = cleaned_data.get('tipo_registro_meta')
        meta_general = cleaned_data.get('meta_general')

        if tipo_registro == 'general' and not meta_general:
            self.add_error('meta_general', "Debe proporcionar una meta general.")
        
        if tipo_registro == 'por_zona':
            cleaned_data['meta_general'] = None
            
        return cleaned_data

# --- 2. Formularios para el modelo AvanceDiario ---

class AvancePorZonaForm(forms.ModelForm):
    """Formulario para una sola entrada de avance por zona."""
    class Meta:
        model = AvancePorZona
        fields = ['zona', 'cantidad']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['zona'].widget.attrs.update({'class': 'form-control'})
        self.fields['cantidad'].widget.attrs.update({'class': 'form-control'})

# FormSet para manejar múltiples avances por zona en un día
AvancePorZonaFormSet = modelformset_factory(
    AvancePorZona,
    form=AvancePorZonaForm,
    extra=1,
    can_delete=True
)

class AvanceDiarioForm(forms.ModelForm):
    # NUEVO: Campo para seleccionar el tipo de registro de avance
    TIPO_REGISTRO_CHOICES = [
        ('general', 'Registrar Avance General'),
        ('por_zona', 'Desglosar Avance por Zona'),
    ]
    tipo_registro = forms.ChoiceField(
        choices=TIPO_REGISTRO_CHOICES,
        widget=forms.RadioSelect,
        initial='general',
        label="Tipo de Registro de Avance"
    )

    class Meta:
        model = AvanceDiario
        # MODIFICADO: Se eliminó 'zonas' y se cambió 'cantidad_realizada_dia'
        # por 'cantidad_general'. Se añade 'tipo_registro'.
        fields = ['actividad', 'fecha_reporte', 'empresa', 'tipo_registro', 'cantidad_general']
        widgets = {
            'fecha_reporte': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'fecha_reporte' in self.fields:
            self.fields['fecha_reporte'].initial = date.today()

        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in existing_classes:
                    field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

    # NUEVO: Lógica de validación para el modelo híbrido
    def clean(self):
        cleaned_data = super().clean()
        tipo_registro = cleaned_data.get('tipo_registro')
        cantidad_general = cleaned_data.get('cantidad_general')

        if tipo_registro == 'general' and not cantidad_general:
            self.add_error('cantidad_general', "Debe proporcionar una cantidad general.")

        if tipo_registro == 'por_zona':
            cleaned_data['cantidad_general'] = None
            
        return cleaned_data