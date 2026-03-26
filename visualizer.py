"""
visualizer.py
-------------
Capa de visualización del ecosistema GOLD-SENTINEL.

Carga los datos de precios (CSV) y noticias (JSON), los alinea en una
escala temporal común y genera una gráfica de doble eje que correlaciona
el precio spot del oro con el volumen de noticias financieras por día.

Salida: data/analisis_oro.png
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # backend no-interactivo: guarda PNG sin bloquear
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# ─── Rutas ───────────────────────────────────────────────────────────────────
CSV_PATH = Path("data/precios_oro.csv")
JSON_PATH = Path("data/noticias_oro.json")
OUTPUT_PATH = Path("data/analisis_oro.png")

# ─── Paleta de colores ────────────────────────────────────────────────────────
COLOR_GOLD = "#FFB347"       # línea de precio
COLOR_GOLD_FILL = "#FFD700"  # relleno bajo la línea
COLOR_NEWS = "#4A90D9"       # barras de noticias
COLOR_NEWS_ALPHA = 0.55


# ─── Carga y preparación de datos ────────────────────────────────────────────

def load_prices(path: Path) -> pd.DataFrame:
    """
    Carga el CSV de precios y prepara la columna temporal.

    Agrupa por día calculando el precio medio para suavizar múltiples
    capturas del mismo día.

    Args:
        path (Path): Ruta al archivo CSV.

    Returns:
        pd.DataFrame: DataFrame con columnas ['fecha', 'precio'] por día.

    Raises:
        FileNotFoundError: Si el CSV no existe.
        ValueError: Si el CSV está vacío o mal formado.
    """
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de precios: {path}")

    df = pd.read_csv(path, parse_dates=["timestamp"])

    if df.empty:
        raise ValueError("El CSV de precios está vacío.")

    df["fecha"] = df["timestamp"].dt.normalize()
    df_day = df.groupby("fecha", as_index=False)["precio"].mean()
    df_day.rename(columns={"precio": "precio_medio"}, inplace=True)
    return df_day


def load_news(path: Path) -> pd.DataFrame:
    """
    Carga el JSON de noticias y cuenta titulares por día.

    Usa 'fecha_publicacion' como eje temporal para reflejar cuándo
    ocurrieron los eventos, no cuándo se recolectaron.

    Args:
        path (Path): Ruta al archivo JSON.

    Returns:
        pd.DataFrame: DataFrame con columnas ['fecha', 'num_noticias'] por día.

    Raises:
        FileNotFoundError: Si el JSON no existe.
        ValueError: Si el JSON está vacío.
    """
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de noticias: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        raise ValueError("El JSON de noticias está vacío.")

    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha_publicacion"], utc=True).dt.normalize()
    df_day = df.groupby("fecha").size().reset_index(name="num_noticias")
    return df_day


def align_ranges(
    df_prices: pd.DataFrame, df_news: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    """
    Calcula el rango temporal a visualizar y rellena días sin datos.

    Estrategia de rango:
    - Si los datos de precio y noticias se solapan, usa la intersección ampliada.
    - Si no hay solapamiento, usa el rango completo de noticias y marca los
      precios como puntos aislados.

    Args:
        df_prices (pd.DataFrame): Precios diarios.
        df_news   (pd.DataFrame): Volumen de noticias diario.

    Returns:
        tuple: (df_prices, df_news, fecha_inicio, fecha_fin) con índice
               temporal completo (sin huecos de días).
    """
    date_min = min(df_prices["fecha"].min(), df_news["fecha"].min())
    date_max = max(df_prices["fecha"].max(), df_news["fecha"].max())

    full_index = pd.date_range(date_min, date_max, freq="D", tz="UTC")

    df_news = df_news.set_index("fecha").reindex(full_index, fill_value=0).reset_index()
    df_news.rename(columns={"index": "fecha"}, inplace=True)

    return df_prices, df_news, date_min, date_max


# ─── Generación de la gráfica ─────────────────────────────────────────────────

def build_chart(
    df_prices: pd.DataFrame,
    df_news: pd.DataFrame,
    date_min: pd.Timestamp,
    date_max: pd.Timestamp,
) -> None:
    """
    Construye y guarda la gráfica de doble eje (precio + volumen de noticias).

    Eje Y izquierdo : Precio medio diario del oro (línea + relleno).
    Eje Y derecho   : Volumen de noticias por día (barras semitransparentes).

    Args:
        df_prices (pd.DataFrame): Precios diarios con columnas ['fecha', 'precio_medio'].
        df_news   (pd.DataFrame): Noticias diarias con columnas ['fecha', 'num_noticias'].
        date_min  (pd.Timestamp): Límite izquierdo del eje X.
        date_max  (pd.Timestamp): Límite derecho del eje X.
    """
    # ── Estilo ────────────────────────────────────────────────────────────────
    available = plt.style.available
    for style in ("seaborn-v0_8-darkgrid", "seaborn-darkgrid", "ggplot"):
        if style in available:
            plt.style.use(style)
            break

    fig, ax1 = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#1C1C2E")
    ax1.set_facecolor("#1C1C2E")

    # ── Eje derecho: volumen de noticias (barras) ─────────────────────────────
    ax2 = ax1.twinx()

    bar_dates = list(df_news["fecha"].dt.to_pydatetime())
    ax2.bar(
        bar_dates,
        df_news["num_noticias"],
        color=COLOR_NEWS,
        alpha=COLOR_NEWS_ALPHA,
        width=0.8,
        label="Volumen de noticias",
        zorder=2,
    )
    ax2.set_ylabel("Noticias por día", color=COLOR_NEWS, fontsize=11, labelpad=10)
    ax2.tick_params(axis="y", colors=COLOR_NEWS)
    ax2.spines["right"].set_color(COLOR_NEWS)
    ax2.set_ylim(bottom=0, top=df_news["num_noticias"].max() * 3.5)

    # ── Eje izquierdo: precio del oro (línea + relleno) ───────────────────────
    price_dates = list(df_prices["fecha"].dt.to_pydatetime())
    price_vals = df_prices["precio_medio"].reset_index(drop=True)

    ax1.plot(
        price_dates,
        price_vals,
        color=COLOR_GOLD,
        linewidth=2.5,
        marker="o",
        markersize=6,
        markerfacecolor=COLOR_GOLD_FILL,
        markeredgecolor="#333333",
        markeredgewidth=0.8,
        label="Precio oro (USD)",
        zorder=5,
    )
    ax1.fill_between(
        price_dates,
        price_vals,
        price_vals.min() * 0.998,
        color=COLOR_GOLD_FILL,
        alpha=0.15,
        zorder=4,
    )

    # Anotación del último precio
    if not df_prices.empty:
        last_date = price_dates[-1]
        last_price = price_vals.iloc[-1]

        ax1.annotate(
            f"  ${last_price:,.2f}",
            xy=(last_date, last_price),
            fontsize=10,
            color=COLOR_GOLD_FILL,
            fontweight="bold",
            va="bottom",
        )

    ax1.set_ylabel("Precio spot del oro (USD)", color=COLOR_GOLD, fontsize=11, labelpad=10)
    ax1.tick_params(axis="y", colors=COLOR_GOLD)
    ax1.spines["left"].set_color(COLOR_GOLD)

    price_range = price_vals.max() - price_vals.min() if len(price_vals) > 1 else price_vals.iloc[0] * 0.01
    ax1.set_ylim(
        price_vals.min() - price_range * 2,
        price_vals.max() + price_range * 8,
    )

    # ── Eje X: fechas ─────────────────────────────────────────────────────────
    span_days = (date_max - date_min).days

    if span_days <= 7:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M"))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    elif span_days <= 60:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    elif span_days <= 365:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=35, ha="right", color="#CCCCCC")
    ax1.tick_params(axis="x", colors="#CCCCCC")

    for spine in ("top", "bottom"):
        ax1.spines[spine].set_color("#444444")
        ax2.spines[spine].set_color("#444444")
    ax1.spines["left"].set_color(COLOR_GOLD)
    ax2.spines["right"].set_color(COLOR_NEWS)

    ax1.grid(True, linestyle="--", linewidth=0.5, color="#333355", alpha=0.7)

    # ── Títulos y leyenda ─────────────────────────────────────────────────────
    fig.suptitle(
        "GOLD-SENTINEL  |  Precio del Oro vs. Volumen de Noticias",
        fontsize=15,
        fontweight="bold",
        color="#F0E68C",
        y=0.98,
    )
    ax1.set_title(
        f"Rango: {date_min.strftime('%d %b %Y')} — {date_max.strftime('%d %b %Y')}  "
        f"({span_days + 1} días)   |   Fuente: Yahoo Finance / Google News RSS",
        fontsize=9,
        color="#AAAAAA",
        pad=6,
    )

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    legend = ax1.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc="upper left",
        framealpha=0.25,
        facecolor="#2A2A3E",
        edgecolor="#555566",
        labelcolor="white",
        fontsize=10,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    # ── Guardar ───────────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"\nGrafica guardada en: {OUTPUT_PATH.resolve()}")

    plt.close(fig)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Punto de entrada del visualizador. Orquesta carga, procesamiento y render.
    """
    print("Cargando datos...")

    try:
        df_prices = load_prices(CSV_PATH)
        df_news = load_news(JSON_PATH)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(f"  Precios : {len(df_prices)} dia(s)  |  rango {df_prices['fecha'].min().date()} -> {df_prices['fecha'].max().date()}")
    print(f"  Noticias: {df_news['num_noticias'].sum():.0f} titulares en {(df_news['num_noticias'] > 0).sum()} dia(s)")

    df_prices, df_news, date_min, date_max = align_ranges(df_prices, df_news)

    print("Generando grafica...")
    build_chart(df_prices, df_news, date_min, date_max)


if __name__ == "__main__":
    main()
