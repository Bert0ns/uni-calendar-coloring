# Modular System Design Architecture Blueprint

This document defines the mandatory structure, section contents, and naming standards for the **Modular Architecture Documentation** inside `docs/architecture/`.

---

## Modular File Topology & Responsibility Matrix

```text
docs/architecture/
├── index.md                              # Module 0: Executive Summary, System Mission, Functional/NFR Catalogs & Map
├── 01-c4-context-and-containers.md        # Module 1: C4 Level 1 (System Context) & C4 Level 2 (Containers & Topology)
├── 02-screens-and-navigation.md           # Module 2: Screen Catalog, Layout Specs, Route Topology & Navigation State Machine
├── 03-state-management-and-domain.md      # Module 3: Zustand Store Inventory, UML Class Diagram, Lifecycles & Reactive Hooks
├── 04-sensors-kinematics-and-native.md    # Module 4: Accelerometer Math, Shake Gesture, GPS Telemetry, Audio State Machine
├── 05-apis-networking-and-proxy.md        # Module 5: API Catalog, OAuth JWT Sequence, Web Proxy Gateway, Smart Polling
├── 06-cross-cutting-concerns.md           # Module 6: Telemetry Logging, Security Architecture, Internationalization (i18n)
├── 07-solid-principles-and-patterns.md    # Module 7: Concrete SOLID Principles Compliance Matrix with Line-Cited Proofs
├── 08-testing-and-cicd.md                 # Module 8: Test Pyramid (90 Suites / 436 Tests), Native Mocks, CI/CD Pipelines
└── 09-appendix-technical-debt.md          # Module 9: Architectural Gaps & Technical Debt Remediation Matrix
```

---

## Module Specifications & Structural Standards

### `index.md` — Executive Summary & System Requirements

- **Breadcrumb / Header:** System Name, Target Platforms, Core Tech Stack.
- **Executive Summary & High-Level System Flow (Mermaid `flowchart TB`):** Passenger -> Presentation -> State -> Integration -> Native/Hardware.
- **System Mission & Core Value Propositions:** 6 architectural pillars.
- **Exhaustive Functional Requirements Catalog (FR-01 to FR-25+ Table):**
  - Columns: `Req ID | Domain / Capability | Description & Business Rules | Applicable Code Modules & Stores | Verification Method`
  - Domains: Authentication, Telemetry, Polling, Journey Mapping, Media/Audio, Weather, News, Incident Reporting, Kinematics, Settings & i18n.
- **Comprehensive Non-Functional Requirements Matrix (NFR-01 to NFR-10 Table):**
  - Columns: `NFR ID | Category | Target Threshold / Metric | Implementation Mechanism | Validation Proof`
  - Categories: UI Fluidity (60fps), Startup Latency, Cryptographic Security, Offline Resilience, Battery Efficiency, Static Typing, Test Reliability.
- **Documentation Navigation Index:** Linked table of contents to all 9 child modules.

---

### `01-c4-context-and-containers.md` — C4 Context & Containers

- **C4 Level 1: System Context Diagram (Mermaid `flowchart TB`):**
  - Commuters, Mobile App Container, Web Proxy Gateway, Upstream IDP, Cloud Transport APIs, Open-Meteo, CurrentsAPI, Media CDNs, Places APIs.
- **C4 Level 2: Container & Topology Diagram (Mermaid `flowchart TB`):**
  - Presentation Layer (Screens, Modals, Shared Primitives).
  - State & Application Layer (Zustand Stores, Selectors, Custom Hooks).
  - Service & Integration Layer (API Gateways, Auth Assertion, Logging, i18n).
  - Native Platform & Storage Layer (Expo Sensors, Location, Audio, Notifications, AsyncStorage).

---

### `02-screens-and-navigation.md` — Screens & Navigation Architecture

- **Root Routing & Presentation Topology (Mermaid `flowchart TB`):**
  - Root Stack, persistent Bottom Tabs Layout, gesture-driven SlideSheets, fullscreen media stacks.
- **Screen Catalog Matrix:** URI, Presentation Style, Primary Intent, Key Child Components, Store Bindings.
- **Screen-by-Screen Architectural Breakdown:** Detailed breakdown for all 13 routes.
- **End-to-End Navigation State Diagram (Mermaid `flowchart TB`):** Complete user navigation lifecycle.

