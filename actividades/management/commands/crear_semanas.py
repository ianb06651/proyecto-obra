from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from actividades.models import Semana

class Command(BaseCommand):
    help = 'Crea o actualiza el catálogo de Semanas hasta una fecha específica.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando la creación/actualización del catálogo de semanas...")

        fecha_actual_inicio = date(2025, 4, 17)
        
        # --- MODIFICACIÓN CLAVE ---
        # 1. Definimos la fecha límite.
        fecha_limite = date(2027, 1, 27)

        # 2. Usamos un contador para el número de semana.
        numero_de_semana = 1
        semanas_creadas = 0

        # Limpiamos la tabla para generar la secuencia correcta hasta la nueva fecha.
        Semana.objects.all().delete()
        self.stdout.write("Tabla de semanas limpiada.")

        # 3. Cambiamos el bucle 'for' por un 'while' que comprueba la fecha.
        while fecha_actual_inicio <= fecha_limite:
            fecha_fin = fecha_actual_inicio + timedelta(days=6)

            # Creamos la semana. Usamos create directamente ya que la tabla está limpia.
            Semana.objects.create(
                numero_semana=numero_de_semana,
                fecha_inicio=fecha_actual_inicio,
                fecha_fin=fecha_fin,
            )
            semanas_creadas += 1
            
            # Preparamos los valores para la siguiente iteración
            fecha_actual_inicio += timedelta(days=7)
            numero_de_semana += 1
        
        self.stdout.write(f"Proceso finalizado. Se crearon {semanas_creadas} semanas.")
        self.stdout.write(self.style.SUCCESS('¡Catálogo de semanas creado exitosamente!'))