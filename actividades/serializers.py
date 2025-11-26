# actividades/serializers.py

from rest_framework import serializers
from .models import ElementoConstructivo, ElementoBIM_GUID

class ElementoBIM_GUID_Serializer(serializers.ModelSerializer):
    
    id_navisworks = serializers.CharField(source='identificador_bim')
    identificador_unico = serializers.CharField(source='elemento_constructivo.identificador_unico')
    status = serializers.CharField(source='elemento_constructivo.status')

    # Campo existente (Fin)
    fecha_fin = serializers.DateField(
        source='ultima_fecha', 
        read_only=True, 
        format='%Y-%m-%d', 
        allow_null=True
    )

    # [3] NUEVO CAMPO: Fecha de Inicio (Timeliner ActualStart)
    fecha_inicio = serializers.DateField(
        source='primera_fecha',   # Viene del annotate Min en la vista
        read_only=True, 
        format='%Y-%m-%d', 
        allow_null=True
    )

    class Meta:
        model = ElementoBIM_GUID 
        fields = [
            'id_navisworks',       
            'identificador_unico', 
            'status',              
            'fecha_inicio', # <--- [4] NO OLVIDES AGREGARLO AQUI
            'fecha_fin'            
        ]