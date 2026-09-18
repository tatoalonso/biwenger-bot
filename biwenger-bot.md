# Bot de Biwenger

Sistema con LLM que juegue por mí en Biwenger (fantasy de fútbol).

## Objetivo

Que el sistema tome o proponga decisiones de juego: fichajes, ventas,
alineación y pujas, con criterio propio y datos actualizados.

## Piezas del sistema

Son tres bloques bastante independientes. El scraping es la base: sin
datos, los otros dos no existen.

### 1. Scraping de la liga — ✅ hecho

- API de Biwenger reversada e implementada en `biwenger_bot/client.py`:
  login, plantilla, liga, mercado, histórico, y acciones de escritura
  (pujar, vender, alinear — estas últimas sin probar todavía en real).
- Persistencia entre ejecuciones: todavía no implementada (de momento
  cada script vuelve a pedir los datos a la API).

### 2. Estimación del dinero de los rivales — ✅ hecho

- Implementado en `biwenger_bot/money.py`, validado al céntimo contra
  el saldo real propio (`scripts/money_report.py`).
- Fórmula: presupuesto inicial del reset de temporada (20M, confirmado
  por texto de la propia liga) + ventas − compras + primas (jornada,
  racha diaria) + préstamos netos − subidas de cláusula.
- Limitación conocida: solo hay verdad-terreno para el equipo propio;
  un mecanismo de dinero que nadie en la liga haya usado nunca podría
  pasar desapercibido (ya pasó una vez con los préstamos).

### 3. Recomendaciones con LLM

- Entrada: estado de mi plantilla + mercado + dinero estimado de rivales.
  El mercado en Biwenger nunca tiene más de ~15 jugadores a la vez, así
  que plantilla + mercado (~30 jugadores) se le puede pasar al LLM tal
  cual, sin preprocesar con heurísticas propias.
- Acceso a web para noticias: lesiones, alineaciones probables,
  sanciones, rotaciones. Limitado a esos ~30 jugadores, no a los 546
  de La Liga, para no disparar el gasto de tokens/búsquedas.
- Salida: qué pujar y cuánto, a quién vender, cómo alinear. Los
  fichajes se dividen en dos tipos de recomendación distintos:
  - **Fichaje equipo**: para cubrir una posición débil de la plantilla.
  - **Fichaje especulación**: jugador con tendencia alcista de valor,
    para comprar y revender a corto plazo por plusvalía, sin importar
    si hace falta en el equipo. Se detecta con `priceIncrement` y el
    histórico `prices` (mismo dato que ya usa `money.py`), mirando la
    tendencia de los últimos días.
- **Idea: calibrar cuánto pujar con datos reales de la liga.** Cada
  movimiento `market` del histórico trae la puja ganadora y todas las
  perdedoras para ese jugador. Cruzando con el valor del jugador ese
  día (mismo mecanismo que en `money.py`), se puede calcular qué % de
  sobreoferta sobre el valor hace falta para ganar una puja con cierta
  probabilidad (ej. "pujar 20% por encima gana el 90% de las veces") y
  usar eso para recomendar el importe. Limitado a ~1 año de histórico
  (lo que cubre el precio diario de cada jugador).
  - **Ojo**: separar jugador libre vs. jugador puesto en venta por otro
    mánager — mezclar los dos casos mete ruido, la dinámica de puja
    puede ser distinta. El propio movimiento `market` no dice si había
    dueño previo (no trae `from`), pero se puede inferir: si existe un
    `transfer` emparejado (mismo jugador, fecha cercana, con `from`)
    es que alguien lo vendía; si no hay pareja, era jugador libre.

## Persistencia

Sin base de datos — ficheros JSON Lines (un JSON por línea, se va
añadiendo) en una carpeta `data/` fuera de git (como `.env`, es estado
de ejecución, no código; cada máquina acumula el suyo). Si algún día
hace falta consultas más complejas, migrar a SQLite desde aquí es
sencillo, pero de momento esto es lo mínimo que funciona.

- **`data/rival_cash.jsonl`** — snapshot diario de caja+valor por
  equipo, para ver tendencias (quién lleva semanas sin gastar = puede
  estar ahorrando para una puja fuerte), no solo la foto del momento:
  ```json
  {"date": "2026-09-18", "team_id": 14148584, "team_name": "SUCO TEAM", "cash": 1230393, "team_value": 43620000}
  ```
- **`data/recommendations.jsonl`** — log de lo que recomienda el bot
  vs. lo que hago yo, para evaluar aciertos con el tiempo y más
  adelante dárselo de contexto al LLM. El campo `hecho` se rellena
  después (a mano, o comparando contra el `board` del día siguiente):
  ```json
  {"date": "2026-09-18", "type": "fichaje_especulacion", "player_id": 26271, "player_name": "Yamal", "detalle": "tendencia alcista, +8% últimos 5 días", "amount": 27000000, "hecho": null}
  ```
- El histórico de movimientos de Biwenger (`board`) NO hace falta
  duplicarlo local — la API ya lo guarda todo sin límite aparente
  (probado hasta 2018). Persistir aquí solo aportaría velocidad, no
  datos que no se puedan volver a pedir.

## Decisiones pendientes

- **Dónde corre**: Raspberry Pi, con ejecución diaria programada
  (cron). Pendiente de montar.
- **Vigilancia del mercado**: el mercado rota a diario, así que algo
  tiene que ejecutarse solo si quiero no perderme nada.
- **Nivel de autonomía**: ¿decide y ejecuta, o solo propone y yo
  confirmo? Empezar por proponer es más seguro.

## Requisitos descubiertos

- **Login diario obligatorio**: Biwenger da 250.000€ de prima por
  conectarse 5 días seguidos (movimiento `bonus`/`dailyStreak` en el
  histórico). La ejecución diaria en la Raspberry debe hacer login
  siempre, aunque ese día no haya ninguna otra acción que tomar, para
  no romper la racha.

## Por dónde empezar

Bloques 1 y 2 (scraping y dinero de rivales) hechos. Lo que queda:

- Bloque 3 (recomendaciones con LLM) — sin empezar.
- Validar en real las acciones de escritura (pujar, vender, alinear)
  antes de fiarse de ellas.
- Montar la ejecución diaria en la Raspberry (incluyendo el login
  diario para no perder la prima por racha).

## Notas

- Entorno: MacBook Pro 13" 2017, Intel i5, 8 GB. Suficiente para
  scraping y llamadas a API; nada de modelos en local.
- El LLM iría por API pagada de mi bolsillo (el presupuesto de
  formación de la empresa no cubre APIs).
