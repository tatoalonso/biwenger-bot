# Bot de Biwenger

Sistema con LLM que juegue por mí en Biwenger (fantasy de fútbol).

Reglas oficiales del juego (no nuestras) en [reglas-biwenger.md](reglas-biwenger.md)
— pasar como contexto fijo al LLM del bloque 3, y tenerlas presentes
en cualquier diseño. Incluyen al menos dos restricciones críticas para
el bot: saldo negativo al empezar jornada = 0 puntos, y -4 por cada
posición vacía en la alineación.

## Objetivo

Que el sistema tome o proponga decisiones de juego: fichajes, ventas,
alineación y pujas, con criterio propio y datos actualizados.

## Piezas del sistema

Son tres bloques bastante independientes. El scraping es la base: sin
datos, los otros dos no existen.

### 1. Scraping de la liga — ✅ hecho

- API de Biwenger reversada e implementada en `biwenger_bot/client.py`:
  login, plantilla, liga, mercado, histórico, y acciones de escritura
  (pujar, vender, alinear).
- Las acciones de escritura se sacaron de un repo de la comunidad de
  2020 y venían **mal**: `send_to_market()` no mandaba ni el jugador ni
  el tipo correcto (`"team"` en vez de `"sell"`). Corregido y dividido
  en `sell_player()` (venta instantánea a precio fijo), `auction_player()`
  (subasta, otros pujan) y `loan_player()` (cedible a cambio de cuota)
  — mismo endpoint `POST /market`, solo cambia `type`: `"sell"` /
  `"auction"` / `"loan"`. Los tres validados con pruebas reales. Hay
  un tercer botón, "venta inmediata" (ver aviso de peligro más abajo),
  que no pasa por `POST /market` — es la única de las cuatro acciones
  del menú de venta que es instantánea e irreversible. En `sell_player()`
  y `auction_player()` el precio SÍ lo elige el usuario en ambos casos
  (que en la prueba de subasta coincidiera con el valor de mercado del
  jugador fue casualidad de dejar el valor sugerido, no un campo
  bloqueado — corregido tras verificarlo con el usuario).
  El resto (`place_offer`, `respond_to_offer`,
  `set_lineup`) sigue sin contrastar contra una acción real — no
  fiarse hasta comprobarlas una a una igual que esta.
  - ⚠️ **Riesgo sin resolver en `transfers.py`**: el solver asume que vas
    a conseguir fichar a los candidatos al precio de la lista (`sales`,
    precio fijo), pero es "el primero que paga se lo lleva" — otro
    mánager puede adelantarse. Y como `place_offer()` no está validado
    contra la cuenta real, no sabemos cómo falla si llegas tarde (¿error
    limpio?, ¿reintento?). Antes de automatizar compras de verdad: (1)
    validar `place_offer()` en real, (2) decidir qué hace el bot si una
    compra del plan falla a mitad — ¿replantea con lo que queda, o para
    y avisa?
- **Estructura real de `GET /market`**: tres listas, no una.
  - `sales`: precio fijo elegido por el vendedor (`type: "sell"`).
    Tiene ventana de tiempo (`until`) igual que las otras — NO es
    instantánea, es "el primero que paga ese precio se lo lleva". Lo
    realmente instantáneo e irreversible es el botón aparte del 50%
    ya anotado más arriba, que no pasa por aquí.
  - `auctions`: subastas y cedibles juntos (`type: "auction"` o
    `"loan"`), precio también elegido por el vendedor — pero aquí sí
    hay negociación después (pujas u oferta de préstamo) antes de
    resolverse, a diferencia de `sales` que se cierra al precio pedido.
  - `offers`: MIS pujas/ofertas activas (no las de todos), con
    `status` (`"waiting"`, etc.) y `requestedPlayers`.
  - El campo `loans` que se ve en el JSON siempre sale `null`, no se
    usa para esto.
