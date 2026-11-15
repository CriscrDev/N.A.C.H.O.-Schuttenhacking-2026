"""Arranca el monitor N.A.C.H.O.

Se corre con:  python main.py
"""

import os
import sys


def main():
    # para que no se vea borroso en pantallas con escalado (Windows)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        try:
            # con esto la barra de tareas muestra nuestro logo y no el de python
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nacho.monitor.tripulacion")
        except (AttributeError, OSError):
            pass

    from vitales.interfaz import Aplicacion

    carpeta = os.path.dirname(os.path.abspath(__file__))
    Aplicacion(carpeta).mainloop()


if __name__ == "__main__":
    main()
