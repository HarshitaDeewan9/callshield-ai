# CallShield architecture handoff pack

Start with **CallShield_Architecture_and_Technical_Diagrams.pdf**. It contains eight landscape diagrams checked against the current Python implementation (20 October 2026).

| Diagram | PNG for chat/slides | Editable vector |
|---|---|---|
| 1. System context and ownership | [PNG](01-system-context.png) | [SVG](01-system-context.svg) |
| 2. Python components and adapters | [PNG](02-components.png) | [SVG](02-components.svg) |
| 3. Text analysis sequence | [PNG](03-text-sequence.png) | [SVG](03-text-sequence.svg) |
| 4. Audio upload pipeline | [PNG](04-audio-flow.png) | [SVG](04-audio-flow.svg) |
| 5. Warning audio and caching | [PNG](05-warning-flow.png) | [SVG](05-warning-flow.svg) |
| 6. Mock and real provider selection | [PNG](06-provider-modes.png) | [SVG](06-provider-modes.svg) |
| 7. Deployment and security | [PNG](07-deployment.png) | [SVG](07-deployment.svg) |
| 8. Result lifecycle and API contract | [PNG](08-state-and-contract.png) | [SVG](08-state-and-contract.svg) |

**Editable conceptual diagrams:** [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md), containing eight Mermaid blocks, implementation notes and source-file mappings.

**API integration reference:** [SPRING_BOOT_HANDOFF.md](SPRING_BOOT_HANDOFF.md), copied from the repository for convenient sharing.

The visual source is `scripts/generate_architecture_diagrams.py` in the repository. It requires ReportLab only for diagram authoring; no new service dependencies or application changes were introduced. Rebuild instructions are in the Mermaid document. The PDF and SVGs are vector outputs; the PNGs are 1600 x 1000 pixels each.

React/Spring are separate teammate projects, and the deployment diagram is a recommendation. The pack does not claim a live EC2 deployment or successful paid-provider calls. In-memory storage, single-worker operation, mock test tones and provider failure behavior are shown explicitly.
