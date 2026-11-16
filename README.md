# Todos en tierra (Ground Stop)

*[English below](#ground-stop)*

A las 18:00 una tormenta cierra el aeropuerto de Tocumen, en Ciudad de Panamá, el centro de
conexiones de Fragata. Se cancelan los vuelos y miles de pasajeros en tránsito quedan varados.
Once agentes de cinco equipos y dos socios externos (Garoa Linhas Aéreas y Hoteles Ondelia)
tienen que reubicar a cada pasajero antes de las 06:00: un asiento, una habitación o atención en
el aeropuerto. Nunca nadie los hizo trabajar juntos.

No vas a construir esos agentes: ya existen y son de otros equipos. Eres el equipo de
plataforma, y construyes la malla que los conecta: un espacio de trabajo compartido, un registro
y un buscador de agentes, trazas que siguen una solicitud de punta a punta, identidad y permisos
para cada agente, certificación, cuarentena y una fábrica de agentes nuevos. Es el proyecto del
curso [Malla agéntica](https://kube.ar/es/agentic-mesh).

Cada noche se genera desde una semilla, así que la verdad siempre se conoce: qué asientos y
habitaciones había, qué podía pasarle a cada pasajero. Por eso las comprobaciones son exactas y
ninguna necesita un modelo de lenguaje.

> **Estado:** en construcción. Todavía no hay código; las instrucciones de cada hito se publicarán
> en el sitio, junto a las lecciones que usa.

## Hitos

| # | Hito | Capítulo del curso | Estado |
|---|---|---|---|
| 0 | La tormenta: la malla ingenua y su marcador | Por qué un ecosistema | planeado |
| 1 | Contar los agentes | Por qué un ecosistema | planeado |
| 2 | Un contrato para reprogramar | Un agente en el que otros confían | planeado |
| 3 | Nadie duerme en el aeropuerto | Agentes que trabajan juntos | planeado |
| 4 | Ni una dirección fija | Servicios compartidos | planeado |
| 5 | El hotel falso | Seguridad y confianza | planeado |
| 6 | Cuarentena | Seguridad y confianza | planeado |
| 7 | La próxima tormenta | Agentes a escala de empresa | planeado |

Camino rápido: Python y SQLite, unas 3 a 4 horas por hito (unas 20 en total). Camino a fondo: las
mismas comprobaciones sobre la infraestructura que usaría una empresa (NATS, OPA, step-ca,
OpenTelemetry).

---

# Ground Stop

At 18:00 a storm closes Tocumen airport in Panama City, Fragata's connecting hub. Flights are
cancelled and thousands of passengers in transit are stranded. Eleven agents from five teams and
two outside partners (Garoa Linhas Aéreas and Hoteles Ondelia) have to rehouse every passenger by
06:00: a seat, a room, or care at the airport. Nobody has ever made them work together.

You don't build those agents: they already exist and belong to other teams. You're the platform
team, and you build the mesh that connects them: a shared workspace, a registry and discovery,
traces that follow one request end to end, identity and permissions for every agent,
certification, quarantine, and a factory for new agents. It's the project for the
[Agentic Mesh](https://kube.ar/agentic-mesh) course.

Every night is generated from a seed, so the truth is always known: which seats and rooms there
were, what could happen to each passenger. That's what makes the checks exact, and none of them
needs a language model.

> **Status:** under construction. There's no code yet; each milestone's instructions will be
> published on the site, next to the lessons it uses.

| # | Milestone | Course chapter | Status |
|---|---|---|---|
| 0 | The storm: the naive mesh and its scoreboard | Why an ecosystem | planned |
| 1 | Count the agents | Why an ecosystem | planned |
| 2 | A contract for rebooking | One agent others can rely on | planned |
| 3 | Nobody sleeps at the airport | Agents working together | planned |
| 4 | Find, don't hardcode | Shared services | planned |
| 5 | The fake hotel | Security and trust | planned |
| 6 | Quarantine | Security and trust | planned |
| 7 | The next storm | Agents at company scale | planned |

Fast path: Python and SQLite, about 3–4 hours per milestone (about 20 in all). Deep path: the same
checks on the infrastructure a company would run (NATS, OPA, step-ca, OpenTelemetry).

Fragata, Garoa Linhas Aéreas, Hoteles Ondelia and every passenger are fictional. Tocumen and
Panama City are real places; nothing here describes a real airline.
