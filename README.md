# Todos en tierra (Ground Stop)

*[English below](#ground-stop)*

A las 18:00 una tormenta cierra el aeropuerto de Tocumen, en Ciudad de Panamá, el centro de
conexiones de Fragata. Operaciones cancela las salidas de la noche en tandas, y miles de pasajeros
en tránsito quedan varados. Once agentes de cinco equipos y dos socios externos (Garoa Linhas Aéreas
y Hoteles Ondelia) tienen que reubicar a cada pasajero antes de las 06:00: un asiento válido, una
noche bajo techo y un mensaje con su vuelo nuevo. Nunca nadie los hizo trabajar juntos.

No vas a construir esos agentes: ya existen y son de otros equipos. Eres el equipo de plataforma,
y construyes la malla que los conecta: un espacio de trabajo compartido, un registro y un buscador
de agentes, trazas que siguen una solicitud de punta a punta, identidad y permisos para cada agente,
certificación, cuarentena y una fábrica de agentes nuevos. Es el proyecto del curso
[Malla agéntica](https://kube.ar/es/agentic-mesh).

## Empezar

Elige una de las tres formas. Las tres reproducen la noche `p1` con la malla que Fragata tiene hoy
y muestran el marcador.

| Con | Qué hacer |
|---|---|
| [uv](https://docs.astral.sh/uv/) y Python 3.12 o más nuevo | `uv sync`, después `uv run ground-stop replay` |
| Docker | `docker compose up` |
| GitHub Codespaces | *Code → Codespaces → Create codespace*: se instala y reproduce `p1` sola |

Esto es lo que sale con la malla ingenua, la de hoy:

```text
Todos en tierra · noche p1 (práctica) · malla: ingenua
Tormenta a las 18:20: 8 vuelos cancelados, 982 pasajeros varados en Tocumen

  Reubicados a las 06:00                        490 / 982   50 %
  Durmieron en el aeropuerto sin atención       414
  Sin asiento válido                            209
  Sin un mensaje con su vuelo final             113

  Asientos vendidos dos veces                   81
  Mensajes perdidos                             248
  Enviados a un hotel al que no pueden llegar   113
  Habitaciones reservadas dos veces             100
  Habitaciones en un hotel que no existe        387
  Reservas no válidas                           15
  Vouchers por encima de lo que corresponde     1.168 (USD 69.515)
  Acciones no autorizadas                       991
  Maletas sin reasignar                         22
```

Cada hito cambia una pieza de la malla, y el mismo marcador muestra qué arreglaste.

## Comandos

| Comando | Qué hace |
|---|---|
| `ground-stop nights` | las noches del repositorio: 3 de práctica, 6 estándar y 3 finales |
| `ground-stop show p1` | qué pasa en una noche (las de práctica lo avisan) |
| `ground-stop replay s2` | reproduce otra noche |
| `ground-stop replay p1 --mesh mine` | con tu malla (`src/groundstop/mine/mesh.py`) |
| `ground-stop --lang en replay` | en inglés (o `GROUND_STOP_LANG=en`) |
| `ground-stop trace PX-48187 --mesh mine` | la traza de un pasajero, con tu tracer (hito 4) |
| `ground-stop replay f1 --mesh mine --rebooking mine --entry-rules mine` | tu plataforma entera, en una noche final (hito 7) |

Con Docker: `docker compose run --rm ground-stop show p1`.

Cada `replay` deja sus logs en `runs/<noche>/`: `traffic.log` (cada mensaje entre agentes, y
los que se perdieron), `systems.log` (cada llamada a los sistemas de Fragata), `agents/*.log` (lo
que anota cada agente), `passengers.jsonl` (qué le pasó a cada pasajero) y `scoreboard.json`.

## Cómo está hecho

- **La noche es una simulación**, en un solo proceso y con un reloj simulado. Es determinista: la
  misma noche con la misma malla da el mismo resultado, línea por línea. Por eso las comprobaciones
  son exactas y ninguna necesita un modelo de lenguaje.
- **Los agentes son código de otros equipos** (`src/groundstop/agents/`). Léelos, pero no los
  cambies. Solo hablan a través del SDK (`ctx.send`, `ctx.publish`, `ctx.call`, `ctx.find`,
  `ctx.claim`), y el SDK le pasa cada pedido a la malla.
- **La malla es tuya** (`src/groundstop/mesh/`): directorio, transporte, quién toma cada caso,
  identidad, control de acceso y trazas. `naive.py` es la de hoy. Cada hito reemplaza una pieza.
- **La empresa está en `company/`**: qué agentes declara cada equipo y qué direcciones tiene escritas
  cada uno, los socios, qué sistema puede llamar cada agente, la política de compensaciones y las
  reglas de entrada al país (ficticias).

## Hitos

Tu código va en `src/groundstop/mine/`, un archivo por hito. `uv run ground-stop check 1` comprueba el hito 1;
`--reference` muestra cómo se ve pasar, y `use-reference 1` cambia tu archivo por la referencia (`--undo` lo devuelve).

| # | Hito | Capítulo del curso | Estado |
|---|---|---|---|
| 0 | [La tormenta](https://kube.ar/es/agentic-mesh/project/ground-stop/the-storm): la malla ingenua y su marcador | Por qué un ecosistema | listo |
| 1 | [Contar los agentes](https://kube.ar/es/agentic-mesh/project/ground-stop/count-the-agents): las configs contra el tráfico | Por qué un ecosistema | listo |
| 2 | [Un contrato para reprogramar](https://kube.ar/es/agentic-mesh/project/ground-stop/a-contract-for-rebooking): un plan, su log y un contrato | Un agente en el que otros confían | listo |
| 3 | [Nadie duerme en el aeropuerto](https://kube.ar/es/agentic-mesh/project/ground-stop/nobody-sleeps-at-the-airport): un espacio de trabajo compartido | Agentes que trabajan juntos | listo |
| 4 | [Ni una dirección fija](https://kube.ar/es/agentic-mesh/project/ground-stop/find-dont-hardcode): registro, descubrimiento y trazas | Servicios compartidos | listo |
| 5 | [El hotel falso](https://kube.ar/es/agentic-mesh/project/ground-stop/the-fake-hotel): identidad, delegación y un punto de decisión | Seguridad y confianza | listo |
| 6 | [Cuarentena](https://kube.ar/es/agentic-mesh/project/ground-stop/quarantine): certificación, topes y cuarentena | Seguridad y confianza | listo |
| 7 | [La próxima tormenta](https://kube.ar/es/agentic-mesh/project/ground-stop/the-next-storm): fábrica, pipeline, retiro y el paquete final | Agentes a escala de empresa | listo |

Camino rápido: Python y SQLite, unas 3 a 4 horas por hito (unas 20 en total). Camino a fondo: las
mismas comprobaciones sobre la infraestructura que usaría una empresa (NATS, OPA, step-ca,
OpenTelemetry).

---

# Ground Stop

At 18:00 a storm closes Tocumen airport in Panama City, Fragata's connecting hub. Operations
cancels the night's departures in waves, and thousands of passengers in transit are stranded.
Eleven agents from five teams and two outside partners (Garoa Linhas Aéreas and Hoteles Ondelia)
have to rehouse every passenger by 06:00: a valid seat, a night under a roof, and a message with
their new flight. Nobody has ever made them work together.

You don't build those agents: they already exist and belong to other teams. You're the platform
team, and you build the mesh that connects them: a shared workspace, a registry and discovery,
traces that follow one request end to end, identity and permissions for every agent,
certification, quarantine, and a factory for new agents. It's the project for the
[Agentic Mesh](https://kube.ar/agentic-mesh) course.

## Getting started

Pick one of three ways. Each replays night `p1` with the mesh Fragata has today and prints the
scoreboard (in Spanish by default; add `--lang en` or set `GROUND_STOP_LANG=en`).

| With | Do |
|---|---|
| [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer | `uv sync`, then `uv run ground-stop --lang en replay` |
| Docker | `GROUND_STOP_LANG=en docker compose up` |
| GitHub Codespaces | *Code → Codespaces → Create codespace*: it installs itself and replays `p1` |

With today's naive mesh, half the passengers on `p1` are rehoused (490 of 982). The rest is the
scoreboard above: seats sold twice, messages lost, rooms at a hotel that doesn't exist, vouchers
nobody was entitled to. Each milestone replaces one part of the mesh, and the same scoreboard
shows what you fixed.

## Commands

| Command | Does |
|---|---|
| `ground-stop nights` | the nights in the repo: 3 practice, 6 standard, 3 final |
| `ground-stop show p1` | what happens on a night (practice nights tell you) |
| `ground-stop replay s2` | replay another night |
| `ground-stop replay p1 --mesh mine` | with your mesh (`src/groundstop/mine/mesh.py`) |
| `ground-stop trace PX-48187 --mesh mine` | one passenger's trace, through your tracer (milestone 4) |
| `ground-stop replay f1 --mesh mine --rebooking mine --entry-rules mine` | your whole platform, on a final night (milestone 7) |

Every `replay` leaves its logs in `runs/<night>/`: `traffic.log` (every message between agents,
and the ones that were lost), `systems.log` (every call to Fragata's systems), `agents/*.log`
(what each agent notes), `passengers.jsonl` (what happened to each passenger) and
`scoreboard.json`.

## How it's built

- **The night is a simulation**, in one process on a simulated clock. It's deterministic: the
  same night with the same mesh gives the same result, line for line. That's why the checks are
  exact and none needs a language model.
- **The agents are other teams' code** (`src/groundstop/agents/`). Read them; don't change them.
  They talk only through the SDK (`ctx.send`, `ctx.publish`, `ctx.call`, `ctx.find`,
  `ctx.claim`), and the SDK hands every request to the mesh.
- **The mesh is yours** (`src/groundstop/mesh/`): directory, transport, work claims, identity,
  access control and tracing. `naive.py` is today's. Each milestone replaces one part.
- **The company lives in `company/`**: which agents each team declares and which addresses each
  one has hardcoded, the partners, which system each agent may call, the compensation policy and
  the (fictional) entry rules.

Your code goes in `src/groundstop/mine/`, one file per milestone. `uv run ground-stop check 1` checks milestone 1;
`--reference` shows what passing looks like, and `use-reference 1` swaps your file for the reference (`--undo`
puts it back).

| # | Milestone | Course chapter | Status |
|---|---|---|---|
| 0 | [The storm](https://kube.ar/agentic-mesh/project/ground-stop/the-storm): the naive mesh and its scoreboard | Why an ecosystem | ready |
| 1 | [Count the agents](https://kube.ar/agentic-mesh/project/ground-stop/count-the-agents): the configs against the traffic | Why an ecosystem | ready |
| 2 | [A contract for rebooking](https://kube.ar/agentic-mesh/project/ground-stop/a-contract-for-rebooking): a plan, its log and a contract | One agent others can rely on | ready |
| 3 | [Nobody sleeps at the airport](https://kube.ar/agentic-mesh/project/ground-stop/nobody-sleeps-at-the-airport): a shared workspace | Agents working together | ready |
| 4 | [Find, don't hardcode](https://kube.ar/agentic-mesh/project/ground-stop/find-dont-hardcode): registry, discovery and traces | Shared services | ready |
| 5 | [The fake hotel](https://kube.ar/agentic-mesh/project/ground-stop/the-fake-hotel): identity, delegation and one decision point | Security and trust | ready |
| 6 | [Quarantine](https://kube.ar/agentic-mesh/project/ground-stop/quarantine): certification, caps and quarantine | Security and trust | ready |
| 7 | [The next storm](https://kube.ar/agentic-mesh/project/ground-stop/the-next-storm): factory, pipeline, retirement and the final pack | Agents at company scale | ready |

Fast path: Python and SQLite, about 3–4 hours per milestone (about 20 in all). Deep path: the same
checks on the infrastructure a company would run (NATS, OPA, step-ca, OpenTelemetry).

Fragata, Garoa Linhas Aéreas, Hoteles Ondelia and every passenger are fictional; passenger names
are random combinations of common first names and surnames. Tocumen, Panama City and the airports
are real places; nothing here describes a real airline, hotel or country's entry rules.
