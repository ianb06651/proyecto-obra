# En el nuevo archivo de migración (ej. actividades/migrations/0004_crear_superuser.py)
from django.db import migrations
import os

def crear_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    
    ADMIN_USER = os.environ.get('ADMIN_USER')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    # Solo intentar crear el superusuario si las variables existen
    if ADMIN_USER and ADMIN_EMAIL and ADMIN_PASSWORD:
        # Revisa si el usuario ya existe para no causar un error
        if not User.objects.filter(username=ADMIN_USER).exists():
            User.objects.create_superuser(
                username=ADMIN_USER,
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD
            )
            print(f"Superusuario '{ADMIN_USER}' creado exitosamente.")
        else:
            print(f"Superusuario '{ADMIN_USER}' ya existe. Omitiendo creación.")

class Migration(migrations.Migration):

    dependencies = [
        # Coloca aquí el nombre de tu última migración de la app 'actividades'
        # Por ejemplo: ('actividades', '0003_auto_20250721_1234'),
        ('actividades', '0003_tipomaquinaria_reportediariomaquinaria'), 
    ]

    operations = [
        migrations.RunPython(crear_superuser),
    ]