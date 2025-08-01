from django import forms
from .models import ReporteDiarioMaquinaria, ReportePersonal

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
        }

class ReportePersonalForm(forms.ModelForm):
    class Meta:
        model = ReportePersonal
        fields = [
            'fecha',
            'empresa',
            'cargo',
            'partida',
            'area_de_trabajo',
            'cantidad',
        ]
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
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )