# Database Model

## research_history.db (persistent)

```
┌─────────────────────────────────┐
│           research              │
├─────────────────────────────────┤
│ id              INTEGER PK      │
│ topic           VARCHAR(500)     │
│ focus_areas     JSON             │
│ agent_name      VARCHAR(100)     │
│ started_at      DATETIME         │
│ completed_at    DATETIME         │
│ processing_time FLOAT (seconds)  │
│ status          VARCHAR(20)      │  ← in_progress | completed | failed
│ executive_summary    TEXT        │
│ key_findings         JSON        │
│ detailed_analysis    TEXT        │
│ report_content       TEXT        │  ← full markdown report
│ report_path          VARCHAR(500)│  ← legacy, reports/ file path
│ total_queries        INTEGER     │
│ total_sources        INTEGER     │
│ error_message        TEXT        │
│ research_metadata    JSON        │
│ original_language    VARCHAR(10) │
│ research_language    VARCHAR(10) │
│ translation_enabled  BOOLEAN     │
│ translated_languages JSON        │
├─────────────────────────────────┤
│ 1 ──── N  queries               │
│ 1 ──── N  sources               │
│ 1 ──── N  translations          │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│           queries               │
├─────────────────────────────────┤
│ id              INTEGER PK      │
│ research_id     INTEGER FK      │ → research.id
│ query_text      VARCHAR(1000)    │
│ query_order     INTEGER          │  ← position in research sequence
│ executed_at     DATETIME         │
│ max_results     INTEGER          │
│ search_depth    VARCHAR(20)      │
│ include_answer  BOOLEAN          │
│ results_count   INTEGER          │
│ ai_answer       TEXT             │  ← Tavily's AI summary
│ follow_up_questions JSON         │
│ search_context  TEXT             │
│ execution_time  FLOAT (seconds)  │
│ success         BOOLEAN          │
│ error_message   TEXT             │
├─────────────────────────────────┤
│ 1 ──── N  sources               │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│           sources               │
├─────────────────────────────────┤
│ id              INTEGER PK      │
│ research_id     INTEGER FK      │ → research.id
│ query_id        INTEGER FK      │ → queries.id
│ title           VARCHAR(1000)    │
│ url             VARCHAR(2000)    │
│ content         TEXT             │  ← snippet from Tavily
│ relevance_score FLOAT            │
│ published_date  VARCHAR(20)      │
│ retrieved_at    DATETIME         │
│ content_length  INTEGER          │
│ domain          VARCHAR(200)     │  ← extracted from URL
│ used_in_analysis BOOLEAN         │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│         translations            │
├─────────────────────────────────┤
│ id              INTEGER PK      │
│ research_id     INTEGER FK      │ → research.id
│ source_text     TEXT             │
│ translated_text TEXT             │
│ source_language VARCHAR(10)      │
│ target_language VARCHAR(10)      │
│ content_type    VARCHAR(50)      │  ← topic | summary | analysis | finding
│ provider        VARCHAR(50)      │
│ confidence_score FLOAT           │
│ character_count INTEGER          │
│ processing_time FLOAT (seconds)  │
│ created_at      DATETIME         │
│ cache_hit       BOOLEAN          │
└─────────────────────────────────┘
```

## search_cache.db (ephemeral, TTL: 24h)

```
┌─────────────────────────────────┐
│        search_cache             │
├─────────────────────────────────┤
│ cache_key     TEXT PK            │  ← SHA-256(query + depth + max_results)
│ query_text    TEXT               │
│ search_depth  TEXT               │
│ max_results   INTEGER            │
│ response_json TEXT               │  ← full Tavily response as JSON
│ created_at    REAL (timestamp)   │
│ expires_at    REAL (timestamp)   │
│ hit_count     INTEGER            │
└─────────────────────────────────┘
```

## translation_cache.db (ephemeral, TTL: 24h)

```
┌─────────────────────────────────┐
│      translation_cache          │
├─────────────────────────────────┤
│ cache_key     TEXT PK            │  ← hash(text + source_lang + target_lang)
│ source_text   TEXT               │
│ translated    TEXT               │
│ source_lang   TEXT               │
│ target_lang   TEXT               │
│ provider      TEXT               │
│ created_at    REAL (timestamp)   │
│ expires_at    REAL (timestamp)   │
│ hit_count     INTEGER            │
└─────────────────────────────────┘
```

## Notes

- `research_history.db` is the core database — must be persisted (Fly.io volume)
- Cache DBs can be wiped anytime without data loss
- `reports/` folder currently duplicates `research.report_content` — to be consolidated in Phase 2
- All DB files currently in project root — to be moved to `data/` and `data/cache/` in Phase 2
