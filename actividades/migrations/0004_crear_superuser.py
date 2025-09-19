from django.db import migrations
import os

def crear_superuser(apps, schema_editor):
    """
    Crea un superusuario usando las variables de entorno para las credenciales.
    """
    User = apps.get_model('auth', 'User')
    username = os.environ.get('ADMIN_USER')
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASSWORD')

    if not all([username, email, password]):
        # Si alguna variable no está, la migración fallará con un error claro
        raise ValueError("Las variables de entorno ADMIN_USER, ADMIN_EMAIL, y ADMIN_PASSWORD deben estar configuradas.")

    if not User.objects.filter(username=username).exists():
        print(f"Creando superusuario: {username}")
        User.objects.create_superuser(username=username, email=email, password=password)
    else:
        print(f"El superusuario {username} ya existe, no se realiza ninguna acción.")

class Migration(migrations.Migration):

    dependencies = [
        ('actividades', '0003_modelos_de_registro_hibridos'), 
    ]

    operations = [
        migrations.RunPython(crear_superuser),
    ]