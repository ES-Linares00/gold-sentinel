# PROTOCOLO DE EXTRACCIÓN Y MONITOREO (GOLD-SENTINEL)

## 1. OBJETIVO DEL SISTEMA
Desarrollar un motor de recolección de datos tecno-fundamentales (precios de activos y noticias geopolíticas) con un enfoque en persistencia, sigilo y soberanía de datos.

## 2. REGLAS DE DESARROLLO (SKILLS REQUERIDAS)

### A. Resiliencia de Conexión (Anti-429)
- **Backoff Exponencial:** Ante un error HTTP 429 o 403, el agente debe esperar un tiempo creciente antes de reintentar.
- **Jitter (Ruido Aleatorio):** Nunca usar esperas fijas. Añadir una variación aleatoria del +/- 20% al tiempo de espera para evitar patrones detectables por WAFs (Web Application Firewalls).
- **Circuit Breaker:** Si tras 5 intentos el error persiste, el script debe abortar la tarea actual y registrar el fallo en un log de errores, no entrar en bucles infinitos.

### B. Sigilo y Huella Digital (Stealth)
- **Rotación de Headers:** Cada sesión debe iniciar con un `User-Agent` de navegador moderno (Chrome, Safari, Edge) rotado aleatoriamente.
- **Headers Miméticos:** Incluir `Accept-Language`, `Referer` y `Sec-Fetch` para simular una navegación humana real.

### C. Arquitectura de Datos (Soberanía)
- **Persistencia Local:** Priorizar el uso de archivos `.csv` o bases de datos ligeras como `SQLite` alojadas localmente. 
- **Modo Append:** Nunca sobrescribir datos existentes. Las nuevas extracciones se añaden al final del archivo con un `timestamp` preciso (ISO 8601).
- **Modularidad:** Separar la lógica de 'Navegación' (Scraper) de la lógica de 'Procesamiento' (Parser).

### D. Calidad de Software (ADSO Standards)
- **Documentación:** Cada función debe tener un Docstring explicando qué hace, qué recibe y qué devuelve.
- **Tipado:** Usar `type hints` de Python para mejorar la legibilidad y el mantenimiento.
- **Gestión de Entorno:** Todas las dependencias deben quedar registradas en un archivo `requirements.txt`.

## 3. PROHIBICIONES ESTRICTAS
- NO usar claves de API en el código (hardcoding). Usar archivos `.env`.
- NO realizar más de 1 petición por segundo a la misma fuente a menos que sea necesario.
- NO subir carpetas de entorno virtual (`venv/`) o archivos de datos masivos a sistemas de control de versiones sin `.gitignore`.