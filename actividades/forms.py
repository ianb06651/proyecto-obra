# actividades/forms.py

from django import forms
from datetime import date
from django.forms import inlineformset_factory
from .models import (
    ReporteDiarioMaquinaria, ReportePersonal, Actividad, 
    PartidaActividad, AvanceDiario, ReporteClima, AvancePorZona
)

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

class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = [
            'nombre', 'padre', 'proyecto', 'partida', 'meta_cantidad_total',
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

class AvanceDiarioForm(forms.ModelForm):
    class Meta:
        model = AvanceDiario
        fields = ['actividad', 'fecha_reporte', 'empresa', 'cantidad_realizada_dia']
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

# --- FORMSET PARA EL DESGLOSE POR ZONAS (VERSIÓN CORREGIDA) ---
AvancePorZonaFormSet = inlineformset_factory(
    AvanceDiario,
    AvancePorZona,
    fields=('zona', 'cantidad_realizada'),
    extra=1,
    can_delete=True,
    widgets={
        'zona': forms.Select(attrs={'class': 'form-control'}),
        'cantidad_realizada': forms.NumberInput(attrs={'class': 'form-control'}),
    }
)