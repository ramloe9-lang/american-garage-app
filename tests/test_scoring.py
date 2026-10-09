import pandas as pd

from app import scoring
from app.scoring import (
    INSIGNIA_CALOR, INSIGNIA_CHEF, INSIGNIA_FRIO, Insumo, Producto,
    construir_menu, recalcular_costo,
)


def insumo(id_, estado="OK", ant=10, act=10, desc=0, nombre=None):
    return {"ID_Insumo": id_, "Nombre_Insumo": nombre or f"Insumo {id_}", "Categoria": "x",
            "Unidad": "kg", "Stock_Actual": 5, "Fecha_Caducidad": "", "Costo_Anterior": ant,
            "Costo_Actual": act, "Descuento_Sugerido": desc, "Estado_Insumo": estado}


def plato(id_, nombre="Plato", precio=100, costo=40, ingr="", temp="indiferente"):
    return {"ID_Producto": id_, "Nombre_Producto": nombre, "Categoria": "Burgers",
            "Precio_Venta": precio, "Costo_Estimado": costo, "Margen_Ganancia": 0,
            "Temperatura_Ideal": temp, "Ingredientes_Clave": ingr}


def bebida(id_, nombre="Bebida", estado="OK", temp="frio", precio=50):
    return {"ID_Bebida": id_, "Nombre_Producto": nombre, "Categoria": "Bebidas",
            "Unidad_Medida": "pz", "Cantidad_Actual": 10, "Stock_Minimo": 2,
            "Estado_Stock": estado, "Precio_Costo": 10, "Precio_Venta": precio,
            "Temperatura_Ideal": temp}


def tablas(menu=(), bebidas=(), insumos=()):
    return {
        "Menu_Productos": pd.DataFrame(list(menu), columns=list(plato("x"))),
        "Inventario_Bebidas": pd.DataFrame(list(bebidas), columns=list(bebida("x"))),
        "Inventario_Insumos_Mermas": pd.DataFrame(list(insumos), columns=list(insumo("x"))),
    }


def unico(menu_items):
    assert len(menu_items) == 1
    return menu_items[0]


# --- Regla A ---------------------------------------------------------------
def test_regla_a_oculta_platillo_con_insumo_agotado():
    t = tablas([plato("P1", ingr="INS-001")], insumos=[insumo("INS-001", "Agotado")])
    assert construir_menu(t, None) == []


def test_regla_a_oculta_bebida_agotada():
    assert construir_menu(tablas(bebidas=[bebida("B1", estado="Agotado")]), None) == []


# --- Regla B ---------------------------------------------------------------
def test_regla_b_urgente_suma_40_insignia_y_descuento():
    t = tablas([plato("P1", precio=100, ingr="INS-001")],
               insumos=[insumo("INS-001", "Urgente (Vence Hoy)", desc="15%")])
    it = unico(construir_menu(t, None))
    assert it.prioridad_score == 90
    assert it.insignia_sugerida == INSIGNIA_CHEF
    assert it.descuento_aplicado == 15 and it.precio_final == 85


def test_regla_b_sin_descuento_mantiene_precio():
    t = tablas([plato("P1", ingr="INS-001")], insumos=[insumo("INS-001", "Urgente (Vence Hoy)", desc=0)])
    it = unico(construir_menu(t, None))
    assert it.precio_final == it.precio_original


def test_regla_b_descuento_tiene_tope_70():
    t = tablas([plato("P1", precio=100, ingr="INS-001")],
               insumos=[insumo("INS-001", "Urgente (Vence Hoy)", desc="95%")])
    assert unico(construir_menu(t, None)).descuento_aplicado == 70


# --- Regla C ---------------------------------------------------------------
def test_regla_c_margen_bajo_resta_30():
    t = tablas([plato("P1", precio=100, costo=40, ingr="INS-001")],
               insumos=[insumo("INS-001", "Costo Elevado", ant=10, act=20)])
    assert unico(construir_menu(t, None)).prioridad_score == 20  # costo 80 -> margen 20%


def test_regla_c_margen_exacto_45_no_se_penaliza():
    # 50 * 1.1 = 55.00000000000001 en flotante: sin redondeo se penalizaba por error
    t = tablas([plato("P1", precio=100, costo=50, ingr="INS-001")],
               insumos=[insumo("INS-001", "Costo Elevado", ant=10, act=11)])
    assert unico(construir_menu(t, None)).prioridad_score == 50


def test_regla_c_ingrediente_inexistente_no_infla_el_costo():
    prod = Producto("P", "P", "c", 100, 40, "", ["INS-001", "INS-999"])
    ins = Insumo("INS-001", "A", "costo elevado", 10, 20, 0)
    assert recalcular_costo(prod, [ins], total_ingredientes=2) == 60.0


# --- Regla D ---------------------------------------------------------------
def test_regla_d_frio_premia_caliente():
    it = unico(construir_menu(tablas([plato("P1", temp="Caliente")]), 15.0))
    assert it.prioridad_score == 70 and it.insignia_sugerida == INSIGNIA_FRIO


def test_regla_d_calor_premia_frio_con_acento():
    it = unico(construir_menu(tablas(bebidas=[bebida("B1", temp="Frío")]), 30.0))
    assert it.prioridad_score == 70 and it.insignia_sugerida == INSIGNIA_CALOR


def test_regla_d_templado_e_indiferente_no_cambian():
    assert unico(construir_menu(tablas([plato("P1", temp="caliente")]), 21.0)).prioridad_score == 50
    assert unico(construir_menu(tablas([plato("P1", temp="indiferente")]), 10.0)).prioridad_score == 50


def test_regla_d_sin_temperatura_se_omite():
    assert unico(construir_menu(tablas([plato("P1", temp="caliente")]), None)).prioridad_score == 50


# --- Robustez --------------------------------------------------------------
def test_omite_filas_invalidas_y_duplicados():
    t = tablas([plato("", "Sin id"), plato("P1", ""), plato("P2", precio=0),
                plato("P3", "Original"), plato("P3", "Duplicado")])
    assert [i.nombre for i in construir_menu(t, None)] == ["Original"]


def test_un_producto_roto_no_tumba_el_menu(monkeypatch):
    original = scoring.evaluar_producto

    def evaluar(p, indice, temp):
        if p.id == "P1":
            raise RuntimeError("fila corrupta")
        return original(p, indice, temp)

    monkeypatch.setattr(scoring, "evaluar_producto", evaluar)
    t = tablas([plato("P1", "Roto"), plato("P2", "Sano")])
    assert [i.nombre for i in construir_menu(t, None)] == ["Sano"]


def test_orden_de_mayor_a_menor_prioridad():
    t = tablas([plato("P1", "Normal"), plato("P2", "Chef", ingr="INS-001")],
               insumos=[insumo("INS-001", "Urgente (Vence Hoy)")])
    assert [i.nombre for i in construir_menu(t, None)] == ["Chef", "Normal"]
