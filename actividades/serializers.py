# actividades/serializers.py

from rest_framework import serializers
from .models import ElementoConstructivo, ElementoBIM_GUID

class ElementoBIM_GUID_Serializer(serializers.ModelSerializer):
    """
    Serializador para exponer el estado de un Elemento Constructivo
    a través de su GUID de BIM.
    """
    
    # "id_navisworks" será el campo 'identificador_bim' de este modelo
    id_navisworks = serializers.CharField(source='identificador_bim')
    
    # "identificador_unico" se obtiene siguiendo la ForeignKey al padre
    identificador_unico = serializers.CharField(source='elemento_constructivo.identificador_unico')
    
    # "status" se obtiene de la propiedad calculada del padre
    status = serializers.CharField(source='elemento_constructivo.status')

    # --- NUEVO: Campo para la fecha de terminación (Timeliner) ---
    # Lee el valor 'ultima_fecha' que anotamos en la vista.
    # allow_null=True permite que elementos sin avance no rompan la API.
    fecha_fin = serializers.DateField(
        source='ultima_fecha', 
        read_only=True, 
        format='%Y-%m-%d', 
        allow_null=True
    )

    class Meta:
        model = ElementoBIM_GUID 
        fields = [
            'id_navisworks',       # GUID para Navisworks
            'identificador_unico', # ID Humano (ej. ZA-B2)
            'status',              # Estado (Verde/Rojo)
            'fecha_fin'            # Fecha real fin (para Timeliner)
        ]