# Gold-Sentinel: Inteligencia Tecno-Fundamental

Un ecosistema multi-agente que monitorea el mercado del oro en tiempo real, combinando datos de precio spot con análisis de noticias financieras, y presentándolos en un dashboard web interactivo.

---

## ¿Qué hace?

Gold-Sentinel corre dos agentes de forma autónoma y orquestada:

| Agente | Fuente | Datos que produce |
|---|---|---|
| **PriceAgent** | Yahoo Finance (GC=F — Gold Futures) | Precio spot en USD, guardado en `data/precios_oro.csv` |
| **NewsAgent** | Google News RSS | Titulares filtrados por relevancia, guardados en `data/noticias_oro.json` |

Los resultados se visualizan en una app Streamlit con métricas en vivo, gráfica interactiva y feed de noticias.

---

## Arquitectura

```
monitor_oro/
├── core/
│   └── base_agent.py      # Clase abstracta: Backoff Exponencial + Jitter + Circuit Breaker
├── agents/
│   ├── price_agent.py     # Extrae precio del oro vía API JSON de Yahoo Finance
│   └── news_agent.py      # Extrae y filtra noticias vía RSS de Google News
├── data/
│   ├── precios_oro.csv    # Historial de precios (append, nunca sobreescribe)
│   └── noticias_oro.json  # Noticias acumuladas (deduplicadas por link)
├── logs/
│   └── sentinel.log       # Log de ejecución de todos los agentes
├── app.py                 # Dashboard web (Streamlit)
├── main.py                # Orquestador: ejecuta agentes en secuencia
├── visualizer.py          # Genera gráfica estática PNG (matplotlib)
└── requirements.txt
```

---

## Protocolos de resiliencia (INSTRUCTIONS.md)

Todos los agentes heredan de `BaseAgent` e implementan:

- **Backoff Exponencial + Jitter ±20%**: ante errores HTTP 429/403, espera un tiempo creciente con variación aleatoria para evitar patrones detectables por WAFs.
- **Circuit Breaker**: si tras 5 intentos el error persiste, aborta y registra el fallo en `logs/errors.log` sin entrar en bucles infinitos.
- **Rotación de User-Agents**: cada sesión HTTP inicia con un User-Agent moderno (Chrome, Edge, Safari, Firefox) elegido aleatoriamente, más headers miméticos (`Referer`, `Accept-Language`, `Sec-Fetch-*`).
- **Modo Append**: los datos nunca se sobreescriben; cada extracción se añade con timestamp ISO 8601 UTC.

---

## Instalación local

**Requisitos:** Python 3.10+

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/gold-sentinel.git
cd gold-sentinel

# 2. Crear y activar entorno virtual
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Uso

### Ejecutar los agentes (recolectar datos)

```bash
python main.py
```

Salida esperada:
```
--------------------------------------------------
  GOLD-SENTINEL -- PriceAgent
--------------------------------------------------
  Timestamp : 2026-03-25T13:35:56Z
  Precio    : 4,557.80 USD
  Fuente    : Yahoo Finance (GC=F - Gold Futures)
--------------------------------------------------

--------------------------------------------------
  GOLD-SENTINEL -- NewsAgent
--------------------------------------------------
  Noticias en feed    : 100
  Nuevas guardadas    : 20
  Total en JSON       : 120
--------------------------------------------------
```

### Lanzar el dashboard web

```bash
streamlit run app.py
```

Abre automáticamente `http://localhost:8501`. Desde el sidebar puedes presionar **"Ejecutar Sentinel"** para actualizar los datos sin salir de la interfaz.

### Generar gráfica estática (opcional)

```bash
python visualizer.py
# Guarda: data/analisis_oro.png
```

---

## Despliegue en Streamlit Cloud

1. Sube el repositorio a GitHub (los archivos `data/*.csv` y `data/*.json` deben estar incluidos para que la app tenga datos al arrancar).
2. Entra a [share.streamlit.io](https://share.streamlit.io) y conecta el repo.
3. Configura:
   - **Main file path:** `app.py`
   - **Python version:** 3.11
4. Streamlit Cloud instalará automáticamente las dependencias desde `requirements.txt`.

> **Nota:** En Streamlit Cloud el botón "Ejecutar Sentinel" puede estar limitado por las políticas de red del servidor. Para producción se recomienda un scheduler externo (cron, GitHub Actions) que ejecute `main.py` periódicamente y haga push de los datos al repositorio.

---

## Variables de entorno

Copia `.env.example` como `.env` y completa los valores (solo necesarios para funcionalidades futuras del NewsAgent):

```bash
cp .env.example .env
```

```env
NEWSAPI_KEY=tu_clave_aqui
ALPHAVANTAGE_KEY=tu_clave_aqui
```

**Nunca subas el archivo `.env` al repositorio.**

---

## Tecnologías

| Librería | Uso |
|---|---|
| `requests` | Peticiones HTTP resilientes |
| `beautifulsoup4` | Parsing HTML (reservado para expansión) |
| `feedparser` | Parsing de feeds RSS |
| `pandas` | Manipulación de datos tabulares |
| `matplotlib` | Gráfica estática de correlación |
| `streamlit` | Dashboard web interactivo |
| `python-dotenv` | Gestión de variables de entorno |

---

## Licencia

MIT — libre para uso educativo y personal.

---

*Proyecto desarrollado como práctica de arquitectura de software orientada a agentes, siguiendo los estándares ADSO de documentación, tipado y modularidad.*
