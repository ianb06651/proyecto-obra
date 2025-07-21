from django import forms
from .models import ReporteDiarioMaquinaria

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})