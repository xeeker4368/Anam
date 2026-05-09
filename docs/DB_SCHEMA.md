# Database Schema

Generated: 2026-05-09T22:48:57.818791+00:00

## Overview

### working.db

Mutable operational/control-plane database.

### archive.db

Durable minimal archive / ground truth database.

### Chroma

Vector index storage. Chroma is not fully documented as SQLite schema here.

## Schema Ownership Notes

- `working.db` owns mutable operational state.
- `archive.db` owns minimal durable conversation/message/user archive.
- Chroma owns vector retrieval indexes.
- Governance files are files, not DB tables.
- `artifacts` primary key is `artifact_id`, not `id`.
- `metadata_json` stores extensible metadata.
- `behavioral_guidance_proposals` lives in `working.db`.
- `review_items`, `open_loops`, artifacts, and journals live in `working.db`.
- Journal artifacts use `artifact_type=journal` and `metadata_json.source_type=journal`.
- `schema_versions` exists only in `working.db`.
- `BEHAVIORAL_GUIDANCE.md` is a governance file, not a database table.
- `archive.db` remains minimal and frozen-scope.

## working.db

### Schema Versions

| Version | Name | Applied At |
| --- | --- | --- |
| 1 | `baseline_current_schema` | 2026-05-08T20:59:26.729248+00:00 |

### Tables

#### `artifacts`

Type: table

Purpose: Workspace artifact registry. Primary key is artifact_id, not id.

Primary key: `artifact_id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| artifact_id | TEXT | no |  | 1 |
| artifact_type | TEXT | yes |  |  |
| title | TEXT | yes |  |  |
| description | TEXT | no |  |  |
| path | TEXT | no |  |  |
| status | TEXT | yes | `'draft'` |  |
| created_at | TEXT | yes |  |  |
| updated_at | TEXT | yes |  |  |
| source | TEXT | no |  |  |
| source_conversation_id | TEXT | no |  |  |
| source_message_id | TEXT | no |  |  |
| source_tool_name | TEXT | no |  |  |
| revision_of | TEXT | no |  |  |
| metadata_json | TEXT | no |  |  |

**Indexes**
- `idx_artifacts_created_at` (non-unique, origin=c): created_at
- `idx_artifacts_path` (non-unique, origin=c): path
- `idx_artifacts_revision_of` (non-unique, origin=c): revision_of
- `idx_artifacts_status` (non-unique, origin=c): status
- `idx_artifacts_type` (non-unique, origin=c): artifact_type
- `sqlite_autoindex_artifacts_1` (unique, origin=pk): artifact_id

**Foreign Keys**
- `revision_of` -> `artifacts`.`artifact_id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE artifacts (
            artifact_id TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            path TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            revision_of TEXT,
            metadata_json TEXT,
            FOREIGN KEY (revision_of) REFERENCES artifacts(artifact_id)
        )
```

</details>

#### `behavioral_guidance_proposals`

Type: table

Purpose: AI-proposed behavioral guidance candidates for admin review.

Primary key: `proposal_id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| proposal_id | TEXT | no |  | 1 |
| proposal_type | TEXT | yes |  |  |
| proposal_text | TEXT | yes |  |  |
| target_existing_guidance_id | TEXT | no |  |  |
| target_text | TEXT | no |  |  |
| rationale | TEXT | yes |  |  |
| source_experience_summary | TEXT | no |  |  |
| source_user_id | TEXT | no |  |  |
| source_conversation_id | TEXT | no |  |  |
| source_message_id | TEXT | no |  |  |
| source_channel | TEXT | yes | `'unknown'` |  |
| risk_if_added | TEXT | no |  |  |
| risk_if_not_added | TEXT | no |  |  |
| status | TEXT | yes | `'proposed'` |  |
| reviewed_by_user_id | TEXT | no |  |  |
| reviewed_by_role | TEXT | no |  |  |
| review_decision_reason | TEXT | no |  |  |
| created_at | TEXT | yes |  |  |
| updated_at | TEXT | yes |  |  |
| reviewed_at | TEXT | no |  |  |
| applied_by_user_id | TEXT | no |  |  |
| applied_at | TEXT | no |  |  |
| apply_note | TEXT | no |  |  |
| metadata_json | TEXT | no |  |  |