- **Mecánica confirmada por búsqueda web** (guías de la comunidad, no
  oficial): subastas exclusivas de **ligas Ultra** (la nuestra lo es).
  Cada puja nueva reinicia una cuenta atrás; si nadie supera la última
  antes de que expire, se la lleva. Probablemente por eso vimos
  `"extended": true` en algunas entradas del mercado.
  - ⚠️ **Corregido**: la guía web decía que `sales` caduca a las 48h.
    Es falso para nuestra liga — el dato real, sacado de
    `settings.daysForSale` vía API, es **7 días**. Prioridad siempre a
    los ajustes reales de la API sobre guías genéricas de comunidad.
- **⚠️ Peligro conocido, no implementar sin cuidado extra**: existe un
  botón de "venta inmediata" en la web, distinto de `sell_player()`,
  que da solo el 50% del valor del jugador (coincide con
  `settings.immediateSales: 50` de la liga) y es irreversible. El bot
  no debe poder disparar esto nunca por accidente.
- `client.league()` pide ahora `fields=*,standings,group,settings,users`
  (antes solo `settings(description)`) — trae los 106 campos reales de
  configuración de la liga de una sola llamada, sin necesidad de ir
  copiando pantallas de ajustes de la web. Detalle completo en
  [reglas-biwenger.md](reglas-biwenger.md).
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
    Reutiliza las mismas variables que la alineación (`fitness`,
    `status`, `points`, `difficulty`, `position`) — el LLM estima
    puntos previstos del candidato igual que para un jugador propio.
  - **Fichaje especulación**: jugador con tendencia alcista de valor,
    para comprar y revender a corto plazo por plusvalía, sin importar
    si hace falta en el equipo. Variables distintas: no puntos, sino
    `priceIncrement` y el histórico `prices` (mismo dato que ya usa
    `money.py`), mirando tendencia de precio de los últimos días.
  - **Por qué no un solo solver conjunto**: puntos de fantasy (plantilla)
    y euros de plusvalía (especulación) no se pueden sumar en una misma
    función a maximizar sin inventar una tasa de conversión arbitraria
    entre las dos unidades — eso rompería la garantía de "sin ambigüedad"
    que hace bueno a un solver.
  - **Solución: secuenciar las dos fases, no mezclarlas.**
    1. **PuLP fase plantilla** (`biwenger_bot/transfers.py`, igual que
       `lineup.py` pero para fichajes): dado tu plantilla + los ~10-15
       candidatos del mercado + tu caja, decide qué combinación de
       ventas (jugadores flojos) + compras (candidatos que suben el
       total de puntos previstos) maximiza la ganancia neta de puntos,
       sin superar el presupuesto (caja + lo estimado de las ventas).
       Esto sustituye a "comparar candidato vs. jugador más débil" —
       lo generaliza a toda la plantilla y el mercado a la vez, como
       `best_lineup()` generalizó las formaciones.
    2. **Ejecutar** esos movimientos reales (`sell_player()`,
       `place_offer()`, etc.).
    3. **Releer el saldo real** de la API tras esos movimientos.
    4. **Especulación con lo que sobre**: ranking simple por tendencia
       de precio (sin solver), gastando solo la caja libre tras la
       fase 1 — priorizar mejorar el equipo antes de especular con lo
       sobrante tiene sentido futbolístico, no solo matemático.
- **Alineación: LLM + solver, no solo LLM.** Elegir los 11 que cumplen
  la formación (ej. 4-3-3) y maximizan puntos es un problema de
  optimización combinatoria (tipo "mochila") — un LLM no garantiza
  cumplir las restricciones exactas (podría saltarse la formación o el
  presupuesto), y probar todas las combinaciones a fuerza bruta se
  dispara en tiempo si el número de candidatos crece (visto en un TFG
  real sobre esto mismo — más abajo). Mejor repartir el trabajo:
  - El LLM estima puntos previstos por jugador (usando lesiones, forma,
    dificultad del rival — su punto fuerte, juicio con info incompleta).
  - Un solver de optimización (ej. `pulp` o `ortools` — con nuestros
    ~15 jugadores de plantilla resuelve en milisegundos, no hace falta
    nada artesanal) coge esos puntos + las reglas de la liga (formación,
    presupuesto) y devuelve la combinación óptima garantizada.
  - Referencia: TFG "Desarrollo de un sistema de soporte a la decisión
    para juegos de gestión deportiva" (ETSII, A. Cuadrado, 2024, sobre
    Biwenger) formaliza este mismo problema como programación lineal
    entera y lo resuelve con backtracking casero (sin solver) — con
    pocos candidatos va bien, pero se les disparó a más de 1 hora al
    crecer el número de jugadores; confirma que un solver de verdad es
    mejor camino que reimplementar la búsqueda a mano. Su sistema de
    puntuación propio (a partir de estadísticas de partido en bruto) no
    nos vale — no tenemos esos datos granulares y ya delegamos ese
    juicio al LLM. Tampoco tienen en cuenta lesiones (usan solo media
    histórica), algo que nosotros ya resolvemos mejor con
    `status`/`statusInfo` de la propia API. Código en
    github.com/cuadantonio/TFG-AI_Assitant (solo la lógica del
    algoritmo es aprovechable, el resto — MongoDB, app de escritorio —
    no aplica a nuestro diseño).
