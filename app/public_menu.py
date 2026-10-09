import inspect
from typing import Any, Callable
from fastapi import APIRouter, Response
from starlette.concurrency import run_in_threadpool


def crear_router_publico(obtener_menu_completo_func: Callable[..., Any]):
    router = APIRouter(prefix="/api/v1/menu", tags=["Menu Publico"])

    @router.get("/public")
    async def obtener_menu_publico():
        # Verificamos si la función requiere el parámetro 'response'
        sig = inspect.signature(obtener_menu_completo_func)
        kwargs = {"response": Response()} if "response" in sig.parameters else {}

        # La función es síncrona (Sheets/clima hacen red): se ejecuta en un hilo para no
        # congelar el event loop ni /health mientras espera.
        if inspect.iscoroutinefunction(obtener_menu_completo_func):
            res = await obtener_menu_completo_func(**kwargs)
        else:
            res = await run_in_threadpool(obtener_menu_completo_func, **kwargs)
            if hasattr(res, "__await__"):
                res = await res

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

                # --- EXTRACCIÓN MULTICLAVE BLINDADA ---
                # Busca el valor sin importar la variación de nombre de la columna del Sheet
                temp_raw = (
                    data.get("temperatura_ideal")
                    or data.get("temp_ideal")
                    or data.get("Temperatura_Ideal")
                    or data.get("temperatura")
                )

                temp_str = str(temp_raw).strip().lower() if temp_raw is not None else ""

                if temp_str not in ["", "none", "null", "undefined"]:
                    # Conservamos explícitamente lo escrito en el Sheet (ej: 'calor', 'frio')
                    valor_final = temp_str
                else:
                    # Inferencia por defecto si la celda en Sheets está en blanco
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

                # Asignamos a todas las variaciones conocidas para garantizar compatibilidad total
                data["temperatura_ideal"] = valor_final
                data["temp_ideal"] = valor_final
                data["temperatura"] = valor_final

            items_filtrados.append(data)

        return items_filtrados

    return router