**Indexes**
- `idx_behavioral_guidance_proposals_conversation` (non-unique, origin=c): source_conversation_id
- `idx_behavioral_guidance_proposals_created_at` (non-unique, origin=c): created_at
- `idx_behavioral_guidance_proposals_source_user` (non-unique, origin=c): source_user_id
- `idx_behavioral_guidance_proposals_status` (non-unique, origin=c): status
- `idx_behavioral_guidance_proposals_type` (non-unique, origin=c): proposal_type
- `sqlite_autoindex_behavioral_guidance_proposals_1` (unique, origin=pk): proposal_id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE behavioral_guidance_proposals (
            proposal_id TEXT PRIMARY KEY,
            proposal_type TEXT NOT NULL,
            proposal_text TEXT NOT NULL,
            target_existing_guidance_id TEXT,
            target_text TEXT,
            rationale TEXT NOT NULL,
            source_experience_summary TEXT,
            source_user_id TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_channel TEXT NOT NULL DEFAULT 'unknown',
            risk_if_added TEXT,
            risk_if_not_added TEXT,
            status TEXT NOT NULL DEFAULT 'proposed',
            reviewed_by_user_id TEXT,
            reviewed_by_role TEXT,
            review_decision_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            reviewed_at TEXT,
            applied_by_user_id TEXT,
            applied_at TEXT,
            apply_note TEXT,
            metadata_json TEXT
        )
```

</details>

#### `channel_identifiers`

Type: table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| user_id | TEXT | yes |  |  |
| channel | TEXT | yes |  |  |
| identifier | TEXT | yes |  |  |
| auth_material | TEXT | no |  |  |
| verified | INTEGER | no | `0` |  |
| created_at | TEXT | yes |  |  |

**Indexes**
- `idx_channel_identifiers_lookup` (non-unique, origin=c): channel, identifier
- `idx_channel_identifiers_user` (non-unique, origin=c): user_id
- `sqlite_autoindex_channel_identifiers_1` (unique, origin=pk): id
- `sqlite_autoindex_channel_identifiers_2` (unique, origin=u): channel, identifier

**Foreign Keys**
- `user_id` -> `users`.`id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE channel_identifiers (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            identifier TEXT NOT NULL,
            auth_material TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (channel, identifier)
        )
```

</details>

#### `chunks_fts`

Type: virtual table

Purpose: FTS5 lexical retrieval index for memory chunks.

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| chunk_id |  | no |  |  |
| text |  | no |  |  |
| conversation_id |  | no |  |  |
| user_id |  | no |  |  |
| source_type |  | no |  |  |
| source_trust |  | no |  |  |
| created_at |  | no |  |  |

**Indexes**
- None

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id UNINDEXED,
                text,
                conversation_id UNINDEXED,
                user_id UNINDEXED,
                source_type UNINDEXED,
                source_trust UNINDEXED,
                created_at UNINDEXED,
                tokenize = 'unicode61 remove_diacritics 2'
            )
```

</details>

#### `chunks_fts_config`

Type: FTS shadow table

Primary key: `k`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| k |  | yes |  | 1 |
| v |  | no |  |  |

**Indexes**
- `sqlite_autoindex_chunks_fts_config_1` (unique, origin=pk): k

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE 'chunks_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID
```

</details>

#### `chunks_fts_content`

Type: FTS shadow table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | INTEGER | no |  | 1 |
| c0 |  | no |  |  |
| c1 |  | no |  |  |
| c2 |  | no |  |  |
| c3 |  | no |  |  |
| c4 |  | no |  |  |
| c5 |  | no |  |  |
| c6 |  | no |  |  |

**Indexes**
- None

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE 'chunks_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3, c4, c5, c6)
```

</details>

#### `chunks_fts_data`

