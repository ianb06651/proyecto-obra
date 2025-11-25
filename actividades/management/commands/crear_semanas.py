from datetime import date, timedelta
from django.core.management.base import BaseCommand
from actividades.models import Semana

class Command(BaseCommand):
    help = 'Crea o actualiza el catálogo de Semanas hasta una fecha específica de manera segura.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando la actualización del catálogo de semanas...")

        fecha_actual_inicio = date(2025, 4, 17)
        fecha_limite = date(2027, 1, 27)
        numero_de_semana = 1
        semanas_procesadas = 0

        # ELIMINADO: Semana.objects.all().delete()  <-- ¡Peligroso!

        while fecha_actual_inicio <= fecha_limite:
            fecha_fin = fecha_actual_inicio + timedelta(days=6)

            # Usamos update_or_create para no romper relaciones existentes
            obj, created = Semana.objects.update_or_create(
                numero_semana=numero_de_semana,
                defaults={
                    'fecha_inicio': fecha_actual_inicio,
                    'fecha_fin': fecha_fin,
                }
            )
            
            semanas_procesadas += 1
            fecha_actual_inicio += timedelta(days=7)
            numero_de_semana += 1
        
        self.stdout.write(self.style.SUCCESS(f'¡Proceso completado! Se procesaron {semanas_procesadas} semanas.'))