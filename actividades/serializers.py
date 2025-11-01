# actividades/serializers.py

from rest_framework import serializers
from .models import ElementoConstructivo

class ElementoStatusSerializer(serializers.ModelSerializer):
    """
    Serializador para exponer el estado de un Elemento Constructivo a Navisworks.
    """
    # SerializerMethodField nos da control total sobre el valor de salida.
    status = serializers.SerializerMethodField()
    
    # Exponemos 'identificador_bim' como el campo clave para la vinculación.
    # Usamos 'source' para leer del campo del modelo.
    id_navisworks = serializers.CharField(source='identificador_bim')

    class Meta:
        model = ElementoConstructivo
        # Campos que se expondrán en la API
        fields = [
            'id_navisworks', # El ID de máquina para Navisworks
            'identificador_unico', # El ID legible (ej. ZA-B5) como dato extra
            'status' # El estado calculado
        ]

    def get_status(self, obj):
        """
        Calcula el estado basado en los campos anotados por el queryset de la vista.
        
        'obj' es la instancia de ElementoConstructivo.
        Esperamos que la vista (get_queryset) ya haya anotado
        'total_pasos' y 'pasos_completados' en el objeto.
        """
        # Accedemos a las propiedades que ya definimos en models.py
        # La vista se habrá encargado de optimizar esto con 'annotate'.
        return obj.status