Type: FTS shadow table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | INTEGER | no |  | 1 |
| block | BLOB | no |  |  |

**Indexes**
- None

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE 'chunks_fts_data'(id INTEGER PRIMARY KEY, block BLOB)
```

</details>

#### `chunks_fts_docsize`

Type: FTS shadow table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | INTEGER | no |  | 1 |
| sz | BLOB | no |  |  |

**Indexes**
- None

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE 'chunks_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB)
```

</details>

#### `chunks_fts_idx`

Type: FTS shadow table

Primary key: `segid, term`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| segid |  | yes |  | 1 |
| term |  | yes |  | 2 |
| pgno |  | no |  |  |

**Indexes**
- `sqlite_autoindex_chunks_fts_idx_1` (unique, origin=pk): segid, term

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE 'chunks_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID
```

</details>

#### `conversations`

Type: table

Purpose: Mutable chat conversation metadata.

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| user_id | TEXT | yes |  |  |
| started_at | TEXT | yes |  |  |
| ended_at | TEXT | no |  |  |
| message_count | INTEGER | no | `0` |  |
| chunked | INTEGER | no | `0` |  |
| consolidated | INTEGER | no | `0` |  |

**Indexes**
- `idx_conversations_ended` (non-unique, origin=c): ended_at
- `idx_conversations_started` (non-unique, origin=c): started_at
- `idx_conversations_user` (non-unique, origin=c): user_id
- `sqlite_autoindex_conversations_1` (unique, origin=pk): id

**Foreign Keys**
- `user_id` -> `users`.`id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            message_count INTEGER DEFAULT 0,
            chunked INTEGER DEFAULT 0,
            consolidated INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
```

</details>

#### `diagnostic_issues`

Type: table

Primary key: `diagnostic_id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| diagnostic_id | TEXT | no |  | 1 |
| title | TEXT | yes |  |  |
| description | TEXT | no |  |  |
| category | TEXT | yes | `'generic'` |  |
| status | TEXT | yes | `'open'` |  |
| severity | TEXT | yes | `'medium'` |  |
| evidence_summary | TEXT | yes |  |  |
| suspected_component | TEXT | no |  |  |
| related_feedback_id | TEXT | no |  |  |
| related_open_loop_id | TEXT | no |  |  |
| related_artifact_id | TEXT | no |  |  |
| source | TEXT | no |  |  |
| source_conversation_id | TEXT | no |  |  |
| source_message_id | TEXT | no |  |  |
| source_tool_name | TEXT | no |  |  |
| target_type | TEXT | no |  |  |
| target_id | TEXT | no |  |  |
| next_action | TEXT | no |  |  |
| created_at | TEXT | yes |  |  |
| updated_at | TEXT | yes |  |  |
| resolved_at | TEXT | no |  |  |
| metadata_json | TEXT | no |  |  |

**Indexes**
- `idx_diagnostic_issues_artifact` (non-unique, origin=c): related_artifact_id
- `idx_diagnostic_issues_category` (non-unique, origin=c): category
- `idx_diagnostic_issues_conversation` (non-unique, origin=c): source_conversation_id
- `idx_diagnostic_issues_created_at` (non-unique, origin=c): created_at
- `idx_diagnostic_issues_feedback` (non-unique, origin=c): related_feedback_id
- `idx_diagnostic_issues_open_loop` (non-unique, origin=c): related_open_loop_id
- `idx_diagnostic_issues_severity` (non-unique, origin=c): severity
- `idx_diagnostic_issues_status` (non-unique, origin=c): status
- `idx_diagnostic_issues_target` (non-unique, origin=c): target_type, target_id
- `sqlite_autoindex_diagnostic_issues_1` (unique, origin=pk): diagnostic_id

