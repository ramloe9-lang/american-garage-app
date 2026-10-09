"""Utilidades de normalización y parseo de celdas de Google Sheets."""
import re
import unicodedata
from typing import Any


def normalizar(texto: Any) -> str:
    """Minúsculas, sin acentos y sin espacios sobrantes: 'Frío ' -> 'frio'."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().casefold()


def a_float(valor: Any, defecto: float = 0.0) -> float:
    """Convierte '$1,250.50', 45, '45.5' a float. Asume punto decimal y coma de miles."""
    if valor is None:
        return defecto
    if isinstance(valor, (int, float)):
        return float(valor)
    s = re.sub(r"[^\d.,\-]", "", str(valor)).replace(",", "")
    try:
        return float(s) if s else defecto
    except ValueError:
        return defecto


def a_fraccion(valor: Any) -> float:
    """Convierte un porcentaje a fracción (0.15 = 15%).

    - '15%'  -> 0.15
    - '15'   -> 0.15   (>= 1 se interpreta como puntos porcentuales)
    - '0.15' -> 0.15
    - ''     -> 0.0
    """
    if valor is None or str(valor).strip() == "":
        return 0.0
    s = str(valor).strip()
    n = a_float(s)
    if "%" in s or n >= 1:
        return max(n / 100.0, 0.0)
    return max(n, 0.0)


def separar_referencias(valor: Any) -> list[str]:
    """'INS-001, INS-006' -> ['INS-001', 'INS-006'] (acepta , ; |)."""
    if valor is None:
        return []
    return [x.strip() for x in re.split(r"[,;|]", str(valor)) if x.strip()]
