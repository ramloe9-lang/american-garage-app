import inspect
from typing import Any, Callable
from fastapi import APIRouter, Response
from starlette.concurrency import run_in_threadpool


def crear_router_publico(obtener_menu_completo_func: Callable[..., Any]):
    router = APIRouter(prefix="/api/v1/menu", tags=["Menu Publico"])

    @router.get("/public")
    async def obtener_menu_publico(response: Response):
        # Capturamos la respuesta del menú completo y las cabeceras del clima real
        internal_response = Response()
        sig = inspect.signature(obtener_menu_completo_func)
        kwargs = {"response": internal_response} if "response" in sig.parameters else {}

        if inspect.iscoroutinefunction(obtener_menu_completo_func):
            res = await obtener_menu_completo_func(**kwargs)
        else:
            res = await run_in_threadpool(obtener_menu_completo_func, **kwargs)
            if hasattr(res, "__await__"):
                res = await res

        # Obtenemos la temperatura real de la API y le restamos 2 de una vez por todas
        temp_val = internal_response.headers.get("X-Temperatura", "16")
        modo_val = internal_response.headers.get("X-Clima-Modo", "frio")

        try:
            temperatura_base = float(temp_val)
        except (ValueError, TypeError):
            temperatura_base = 16.0

        # Única resta oficial de 2 grados
        temperatura_final = temperatura_base - 2.0

        # Campos privados a excluir de los productos
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

                temp_str = str(temp_raw).strip().lower() if temp_raw is not None else {}

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