**Foreign Keys**
- `related_artifact_id` -> `artifacts`.`artifact_id` on_update=NO ACTION on_delete=NO ACTION
- `related_open_loop_id` -> `open_loops`.`open_loop_id` on_update=NO ACTION on_delete=NO ACTION
- `related_feedback_id` -> `feedback_records`.`feedback_id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE diagnostic_issues (
            diagnostic_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'generic',
            status TEXT NOT NULL DEFAULT 'open',
            severity TEXT NOT NULL DEFAULT 'medium',
            evidence_summary TEXT NOT NULL,
            suspected_component TEXT,
            related_feedback_id TEXT,
            related_open_loop_id TEXT,
            related_artifact_id TEXT,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            target_type TEXT,
            target_id TEXT,
            next_action TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY (related_feedback_id) REFERENCES feedback_records(feedback_id),
            FOREIGN KEY (related_open_loop_id) REFERENCES open_loops(open_loop_id),
            FOREIGN KEY (related_artifact_id) REFERENCES artifacts(artifact_id)
        )
```

</details>

#### `documents`

Type: table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| title | TEXT | yes |  |  |
| url | TEXT | no |  |  |
| source_type | TEXT | yes | `'article'` |  |
| source_trust | TEXT | yes | `'thirdhand'` |  |
| chunk_count | INTEGER | no | `0` |  |
| summarized | INTEGER | no | `0` |  |
| summary | TEXT | no |  |  |
| created_at | TEXT | yes |  |  |

**Indexes**
- `sqlite_autoindex_documents_1` (unique, origin=pk): id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT,
            source_type TEXT NOT NULL DEFAULT 'article',
            source_trust TEXT NOT NULL DEFAULT 'thirdhand',
            chunk_count INTEGER DEFAULT 0,
            summarized INTEGER DEFAULT 0,
            summary TEXT,
            created_at TEXT NOT NULL
        )
```

</details>

#### `feedback_records`

Type: table

Primary key: `feedback_id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| feedback_id | TEXT | no |  | 1 |
| feedback_type | TEXT | yes |  |  |
| status | TEXT | yes | `'open'` |  |
| title | TEXT | yes |  |  |
| description | TEXT | no |  |  |
| user_feedback | TEXT | yes |  |  |
| target_type | TEXT | no |  |  |
| target_id | TEXT | no |  |  |
| source | TEXT | no |  |  |
| source_conversation_id | TEXT | no |  |  |
| source_message_id | TEXT | no |  |  |
| source_tool_name | TEXT | no |  |  |
| related_artifact_id | TEXT | no |  |  |
| related_open_loop_id | TEXT | no |  |  |
| created_at | TEXT | yes |  |  |
| updated_at | TEXT | yes |  |  |
| resolved_at | TEXT | no |  |  |
| metadata_json | TEXT | no |  |  |

**Indexes**
- `idx_feedback_records_artifact` (non-unique, origin=c): related_artifact_id
- `idx_feedback_records_conversation` (non-unique, origin=c): source_conversation_id
- `idx_feedback_records_created_at` (non-unique, origin=c): created_at
- `idx_feedback_records_open_loop` (non-unique, origin=c): related_open_loop_id
- `idx_feedback_records_status` (non-unique, origin=c): status
- `idx_feedback_records_target` (non-unique, origin=c): target_type, target_id
- `idx_feedback_records_type` (non-unique, origin=c): feedback_type
- `sqlite_autoindex_feedback_records_1` (unique, origin=pk): feedback_id

**Foreign Keys**
- `related_open_loop_id` -> `open_loops`.`open_loop_id` on_update=NO ACTION on_delete=NO ACTION
- `related_artifact_id` -> `artifacts`.`artifact_id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE feedback_records (
            feedback_id TEXT PRIMARY KEY,
            feedback_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            title TEXT NOT NULL,
            description TEXT,
            user_feedback TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            related_artifact_id TEXT,
            related_open_loop_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY (related_artifact_id) REFERENCES artifacts(artifact_id),
            FOREIGN KEY (related_open_loop_id) REFERENCES open_loops(open_loop_id)
        )
```

</details>

#### `messages`

Type: table

Purpose: Conversation messages and optional tool trace JSON.

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| conversation_id | TEXT | yes |  |  |
| role | TEXT | yes |  |  |
| content | TEXT | yes |  |  |
| tool_trace | TEXT | no |  |  |
| timestamp | TEXT | yes |  |  |

