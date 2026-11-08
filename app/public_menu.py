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

        # Obtenemos la temperatura real calculada en el backend
        temp_val = internal_response.headers.get("X-Temperatura", "16")

        try:
            temperatura_base = float(temp_val)
        except (ValueError, TypeError):
            temperatura_base = 16.0

        # Mantenemos tu compensación de + 4.0 grados
        temperatura_compensada = temperatura_base + 4.0

        # Lógica estricta de umbrales: menor a 18°C es frío, mayor a 25°C es calor
        if temperatura_compensada < 18.0:
            modo_val = "frio"
        elif temperatura_compensada > 25.0:
            modo_val = "calor"
        else:
            modo_val = "indiferente"

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

                # --- EXTRACCIÓN BLINDADA DE LA IMAGEN ---
                imagen_val = (
                    data.get("imagenUrl")
                    or data.get("Imagen")
                    or data.get("imagen")
                    or data.get("imagen_url")
                    or data.get("Imagen_URL")
                )
                
                if imagen_val and str(imagen_val).strip() not in ["", "none", "null", "undefined"]:
                    data["imagenUrl"] = str(imagen_val).strip()
                else:
                    data["imagenUrl"] = None

                # --- EXTRACCIÓN BLINDADA DE LA DESCRIPCIÓN ---
                desc_val = None
                if isinstance(data, dict):
                    desc_val = (
                        data.get("descripcion")
                        or data.get("Descripcion")
                        or data.get("Descripción")
                        or data.get("descripcion_larga")
                        or data.get("detalles")
                    )
                
                if not desc_val and hasattr(item, "__dict__"):
                    item_dict = item.__dict__
                    desc_val = (
                        item_dict.get("descripcion")
                        or item_dict.get("Descripcion")
                        or item_dict.get("Descripción")
                    )

                if desc_val and str(desc_val).strip() not in ["", "none", "null", "undefined", "nan"]:
                    data["descripcion"] = str(desc_val).strip()
                else:
                    data["descripcion"] = None

                # --- EXTRACCIÓN MULTICLAVE BLINDADA PARA TEMPERATURA ---
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

        # Devolvemos el clima con los umbrales correctos y el menú con imágenes y descripciones listas
        return {
            "clima": {
                "ciudad": "Querétaro",
                "temperatura": temperatura_compensada,
                "modo": modo_val,
                "condicion": modo_val,
                "descripcion": f"Día {modo_val} en Querétaro",
            },
            "menu": items_filtrados,
        }

    return router
