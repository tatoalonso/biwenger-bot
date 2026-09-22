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
    puntos previstos del candidato igual que para un jugador propio, y
    se compara contra el más flojo de la plantilla en esa posición.
  - **Fichaje especulación**: jugador con tendencia alcista de valor,
    para comprar y revender a corto plazo por plusvalía, sin importar
    si hace falta en el equipo. Variables distintas: no puntos, sino
    `priceIncrement` y el histórico `prices` (mismo dato que ya usa
    `money.py`), mirando tendencia de precio de los últimos días.
  - El solver (ver más abajo) no hace falta para fichajes normales —
    con ~15 candidatos y un movimiento cada vez basta con comparar
    candidato vs. jugador más débil. Se reserva para la alineación,
    donde sí hay combinatoria real (11 de 15 con restricciones
    estrictas). Si algún día se quisiera optimizar varios fichajes a
    la vez con presupuesto limitado, ahí sí tendría sentido — es el
    problema completo del TFG citado abajo, con precio incluido.
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
    Confirmado que el concepto es real: `GET /market` (listados activos
    ahora mismo) sí trae `user: null` para jugador libre vs.
    `user: {id, name}` para el mánager que lo vende — pero eso no sirve
    para el histórico, `board` no expande `player` aunque se le pida
    con `fields` (se probó y no funciona), así que ahí toca seguir
    usando el truco del `transfer` emparejado.
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
