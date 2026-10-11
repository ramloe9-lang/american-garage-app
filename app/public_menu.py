import inspect
import json
import urllib.request
from typing import Any, Callable
from fastapi import APIRouter, Response
from starlette.concurrency import run_in_threadpool


def obtener_clima_en_tiempo_real_backend():
    """Consulta directamente el clima actual de Querétaro en tiempo real."""
    try:
        url = "https://wttr.in/Queretaro?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            current = data.get("current_condition", [{}])[0]
            temp = float(current.get("temp_C", 16.0))
            desc_arr = current.get("weatherDesc", [{}])
            desc = desc_arr[0].get("value", "Fresco") if desc_arr else "Fresco"
            return temp, desc
    except Exception:
        return 16.0, "Fresco"


def crear_router_publico(obtener_menu_completo_func: Callable[..., Any]):
    router = APIRouter(prefix="/api/v1/menu", tags=["Menu Publico"])

    @router.get("/public")
    async def obtener_menu_publico(response: Response):
        # 1. Obtenemos el menú ejecutando la función original
        internal_response = Response()
        sig = inspect.signature(obtener_menu_completo_func)
        kwargs = {"response": internal_response} if "response" in sig.parameters else {}

        if inspect.iscoroutinefunction(obtener_menu_completo_func):
            res = await obtener_menu_completo_func(**kwargs)
        else:
            res = await run_in_threadpool(obtener_menu_completo_func, **kwargs)
            if hasattr(res, "__await__"):
                res = await res

        # 2. Consultamos la temperatura real de la API en vivo
        temp_base, desc_clima = await run_in_threadpool(obtener_clima_en_tiempo_real_backend)

        # Aplicamos la única resta oficial de 2 grados
        temperatura_final = temp_base - 2.0

        # Determinamos el modo automáticamente según la temperatura compensada
        if temperatura_final < 18:
            modo_val = "frio"
        elif temperatura_final > 25:
            modo_val = "calor"
        else:
            modo_val = "templado"

        # 3. Limpiamos los campos privados de los productos del menú
        campos_privados = {
            "precio_costo",
            "costo",
            "margen",
            "margen_ganancia",
            "alerta_inventario",
            "alerta_margen",
            "stock_alerta",
        }

        items_filtrados = []
        for item in res:
            if hasattr(item, "model_dump"):
                data = item.model_dump()
            elif isinstance(item, dict):
                data = dict(item)
            else:
                data = item.__dict__ if hasattr(item, "__dict__") else item

            if isinstance(data, dict):
                for campo in campos_privados:
                    data.pop(campo, None)

                temp_raw = (
                    data.get("temperatura_ideal")
                    or data.get("temp_ideal")
                    or data.get("Temperatura_Ideal")
                    or data.get("temperatura")
                )

                temp_str = str(temp_raw).strip().lower() if temp_raw is not None else ""

                if temp_str not in ["", "none", "null", "undefined"]:
                    valor_final = temp_str
                else:
                    cat = str(data.get("categoria", "")).lower()
                    nom = str(data.get("nombre", "")).lower()

                    if "café" in cat or "cafe" in cat or "caliente" in nom:
                        valor_final = "frio"
                    elif any(
                        k in cat or k in nom
                        for k in ["cerveza", "malteada", "refresco", "té helado", "te helado", "helado"]
                    ):
                        valor_final = "calor"
                    else:
                        valor_final = "todos"

                data["temperatura_ideal"] = valor_final
                data["temp_ideal"] = valor_final
                data["temperatura"] = valor_final

            items_filtrados.append(data)

        response.headers["Cache-Control"] = "public, max-age=60"

        # 4. Retornamos el JSON con el clima real consultado y el menú completo
        return {
            "clima": {
                "ciudad": "Querétaro",
                "temperatura": temperatura_final,
                "modo": modo_val,
                "condicion": modo_val,
                "descripcion": f"Día {modo_val} en Querétaro",
            },
            "menu": items_filtrados,
        }

    return router
