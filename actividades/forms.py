from django import forms
from .models import (
    ReporteDiarioMaquinaria, ReportePersonal, Actividad, 
    PartidaActividad, AvanceDiario, ReporteClima 
)

class ReporteMaquinariaForm(forms.ModelForm):
    class Meta:
        model = ReporteDiarioMaquinaria
        fields = [
            'fecha',
            'empresa',
            'partida',
            'tipo_maquinaria',
            'zona_trabajo',
            'cantidad_total',
            'cantidad_activa',
            'cantidad_inactiva',
            'observaciones',
        ]
        widgets = {
            'fecha': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'empresa': forms.Select(attrs={'class': 'form-control'}),
            'partida': forms.Select(attrs={'class': 'form-control'}),
            'tipo_maquinaria': forms.Select(attrs={'class': 'form-control'}),
            'zona_trabajo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_activa': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_inactiva': forms.NumberInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ReportePersonalForm(forms.ModelForm):
    class Meta:
        model = ReportePersonal
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ConsultaClimaForm(forms.Form):
    fecha = forms.DateField(
        label="Selecciona una fecha",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )

class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = [
            'nombre',
            'padre',
            'proyecto',
            'partida',
            'meta_cantidad_total',
            'unidad_medida',
            'fecha_inicio_programada',
            'fecha_fin_programada'
        ]
        widgets = {
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

        if self.instance and self.instance.pk:
            self.fields['padre'].queryset = Actividad.objects.exclude(pk=self.instance.pk)

        if 'padre' in self.fields:
                self.fields['padre'].queryset = self.fields['padre'].queryset.order_by('padre__nombre', 'nombre')


# --- NUEVO FORMULARIO AÑADIDO ---
class AvanceDiarioForm(forms.ModelForm):
    """
    Formulario para registrar el avance diario, incluyendo la empresa contratista.
    """
    class Meta:
        model = AvanceDiario
        fields = ['actividad', 'fecha_reporte', 'cantidad_realizada_dia', 'empresa']
        widgets = {
            'fecha_reporte': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicamos un estilo consistente a todos los campos del formulario.
        for field_name, field in self.fields.items():
            # El widget del campo 'actividad' podría no tener 'attrs' si se reemplaza,
            # por eso comprobamos primero.
            if hasattr(field.widget, 'attrs'):
                field.widget.attrs.update({'class': 'form-control'})