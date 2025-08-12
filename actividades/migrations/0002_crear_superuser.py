# actividades/migrations/000X_crear_superuser.py

import os
from django.db import migrations
from django.contrib.auth import get_user_model

def crear_superuser(apps, schema_editor):
    """
    Crea un superusuario usando las variables de entorno.
    """
    User = get_user_model()
    
    ADMIN_USER = os.environ.get('ADMIN_USER')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')

    if ADMIN_USER and ADMIN_PASSWORD and ADMIN_EMAIL:
        if not User.objects.filter(username=ADMIN_USER).exists():
            print(f"Creando superusuario: {ADMIN_USER}")
            User.objects.create_superuser(
                username=ADMIN_USER,
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD
            )
        else:
            print(f"Superusuario '{ADMIN_USER}' ya existe.")
    else:
        print("ADVERTENCIA: Faltan variables de entorno ADMIN_USER, ADMIN_PASSWORD o ADMIN_EMAIL. No se creará el superusuario.")

def eliminar_superuser(apps, schema_editor):
    """
    Elimina al superusuario si la migración se revierte.
    """
    User = get_user_model()
    ADMIN_USER = os.environ.get('ADMIN_USER')
    
    if ADMIN_USER:
        try:
            user = User.objects.get(username=ADMIN_USER)
            user.delete()
            print(f"Superusuario '{ADMIN_USER}' eliminado.")
        except User.DoesNotExist:
            pass

class Migration(migrations.Migration):

    dependencies = [
        # Esta es la línea que confirmaste.
        # Apunta a tu primera migración para asegurar el orden correcto.
        ('actividades', '0001_initial'), 
    ]

    operations = [
        migrations.RunPython(crear_superuser, reverse_code=eliminar_superuser),
    ]