**Indexes**
- `idx_working_conversation` (non-unique, origin=c): conversation_id
- `idx_working_timestamp` (non-unique, origin=c): timestamp
- `sqlite_autoindex_messages_1` (unique, origin=pk): id

**Foreign Keys**
- `conversation_id` -> `conversations`.`id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_trace TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
```

</details>

#### `open_loops`

Type: table

Purpose: Unresolved follow-ups and unfinished threads.

Primary key: `open_loop_id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| open_loop_id | TEXT | no |  | 1 |
| title | TEXT | yes |  |  |
| description | TEXT | no |  |  |
| status | TEXT | yes | `'open'` |  |
| loop_type | TEXT | yes | `'generic'` |  |
| priority | TEXT | yes | `'normal'` |  |
| related_artifact_id | TEXT | no |  |  |
| source | TEXT | no |  |  |
| source_conversation_id | TEXT | no |  |  |
| source_message_id | TEXT | no |  |  |
| source_tool_name | TEXT | no |  |  |
| next_action | TEXT | no |  |  |
| created_at | TEXT | yes |  |  |
| updated_at | TEXT | yes |  |  |
| closed_at | TEXT | no |  |  |
| metadata_json | TEXT | no |  |  |

**Indexes**
- `idx_open_loops_artifact` (non-unique, origin=c): related_artifact_id
- `idx_open_loops_conversation` (non-unique, origin=c): source_conversation_id
- `idx_open_loops_created_at` (non-unique, origin=c): created_at
- `idx_open_loops_priority` (non-unique, origin=c): priority
- `idx_open_loops_status` (non-unique, origin=c): status
- `idx_open_loops_type` (non-unique, origin=c): loop_type
- `sqlite_autoindex_open_loops_1` (unique, origin=pk): open_loop_id

**Foreign Keys**
- `related_artifact_id` -> `artifacts`.`artifact_id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE open_loops (
            open_loop_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            loop_type TEXT NOT NULL DEFAULT 'generic',
            priority TEXT NOT NULL DEFAULT 'normal',
            related_artifact_id TEXT,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            next_action TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY (related_artifact_id) REFERENCES artifacts(artifact_id)
        )
```

</details>

#### `overnight_runs`

Type: table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| started_at | TEXT | yes |  |  |
| ended_at | TEXT | no |  |  |
| duration_seconds | REAL | no |  |  |
| conversations_closed | INTEGER | no | `0` |  |
| summary | TEXT | no |  |  |

**Indexes**
- `sqlite_autoindex_overnight_runs_1` (unique, origin=pk): id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE overnight_runs (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_seconds REAL,
            conversations_closed INTEGER DEFAULT 0,
            summary TEXT
        )
```

</details>

#### `review_items`

Type: table

Purpose: Operator review queue items.

Primary key: `item_id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| item_id | TEXT | no |  | 1 |
| title | TEXT | yes |  |  |
| description | TEXT | no |  |  |
| category | TEXT | yes | `'other'` |  |
| status | TEXT | yes | `'open'` |  |
| priority | TEXT | yes | `'normal'` |  |
| source_type | TEXT | no |  |  |
| source_conversation_id | TEXT | no |  |  |
| source_message_id | TEXT | no |  |  |
| source_artifact_id | TEXT | no |  |  |
| source_tool_name | TEXT | no |  |  |
| created_by | TEXT | yes | `'operator'` |  |
| owner | TEXT | no |  |  |
| created_at | TEXT | yes |  |  |
| updated_at | TEXT | yes |  |  |
| reviewed_at | TEXT | no |  |  |
| metadata_json | TEXT | no |  |  |

**Indexes**
- `idx_review_items_artifact` (non-unique, origin=c): source_artifact_id
- `idx_review_items_category` (non-unique, origin=c): category
- `idx_review_items_conversation` (non-unique, origin=c): source_conversation_id
- `idx_review_items_created_at` (non-unique, origin=c): created_at
- `idx_review_items_priority` (non-unique, origin=c): priority
- `idx_review_items_status` (non-unique, origin=c): status
- `sqlite_autoindex_review_items_1` (unique, origin=pk): item_id

**Foreign Keys**
- `source_artifact_id` -> `artifacts`.`artifact_id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE review_items (
            item_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'other',
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'normal',
            source_type TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_artifact_id TEXT,
            source_tool_name TEXT,
            created_by TEXT NOT NULL DEFAULT 'operator',
            owner TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            reviewed_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY (source_artifact_id) REFERENCES artifacts(artifact_id)
        )
