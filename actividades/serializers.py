# actividades/serializers.py

from rest_framework import serializers
# --- 1. MODIFICADO: Importar los dos modelos ---
from .models import ElementoConstructivo, ElementoBIM_GUID

# --- 2. NUEVO SERIALIZADOR ---
class ElementoBIM_GUID_Serializer(serializers.ModelSerializer):
    """
    Serializador para exponer el estado de un Elemento Constructivo
    a través de su GUID de BIM.
    
    Cada GUID en la BD generará un objeto JSON en la API,
    pero el 'status' y 'identificador_unico' se tomarán del
    ElementoConstructivo padre al que está vinculado.
    """
    
    # "id_navisworks" será el campo 'identificador_bim' de este modelo
    id_navisworks = serializers.CharField(source='identificador_bim')
    
    # "identificador_unico" se obtiene siguiendo la ForeignKey
    # al 'elemento_constructivo' padre y leyendo su campo 'identificador_unico'
    identificador_unico = serializers.CharField(source='elemento_constructivo.identificador_unico')
    
    # "status" también se obtiene del 'elemento_constructivo' padre,
    # usando su propiedad @property 'status'
    status = serializers.CharField(source='elemento_constructivo.status')

    class Meta:
        model = ElementoBIM_GUID # <--- El modelo base es el GUID
        fields = [
            'id_navisworks',       # El ID de máquina (GUID) para Navisworks
            'identificador_unico', # El ID legible (ej. ZA-B5) como dato extra
            'status'               # El estado calculado (Pendiente, En Proceso, Completado)
        ]
# --- FIN NUEVO SERIALIZADOR ---


# --- 3. ELIMINADO/OBSOLETO ---
# El Serializer 'ElementoStatusSerializer' anterior ya no es necesario
# ya que 'ElementoStatusAPIView' ahora usará 'ElementoBIM_GUID_Serializer'.

# class ElementoStatusSerializer(serializers.ModelSerializer):
#    ... (este bloque de código se elimina) ...