---

### `03-state-management-and-domain.md` — State Management & Domain Logic

- **State Architecture Overview (Mermaid `flowchart TB`):** View Components -> Selectors/Hooks -> Zustand Stores -> AsyncStorage.
- **State Store Inventory Table:** 10 Zustand stores with storage keys, managed properties, mutation actions, and side effects.
- **State Store Class Diagram (Mermaid `classDiagram`):** UML representation with generics (`~T~`).
- **State Lifecycle & Hydration Flow (Mermaid `flowchart TB`):**
  - Bootstrap rehydration & auth guard routing flow.
  - Journey login & metadata resolution sequence.
  - Audio event bridge & throttled persistence loop.
- **Reactive Hooks Matrix:** Custom hooks bridging stores with views.

---

### `04-sensors-kinematics-and-native.md` — Hardware Sensors & Real-Time Engines

- **Hardware & Sensor Specification Matrix:** Native driver, polling rates, filter thresholds, required permissions.
- **Kinematics & Inertial Algorithms (with Mathematical Derivations & Mermaid `flowchart TB` vector flows):**
  - Anti-motion sickness particle engine ($\alpha = 0.8$, magnitude gates, toroidal wrapping).
  - Shake detection formula ($M > 2.2\text{G}, \Delta > 1.2\text{G}, 1500\text{ms}$ cooldown).
  - GPS speedometer (Haversine, EMA smoothing $\alpha = 0.35$, timetable dead-reckoning fallback).
- **Sensor Event Pipeline Sequence Diagram (Mermaid `sequenceDiagram`):** Raw sensor -> filter -> threshold -> modal presentation.
- **Media Playback & Scrubber State Machine (Mermaid `stateDiagram-v2`):** Player lifecycle, MediaSession, scrubber synchronization.
- **Notification Concurrency & QR Scanning Pipelines (Mermaid `flowchart TB`).**

---

### `05-apis-networking-and-proxy.md` — External APIs, Web Proxy & Sequence Flows

- **Network Layer Topology Diagram (Mermaid `flowchart TB`):** Client -> Service Clients -> Web Edge Proxy -> Upstream Providers.
- **API Integration Catalog:** 8 upstream service providers.
- **Web Proxy Security Gateway Diagram (Mermaid `flowchart TB`):** Protocol assertion and SSRF hostname allowlists.
- **Cryptographic Authentication Sequence Diagram (Mermaid `sequenceDiagram`):** RFC 7523 OAuth 2.0 Private Key JWT flow.
- **Smart Polling & Offline Fallback Sequence Diagram (Mermaid `sequenceDiagram`):** Adaptive intervals and cache fallback.

---

### `06-cross-cutting-concerns.md` — Cross-Cutting Concerns

- **Telemetry & Logging Infrastructure (Mermaid `flowchart TB`):** Scoped `react-native-logs` configuration, log levels, and subsystem loggers.
- **Security & Privacy Architecture (Mermaid `sequenceDiagram`):** Private key isolation, token encryption, HTTPS transport security.
- **Internationalization (i18n):** Namespace trees and municipality transliteration mapping.

---

### `07-solid-principles-and-patterns.md` — SOLID Principles Compliance Matrix

- **Detailed SOLID Compliance Matrix:** 2+ verified file and code symbol proofs for each of S, O, L, I, D.

---

### `08-testing-and-cicd.md` — Verification, Testing & CI/CD Pipelines

- **Test Framework Overview & Test Pyramid (Mermaid `flowchart TB`):** 90 suites / 436 tests passing.
- **Mocking Architecture (`jest.setup.js`):** Reanimated, `MockAudioPlayer`, Notifications, Router, real i18n JSON loader.
- **CI/CD Quality Gates & Release Pipelines (Mermaid `flowchart LR`).**

---

### `09-appendix-technical-debt.md` — Architectural Gaps & Technical Debt

- **Comprehensive Technical Debt Matrix:** Severity, subsystem, operational impact, remediation blueprint.
- **Incremental Remediation Roadmap (Mermaid `flowchart TB`):** Milestone 1, Milestone 2, Milestone 3.
