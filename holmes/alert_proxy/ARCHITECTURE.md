# Alert Proxy Architecture

## Component Responsibilities

### AlertManager
**Purpose**: Unified alert management - storage, tracking, and polling
**Responsibilities**:
- Store alerts by fingerprint
- Maintain display order
- Track which sources have seen which alerts (for deduplication)
- Discover AlertManager instances
- Poll them using AlertFetcher
- Provide both deduplicated (for standalone) and all alerts (for UI)
- NO UI concerns (selection, focus, etc)
- NO enrichment logic

### AlertFetcher
**Purpose**: Stateless alert fetching from AlertManager instances
**Responsibilities**:
- Fetch alerts from AlertManager API (v2)
- Handle both proxy and direct access
- Apply configuration filters (max_alerts, firing only, etc)
- Convert API responses to Alert models
- Validate alerts have fingerprints
- NO state management
- NO enrichment
- NO UI concerns


### AlertUIController
**Purpose**: Controller for interactive alert viewing
**Responsibilities**:
- Initialize and coordinate AlertManager, enricher
- Manage enrichment queue and workers
- Provide data to the view
- NO view state (selection, focus)
- NO direct storage (uses AlertManager)
- NO direct fetching (AlertManager handles that)

### AlertUIView
**Purpose**: View layer for interactive UI
**Responsibilities**:
- Display alerts, inspector, console
- Handle keyboard navigation
- Manage view state (selected_index, focused_pane)
- Search/filter UI
- NO data fetching
- NO business logic

### AlertEnricher
**Purpose**: Enrich alerts with AI analysis
**Responsibilities**:
- Call Holmes AI to investigate alerts
- Parse AI responses
- Update enrichment status
- NO state management
- NO UI concerns

### AlertWebhookServer
**Purpose**: HTTP server for webhook mode
**Responsibilities**:
- Receive AlertManager webhooks
- Trigger enrichment
- Forward to destinations
- NO polling logic
- NO UI concerns

### DestinationManager
**Purpose**: Forward alerts to external systems
**Responsibilities**:
- Send to Slack
- Forward to AlertManager
- Send to generic webhooks
- Format for different destinations
- NO enrichment logic
- NO UI concerns

## Data Flow

### Interactive Mode
```
AlertUIController
  -> AlertManager.poll_all(deduplicate=False)
    -> AlertFetcher (fetch all from API)
    -> Update storage
  -> AlertEnricher (enrich new alerts)
  -> AlertUIView (display)
```

### Webhook Mode
```
AlertWebhookServer (receive webhook)
  -> AlertEnricher (enrich)
  -> DestinationManager (forward)
```

## Key Design Principles

1. **No Fingerprint Generation**: AlertManager v2 always provides fingerprints - we validate but don't generate
2. **View Owns View State**: Selection, focus, etc are pure view concerns, not stored in model
3. **Single Source of Truth**: AlertManager is the only place alerts are stored
4. **Clear Separation**: Each component has one clear responsibility
5. **No Duplication**: AlertManager combines what was AlertManagerPoller + AlertRepository
6. **Stateless Fetching**: AlertFetcher has no state, just transforms API responses
