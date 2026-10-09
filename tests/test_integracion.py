"""Integración: sheets.py (con gspread simulado) + utils + scoring + caché reales."""
from app import scoring, sheets
from app.cache import StaleCache
from app.schemas import ItemMenu


class HojaFalsa:
    def __init__(self, title, valores):
        self.title, self._v = title, valores

    def get_all_values(self):
        return self._v


class LibroFalso:
    def __init__(self, hojas, contador):
        self._h, self._c = hojas, contador

    def worksheets(self):
        self._c.append(1)
        return self._h


class ClienteFalso:
    def __init__(self, hojas, contador):
        self._h, self._c = hojas, contador

    def open_by_key(self, _id):
        return LibroFalso(self._h, self._c)


def hojas():
    # Todo llega como texto, igual que get_all_values() de gspread.
    return [
        HojaFalsa("Inventario_Bebidas", [
            ["ID_Bebida", "Nombre_Producto", "Categoria", "Unidad_Medida", "Cantidad_Actual", "Stock_Minimo",
             "Estado_Stock", "Precio_Costo", "Precio_Venta", "Temperatura_Ideal"],
            ["BEB-001", "Limonada", "Bebidas", "pz", "20", "5", "OK", "$10.00", "$45.00", " Frío "],
            ["BEB-002", "Cerveza", "Bebidas", "pz", "0", "5", "Agotado", "$15.00", "$60.00", "frio"],
            ["", "", "", "", "", "", "", "", "", ""],
        ]),
        HojaFalsa("Menu_Productos", [
            ["ID_Producto", "Nombre_Producto", "Categoria", "Precio_Venta", "Costo_Estimado",
             "Margen_Ganancia", "Temperatura_Ideal", "Ingredientes_Clave"],
            ["PRO-001", "Burger Clásica", "Burgers", "$1,200.00".replace(",", ""), "$500.00", "58%", "Caliente", "INS-001,INS-006"],
            ["PRO-002", "Wings BBQ", "Wings", "$150.00", "$60.00", "60%", "caliente", "INS-002"],
            ["PRO-003", "Burger Doble", "Burgers", "$200.00", "$90.00", "55%", "indiferente", "INS-003"],
        ]),
        HojaFalsa("Inventario_Insumos_Mermas", [
            ["ID_Insumo", "Nombre_Insumo", "Categoria", "Unidad", "Stock_Actual", "Fecha_Caducidad",
             "Costo_Anterior", "Costo_Actual", "Descuento_Sugerido", "Estado_Insumo"],
            ["INS-001", "Carne", "Carnes", "kg", "5", "", "100", "100", "15%", "Urgente (Vence Hoy)"],
            ["INS-006", "Pan", "Panes", "pz", "5", "", "5", "5", "0%", "OK"],
            ["INS-002", "Alitas", "Carnes", "kg", "0", "", "80", "80", "", "Agotado"],
            ["INS-003", "Queso", "Lácteos", "kg", "3", "", "100", "200", "", "Costo Elevado"],
        ]),
        HojaFalsa("Registro_Ventas", [["ID_Venta", "Fecha_Hora", "ID_Producto", "Cantidad", "Total_Venta"]]),
        HojaFalsa("Dashboard_Resumen", [
            ["Métrica / Indicador", "Valor Calculado", "Nota / Estado"],
            ["Ventas del día", "$5,000", "Normal"],
            ["", "", ""],
        ]),
    ]


def preparar(monkeypatch):
    contador = []
    monkeypatch.setattr(sheets, "_cache", StaleCache(ttl=300))
    monkeypatch.setattr(sheets, "_obtener_cliente", lambda reiniciar=False: ClienteFalso(hojas(), contador))
    return contador


def test_menu_completo_desde_hoja_simulada(monkeypatch):
    preparar(monkeypatch)
    menu = scoring.construir_menu(sheets.obtener_tablas(), 15.0)
    por_nombre = {i.nombre: i for i in menu}

    assert isinstance(menu[0], ItemMenu)
    assert "Wings BBQ" not in por_nombre          # Regla A: INS-002 agotado
    assert "Cerveza" not in por_nombre            # Regla A: bebida agotada
    burger = por_nombre["Burger Clásica"]
    assert burger.prioridad_score == 100          # 50 + 40 (urgente) + 20 (frío + caliente)
    assert burger.precio_final == 1020.0 and burger.descuento_aplicado == 15.0
    assert burger.insignias[0] == scoring.INSIGNIA_CHEF
    doble = por_nombre["Burger Doble"]            # Regla C: costo 90 -> 180, margen 10%
    assert doble.prioridad_score == 20
    assert por_nombre["Limonada"].prioridad_score == 50   # frío sin calor: sin bono
    assert [i.nombre for i in menu][0] == "Burger Clásica" and menu[-1].nombre == "Burger Doble"


def test_calor_premia_bebida_fria_con_acento_y_espacios(monkeypatch):
    preparar(monkeypatch)
    menu = scoring.construir_menu(sheets.obtener_tablas(), 30.0)
    limonada = next(i for i in menu if i.nombre == "Limonada")
    assert limonada.prioridad_score == 70 and limonada.insignia_sugerida == scoring.INSIGNIA_CALOR


def test_segunda_lectura_usa_cache(monkeypatch):
    contador = preparar(monkeypatch)
    sheets.obtener_tablas()
    sheets.obtener_tablas()
    assert len(contador) == 1


def test_kpis_del_dashboard(monkeypatch):
    preparar(monkeypatch)
    assert sheets.obtener_dashboard() == [
        {"metrica": "Ventas del día", "valor": "$5,000", "nota": "Normal"}
    ]


def test_pestana_con_solo_encabezados_conserva_columnas():
    df = sheets._a_dataframe([["ID_Venta", "Fecha_Hora"]])
    assert list(df.columns) == ["ID_Venta", "Fecha_Hora"] and df.empty


def test_filas_vacias_se_descartan():
    df = sheets._a_dataframe([["A", "B"], ["1", "2"], ["", ""]])
    assert len(df) == 1
