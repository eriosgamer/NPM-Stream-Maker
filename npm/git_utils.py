import os
import re
import shutil
import subprocess
from rich.progress import Progress

# Este módulo proporciona utilidades para trabajar con repositorios git,
# específicamente clonar un repositorio con una barra de progreso usando 'rich'.

def repo_clone(repo_url, destino, console):
    """
    Clona un repositorio git mostrando una barra de progreso.
    Elimina el destino si ya existe antes de clonar.
    Lanza una excepción si falla el clonado.
    Args:
        repo_url (str): URL del repositorio git a clonar.
        destino (str): Ruta donde se clonará el repositorio.
        console: Objeto de consola Rich (no utilizado en esta función).
    """
    # Clonar el repositorio con barra de progreso
    if os.path.exists(destino):
        # Eliminar el directorio de destino si ya existe
        shutil.rmtree(destino)
    with Progress() as progress:
        # Agregar una nueva tarea a la barra de progreso para la clonación
        task = progress.add_task(
            "[cyan]Cloning AMPTemplates repository...", total=100)
        # Usar subprocess para clonar y mostrar el progreso simulado
        process = subprocess.Popen(
            ["git", "clone", "--progress", repo_url, destino],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        percent = 0
        # Leer líneas de stderr para analizar la salida del progreso de git
        for line in process.stderr:
            if "Receiving objects" in line:
                # Extraer el porcentaje de la línea usando expresiones regulares
                match = re.search(r'(\d+)%', line)
                if match:
                    percent = int(match.group(1))
                    # Actualizar la barra de progreso con el porcentaje actual
                    progress.update(task, completed=percent)
        process.wait()
        # Asegurarse de que la barra de progreso llegue al 100% al final
        progress.update(task, completed=100)
    if process.returncode != 0:
        # Lanzar una excepción si falló el comando git clone
        raise Exception("Error cloning AMPTemplates repository.")