- **Calibrar cuánto pujar con datos reales de la liga — ✅ hecho**
  (`biwenger_bot/bidding.py`, `scripts/record_bids.py`). Cada
  movimiento `market` del histórico trae la puja ganadora y todas las
  perdedoras para ese jugador. Cruzando con el valor del jugador ese
  día (mismo mecanismo que en `money.py`) se calcula el % de
  sobreoferta necesario para ganar, agrupado por nº de pujantes.
  - **Separación jugador libre vs. no libre, resuelta con datos reales
    de esta temporada**: los 131 movimientos `market` de este año
    fueron TODOS de jugadores libres — nadie ha subastado un jugador ya
    fichado. Los traspasos de jugadores no libres pasan por otra vía,
    `transfer` con `from` Y `to` a la vez, y casi siempre son
    `type: "clause"` (pago de cláusula, 200% del valor — dato ya
    conocido, no hace falta histórico). Los pocos traspasos directos
    sin cláusula (8 esta temporada) muestran un ratio pagado/valor de
    ~1,03 a 1,65 (mediana ~1,24) — confirma que no se acepta el valor
    de mercado tal cual para un jugador ajeno.
  - **Resultado con datos reales de esta temporada** (mediana, más
    robusta que la media con pocas muestras): 1 pujante → 0,5%, 2 →
    5,0%, 3 → 21,7%, 4 → 35,4%, 5+ → ~43%. No coincide exactamente con
    la hipótesis inicial (20%/40%), pero confirma la tendencia. Con
    pocas muestras para 4+ pujantes, cae al bidder_count más cercano
    con datos suficientes (`min_samples`).
  - **Por qué hay que persistirlo YA, no solo calcularlo al vuelo**: el
    histórico de precios de cada jugador (`prices`) solo cubre ~1 año.
    Dentro de un año, las resoluciones de mercado de ahora ya no se
    podrán recalcular — por eso `record_market_resolutions()` va
    guardando en `data/bid_history.jsonl` (JSON Lines, sin base de
    datos, fuera de git) cada vez que se ejecuta, acumulando muestras
    temporada tras temporada en vez de partir de cero cada vez.
    `since` por defecto usa el reset de la temporada actual — no hace
    falta acordarse de pasarlo para no colar temporadas viejas.
  - **Dato en vivo útil**: `POST /market/bids` con `{"player": id}`
    devuelve cuántas pujas tiene ahora mismo un jugador del mercado
    (`bid_count()` en el cliente). Sirve para ver cuánta competencia
    hay por un jugador concreto antes de decidir cuánto ofrecer, más
    allá de la calibración histórica.

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
- **Nivel de autonomía — decidido, en dos fases**:
  1. **Ahora**: bot de Telegram. El cron manda las recomendaciones
     (alineación, fichajes, pujas) por Telegram y yo las confirmo a
     mano antes de que se ejecute nada real. Encaja con que las
     acciones de escritura (`place_offer`, `set_lineup`...) siguen sin
     validar — no tiene sentido autoejecutar antes de eso de todas
     formas.
  2. **A la larga**: autonomía completa, el bot juega solo sin
     confirmación humana. Pendiente de construir el bot de Telegram
     (sin empezar) y de decidir cuándo dar el salto a la fase 2.

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
