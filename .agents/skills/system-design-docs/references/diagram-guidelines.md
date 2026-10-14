# Mermaid Diagram Authoring & Validation Guidelines

To guarantee that all generated Mermaid diagrams render flawlessly across Markdown viewers and documentation engines without parser errors, layout clipping, or illegibility, follow these strict syntax and structural rules.

---

## 1. Absolute Prohibition on ASCII & Text-Box Drawings (100% Mermaid Rule)

> ⚠️ **Zero Tolerance for ASCII Art:**  
> Never output ASCII box drawings (`┌───┐`, `+---+`, `| ... |`, `[A] ──▶ [B]`, `+===+`) in architectural documentation.  
> Every structural hierarchy, state lifecycle, event pipeline, data flow, container relationship, and network topology **MUST** be authored as a native Mermaid diagram block (` ```mermaid `).

| Concept to Visualize                      | Mandatory Mermaid Diagram Type      | Layout Direction                                  |
| :---------------------------------------- | :---------------------------------- | :------------------------------------------------ |
| **System Context & Containers (C4)**      | `flowchart TB` / `flowchart TD`     | Top-to-bottom with `direction TB` in subgraphs    |
| **Screen & Route Navigation Hierarchies** | `flowchart TB` / `stateDiagram-v2`  | Top-to-bottom                                     |
| **Component Layout Trees**                | `flowchart TB`                      | Nested subgraphs with `direction TB`              |
| **State Store Schemas & Interfaces**      | `classDiagram`                      | Top-to-bottom (`direction TB`)                    |
| **Asynchronous API & Auth Sequences**     | `sequenceDiagram`                   | Sequential with `autonumber` (max 6 participants) |
| **Sensor & Kinematic Event Pipelines**    | `sequenceDiagram` or `flowchart TB` | Sequential or directional pipeline                |
| **State Lifecycles & Playback Machines**  | `stateDiagram-v2`                   | CamelCase state identifiers                       |
| **Test Pyramids & Layer Topologies**      | `flowchart TB`                      | Stacked subgraphs                                 |

---

## 2. Direction & Viewport Width Sizing Constraints

### 2.1 Top-to-Bottom Layouts (`flowchart TB` / `flowchart TD`):

- **Default Flow Direction:** Always use `flowchart TB` or `flowchart TD` for C4 Context, Container, Component, and Topology diagrams. Avoid `LR` (left-to-right) for broad system graphs, as horizontal layouts exceed typical markdown viewport widths and require horizontal scrolling.
- **Nested Subgraph Direction:** Declare `direction TB` inside multi-node subgraphs to stack internal components vertically.

### 2.2 Sequence Diagram Constraints:

- Declare all participants explicitly at the top of the diagram using `participant` or `actor` before messages.
- Limit participants to **$\le 6$ participants** per sequence diagram. Group or collapse intermediate sub-steps to preserve readability.
- Always include `autonumber` for step-by-step traceability.

---

## 3. Safe Label Syntax & Character Escaping

### 3.1 Quotes Around Special Characters:

- **Always wrap node labels containing spaces, parentheses, slashes, colons, brackets, or braces in double quotes:**
  ```mermaid
  flowchart TB
      User["Commuter (Mobile User)"] --> App["Trenord App (React Native / Expo)"]
      App --> Proxy["API Proxy (/api/proxy)"]
      Proxy --> Cloud["Trenord Cloud API (B2B Backend)"]
  ```

### 3.2 Reserved Words & Generics:

- **Never use unescaped `<` or `>` inside node labels or class diagrams.**
  - Use `~T~` for generics (e.g. `Promise~void~`, `Array~string~`, `Record~string, POIDetail~`).
  - Use HTML entities (`&lt;` / `&gt;`) if mathematical comparison operators are required in node text.
- **Avoid reserved keyword collisions:** Do not use `end`, `subgraph`, `state`, `class`, `default`, `style`, or `direction` as standalone node IDs.

---

## 4. Class Diagram Guidelines (`classDiagram`)

- Define clear visibility modifiers (`+` for public, `-` for private, `#` for protected).
- Keep method parameter lists succinct and use `~T~` for return generics:
  ```mermaid
  classDiagram
      direction TB
      class JourneyStore {
          +string? trainId
          +Station? destinationStation
          +TrainInfoResponse? trainData
          +number? lastUpdated
          +setJourney(trainId, dest, data) void
          +clearJourney() void
      }
      class AudioStore {
          +AudioEpisode? episode
          +boolean isPlaying
          +number position
          +playEpisode(episode, initialPos) Promise~void~
          +closePlayer() Promise~void~
      }
      JourneyStore ..> AudioStore : cleans up media on session exit
  ```

---

## 5. State Diagram Guidelines (`stateDiagram-v2`)

- Always use `stateDiagram-v2` (modern renderer).
- State names must use CamelCase identifiers without spaces (e.g. `HomeDashboard`, `LockedState`, `IncidentReporting`).
- Transitions must follow the pattern `SourceState --> TargetState : Event / Condition`.

---

## 6. Pre-Synthesis Diagram Validation Checklist

Before writing any Mermaid block into documentation modules, verify:

1. [ ] **Zero ASCII Art:** No ASCII box drawings (`┌`, `┐`, `└`, `┘`, `│`, `─`, `+---`, `+===`) exist in the output.
2. [ ] **Flowchart Direction:** All flowcharts use `flowchart TB` or `flowchart TD` with `direction TB` in subgraphs.
3. [ ] **Escaped Labels:** All node labels with spaces or punctuation (`/`, `(`, `)`, `[`, `]`, `:`) are enclosed in double quotes `["..."]`.
4. [ ] **Unique Subgraphs:** All subgraphs have unique alphanumeric IDs and explicit bracketed titles: `subgraph ID ["Title"]`.
5. [ ] **Safe Generics:** No raw `<` or `>` are present in labels (use `&lt;` / `&gt;` or `~T~` for generics).
6. [ ] **Sequence Participants:** In sequence diagrams, every `participant` / `actor` is declared before use (max 6 participants, `autonumber` enabled).
7. [ ] **State Identifiers:** In state diagrams, state identifiers do not contain spaces.
