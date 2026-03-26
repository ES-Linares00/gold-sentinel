"""
app.py
------
Interfaz web del ecosistema GOLD-SENTINEL construida con Streamlit.

Funcionalidades:
- Sidebar con botón para disparar el orquestador (main.py) en tiempo real.
- Panel de métricas: precio actual, cambio %, noticias de hoy.
- Gráfica interactiva de la evolución del precio del oro.
- Feed de las últimas 5 noticias con enlaces clickeables.

Uso:
    streamlit run app.py
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

# ─── Rutas (absolutas desde la ubicación de app.py para compatibilidad Cloud) ──
ROOT_DIR  = Path(__file__).parent
CSV_PATH  = ROOT_DIR / "data" / "precios_oro.csv"
JSON_PATH = ROOT_DIR / "data" / "noticias_oro.json"
MAIN_PATH = ROOT_DIR / "main.py"

# ─── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Gold-Sentinel",
    page_icon="gold_bar",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS personalizado ────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Fondo general */
    .stApp { background-color: #0f0f1a; }

    /* Tarjetas de noticias */
    .news-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-left: 3px solid #FFB347;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .news-card a {
        color: #FFD700;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.92rem;
        line-height: 1.4;
    }
    .news-card a:hover { text-decoration: underline; }
    .news-meta {
        color: #888;
        font-size: 0.75rem;
        margin-top: 5px;
    }

    /* Separador dorado */
    .gold-divider {
        border: none;
        border-top: 1px solid #FFB34744;
        margin: 16px 0;
    }

    /* Métrica grande */
    [data-testid="stMetricValue"] { font-size: 2rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Funciones de carga de datos ─────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_prices() -> pd.DataFrame:
    """
    Carga y prepara el DataFrame de precios desde el CSV.

    Returns:
        pd.DataFrame: Columnas [timestamp, precio, divisa, fuente] con
                      timestamp como DatetimeTZDtype UTC y precio float.
                      DataFrame vacío si el archivo no existe.
    """
    if not CSV_PATH.exists():
        return pd.DataFrame(columns=["timestamp", "precio", "divisa", "fuente"])
    df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


@st.cache_data(ttl=30)
def load_news() -> list[dict]:
    """
    Carga la lista de noticias desde el JSON.

    Returns:
        list[dict]: Lista de dicts con claves titulo, fecha_publicacion,
                    link, fuente. Lista vacía si el archivo no existe.
    """
    if not JSON_PATH.exists():
        return []
    with open(JSON_PATH, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


# ─── Funciones de métricas ────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
    """
    Calcula el precio actual, cambio absoluto y cambio porcentual.

    Args:
        df (pd.DataFrame): DataFrame de precios ordenado por timestamp.

    Returns:
        tuple: (precio_actual, delta_abs, delta_pct)
               Todos None si hay menos de 1 registro.
               delta_* None si hay menos de 2 registros.
    """
    if df.empty:
        return None, None, None
    precio_actual = df["precio"].iloc[-1]
    if len(df) < 2:
        return precio_actual, None, None
    precio_anterior = df["precio"].iloc[-2]
    delta_abs = precio_actual - precio_anterior
    delta_pct = (delta_abs / precio_anterior) * 100
    return precio_actual, delta_abs, delta_pct


def count_today_news(noticias: list[dict]) -> int:
    """
    Cuenta cuántas noticias fueron extraídas hoy (por 'extraido_en').

    Args:
        noticias (list[dict]): Lista completa de noticias.

    Returns:
        int: Cantidad de noticias recolectadas en la fecha actual UTC.
    """
    hoy = datetime.now(timezone.utc).date()
    count = 0
    for n in noticias:
        try:
            dt = datetime.fromisoformat(n.get("extraido_en", "").replace("Z", "+00:00"))
            if dt.date() == hoy:
                count += 1
        except (ValueError, AttributeError):
            pass
    return count


# ─── Función del orquestador ──────────────────────────────────────────────────

def run_sentinel() -> tuple[bool, str]:
    """
    Ejecuta main.py como subproceso usando el mismo intérprete de Python del venv.

    Returns:
        tuple[bool, str]: (éxito, mensaje de salida o error).
    """
    result = subprocess.run(
        [sys.executable, str(MAIN_PATH)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        cwd=str(ROOT_DIR),
    )
    if result.returncode == 0:
        output = (result.stdout + result.stderr).strip()
        return True, output
    else:
        return False, result.stderr.strip() or result.stdout.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Título principal ─────────────────────────────────────────────────────────
st.markdown(
    """
    <h1 style='
        text-align: center;
        background: linear-gradient(90deg, #FFB347, #FFD700, #FFA500);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.6rem;
        margin-bottom: 0;
    '>
        &#9782; Gold-Sentinel
    </h1>
    <p style='text-align:center; color:#888; margin-top:4px; font-size:1rem;'>
        Inteligencia Tecno-Fundamental del Mercado del Oro
    </p>
    <hr class='gold-divider'>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Panel de Control")
    st.caption("Agentes activos: PriceAgent · NewsAgent")
    st.markdown("<hr class='gold-divider'>", unsafe_allow_html=True)

    ejecutar = st.button(
        "Ejecutar Sentinel (Actualizar Datos)",
        type="primary",
        use_container_width=True,
        icon=":material/bolt:",
    )

    if ejecutar:
        with st.spinner("Ejecutando agentes..."):
            exito, output = run_sentinel()

        if exito:
            st.success("Pipeline completada con exito.")
            # Limpiar cache para reflejar datos nuevos
            st.cache_data.clear()
            with st.expander("Ver log de ejecucion"):
                st.code(output, language="text")
        else:
            st.error("Error durante la ejecucion.")
            st.code(output, language="text")

    st.markdown("<hr class='gold-divider'>", unsafe_allow_html=True)
    st.markdown("**Fuentes de datos**")
    st.markdown("- Yahoo Finance `GC=F`")
    st.markdown("- Google News RSS")
    st.caption("Datos guardados localmente en `data/`")

# ─── Carga de datos ───────────────────────────────────────────────────────────
df_prices = load_prices()
noticias  = load_news()

# ─── Métricas ─────────────────────────────────────────────────────────────────
precio_actual, delta_abs, delta_pct = compute_metrics(df_prices)
noticias_hoy = count_today_news(noticias)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Precio Actual del Oro (USD)",
        value=f"${precio_actual:,.2f}" if precio_actual else "Sin datos",
        delta=None,
        help="Ultimo precio spot de GC=F extraido de Yahoo Finance",
    )