```

</details>

#### `schema_versions`

Type: table

Purpose: Applied working.db schema migration versions.

Primary key: `version`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| version | INTEGER | no |  | 1 |
| name | TEXT | yes |  |  |
| applied_at | TEXT | yes |  |  |

**Indexes**
- None

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE schema_versions (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
```

</details>

#### `summaries`

Type: table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| conversation_id | TEXT | yes |  |  |
| content | TEXT | yes |  |  |
| created_at | TEXT | yes |  |  |

**Indexes**
- `sqlite_autoindex_summaries_1` (unique, origin=pk): id
- `sqlite_autoindex_summaries_2` (unique, origin=u): conversation_id

**Foreign Keys**
- `conversation_id` -> `conversations`.`id` on_update=NO ACTION on_delete=NO ACTION

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE summaries (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
```

</details>

#### `tasks`

Type: table

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| description | TEXT | yes |  |  |
| source | TEXT | yes | `'user'` |  |
| source_user_id | TEXT | no |  |  |
| priority | INTEGER | no | `5` |  |
| status | TEXT | yes | `'pending'` |  |
| created_at | TEXT | yes |  |  |
| started_at | TEXT | no |  |  |
| completed_at | TEXT | no |  |  |
| result_document_id | TEXT | no |  |  |

**Indexes**
- `idx_tasks_priority` (non-unique, origin=c): priority
- `idx_tasks_status` (non-unique, origin=c): status
- `sqlite_autoindex_tasks_1` (unique, origin=pk): id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user',
            source_user_id TEXT,
            priority INTEGER DEFAULT 5,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            result_document_id TEXT
        )
```

</details>

#### `users`

Type: table

Purpose: User records for resolving conversations and operator/admin ownership.

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| name | TEXT | yes |  |  |
| role | TEXT | yes | `'user'` |  |
| created_at | TEXT | yes |  |  |
| last_seen_at | TEXT | no |  |  |

**Indexes**
- `idx_users_role` (non-unique, origin=c): role
- `sqlite_autoindex_users_1` (unique, origin=pk): id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL,
            last_seen_at TEXT
        )
```

</details>

## archive.db

### Tables

#### `messages`

Type: table

Purpose: Conversation messages and optional tool trace JSON.

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| conversation_id | TEXT | yes |  |  |
| user_id | TEXT | yes |  |  |
| role | TEXT | yes |  |  |
| content | TEXT | yes |  |  |
| tool_trace | TEXT | no |  |  |
| timestamp | TEXT | yes |  |  |

**Indexes**
- `idx_archive_conversation` (non-unique, origin=c): conversation_id
- `idx_archive_timestamp` (non-unique, origin=c): timestamp
- `idx_archive_user` (non-unique, origin=c): user_id
- `sqlite_autoindex_messages_1` (unique, origin=pk): id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_trace TEXT,
                timestamp TEXT NOT NULL
            )
```

</details>

#### `users`

Type: table

Purpose: User records for resolving conversations and operator/admin ownership.

Primary key: `id`

| Column | Type | Not Null | Default | Primary Key |
| --- | --- | --- | --- | --- |
| id | TEXT | no |  | 1 |
| name | TEXT | yes |  |  |
| created_at | TEXT | yes |  |  |

**Indexes**
- `sqlite_autoindex_users_1` (unique, origin=pk): id

**Foreign Keys**
- None

<details>
<summary>CREATE SQL</summary>

```sql
CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
```

</details>
