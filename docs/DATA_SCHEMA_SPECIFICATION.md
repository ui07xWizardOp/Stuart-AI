# Stuart Data Schema Specification

This document provides granular definitions for all persistent data formats used by Stuart-AI. Development of new tools or modules must adhere to these schemas to ensure cross-session compatibility.

## 📁 1. Cron Job Persistence (`data/cron_jobs.json`)
This file stores all proactive tasks scheduled by the user.

### JSON Structure:
```json
[
  {
    "job_id": "cron_8a2b1c3d",
    "time_str": "08:00",
    "prompt": "Summarize my top 5 unread emails.",
    "job_type": "daily",
    "interval_minutes": 0,
    "created_at": "2026-03-12T14:45:00Z"
  }
]
```

### Field Definitions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `job_id` | String | Unique UUID-like identifier prefixed with `cron_`. |
| `time_str` | String | 24-hour time format (`HH:MM`). Ignored if `job_type` is `interval`. |
| `prompt` | String | The natural language instruction to be injected into the Orchestrator. |
| `job_type` | Enum | `daily` (fixed time) or `interval` (recurring). |
| `interval_minutes` | Integer | Frequency in minutes for `interval` jobs. |

## 🧠 2. Plan Library Storage (`data/plans/*.json`)
Proven reasoning plans are stored as individual JSON files indexed by the MD5 hash of the original intent.

### JSON Structure:
```json
{
  "intent_hash": "e99a18c428cb38d5f260853678922e03",
  "original_prompt": "What's the weather in Tokyo?",
  "tool_sequence": [
    {
      "tool": "weather_api",
      "action": "get_weather",
      "parameters": {"city": "Tokyo"}
    }
  ],
  "created_at": "2026-03-13T10:00:00Z",
  "execution_count": 5
}
```

## 🗄️ 3. Memory Schema (SQLite)
The `LongTermMemory` module uses a standard relational schema for performance and persistence.

### Table: `memory_facts`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique ID. |
| `category` | TEXT | INDEXED | `proven_plans`, `interaction_history`, etc. |
| `key` | TEXT | UNIQUE | Intent hash or explicit key. |
| `facts` | TEXT | JSON string | The actual data payload. |
| `created_at` | DATETIME | DEFAULT current_timestamp | When the memory was encoded. |

## ⚙️ 4. Token Quota State
Quotas are currently kept in memory but can be serialized to `data/quota_state.json`.

### Snapshot Structure:
```json
{
  "daily_cloud_usage": 45678,
  "daily_local_usage": 12345,
  "last_reset_date": "2026-03-13"
}
```

---

> [!NOTE]
> All automated backups and migration scripts reference these exact schemas. Modification of field names or types will require a corresponding `database/migrations/` entry.