with col2:
    if delta_pct is not None:
        st.metric(
            label="Cambio vs. Toma Anterior",
            value=f"{delta_pct:+.3f}%",
            delta=f"${delta_abs:+.2f}",
            delta_color="normal",
            help="Variacion respecto al penultimo registro del CSV",
        )
    else:
        st.metric(
            label="Cambio vs. Toma Anterior",
            value="N/A",
            help="Se necesitan al menos 2 registros para calcular el cambio",
        )

with col3:
    st.metric(
        label="Noticias Recolectadas Hoy",
        value=noticias_hoy,
        delta=f"{len(noticias)} total acumuladas",
        delta_color="off",
        help="Noticias cuya marca 'extraido_en' corresponde a la fecha actual UTC",
    )

st.markdown("<hr class='gold-divider'>", unsafe_allow_html=True)

# ─── Gráfica interactiva ──────────────────────────────────────────────────────
st.subheader("Evolucion del Precio del Oro")

if df_prices.empty:
    st.info("Sin datos de precio. Presiona 'Ejecutar Sentinel' para comenzar.")
else:
    # Preparar serie temporal con timestamp como índice
    df_chart = df_prices.set_index("timestamp")[["precio"]].rename(
        columns={"precio": "Precio USD"}
    )

    st.area_chart(
        df_chart,
        color="#FFB347",
        use_container_width=True,
        height=320,
    )

    with st.expander(f"Ver tabla de datos ({len(df_prices)} registros)"):
        st.dataframe(
            df_prices[["timestamp", "precio", "divisa", "fuente"]].sort_values(
                "timestamp", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )

st.markdown("<hr class='gold-divider'>", unsafe_allow_html=True)

# ─── Feed de noticias ─────────────────────────────────────────────────────────
st.subheader("Ultimas Noticias del Mercado")

if not noticias:
    st.info("Sin noticias. Presiona 'Ejecutar Sentinel' para comenzar.")
else:
    # Ordenar por fecha de extraccion y tomar las 5 mas recientes
    def parse_dt(n: dict) -> datetime:
        try:
            return datetime.fromisoformat(
                n.get("extraido_en", "1970-01-01T00:00:00Z").replace("Z", "+00:00")
            )
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    recientes = sorted(noticias, key=parse_dt, reverse=True)[:5]

    for noticia in recientes:
        titulo    = noticia.get("titulo", "Sin titulo")
        link      = noticia.get("link", "#")
        fecha_pub = noticia.get("fecha_publicacion", "")
        fuente    = noticia.get("fuente", "")

        # Formatear fecha legible
        try:
            dt_pub = datetime.fromisoformat(fecha_pub.replace("Z", "+00:00"))
            fecha_fmt = dt_pub.strftime("%d %b %Y  %H:%M UTC")
        except (ValueError, AttributeError):
            fecha_fmt = fecha_pub

        st.markdown(
            f"""
            <div class='news-card'>
                <a href='{link}' target='_blank'>{titulo}</a>
                <div class='news-meta'>{fecha_fmt} &nbsp;|&nbsp; {fuente}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr class='gold-divider'>", unsafe_allow_html=True)
st.caption(
    "GOLD-SENTINEL v1.0  |  Datos locales: `data/precios_oro.csv` · "
    "`data/noticias_oro.json`  |  Protocolo: INSTRUCTIONS.md"
)
