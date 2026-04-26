# Obsidian Integration

Stuart integrates deeply with [Obsidian](https://obsidian.md/), allowing it to treat your local markdown vault as a structured, human-readable long-term memory.

## 🚀 Overview

The Obsidian integration allows Stuart to:
1.  **Search** your vault using semantic (vector-based) search.
2.  **Read** existing notes to gain context on your projects, meetings, or thoughts.
3.  **Write** new notes with structured frontmatter (YAML) to save memories or summaries.

## 🛠️ Capabilities

### `semantic_search`
Uses Stuart's internal Vector Database (Qdrant) to find conceptually relevant notes even if the exact keywords don't match.
- **Parameters**: `query` (search phrase)
- **Use Case**: "What did we decide about the payment architecture last week?"

### `read_note`
Retrieves the full content of a specific markdown file.
- **Parameters**: `filename` (e.g., `Project_X.md`)
- **Use Case**: Reading a project requirement or a meeting transcript.

### `write_note`
Creates or overwrites a note in the vault. Stuart automatically includes frontmatter with:
- `author: Stuart-AI`
- `created: [timestamp]`
- `tags: [custom_tags]`
- **Parameters**: `filename`, `content`, `tags`

## ⚙️ Configuration

To enable Obsidian Sync, set your vault path in `.env` or during onboarding:

```env
OBSIDIAN_VAULT_PATH="C:/Users/YourName/Documents/MyVault"
```

## 🧠 Behind the Scenes

When Stuart writes a note to Obsidian, it also:
1.  **Chunks** the text into smaller pieces.
2.  **Vectorizes** the chunks using an embedding model (e.g., `all-MiniLM-L6-v2`).
3.  **Stores** the vectors in the local Qdrant collection for later retrieval.

This ensures that the "human-readable" vault and the "AI-optimized" vector DB stay in sync.

## 🧪 Testing

You can verify the sync using the integrated test script:
```bash
python knowledge/test_obsidian_sync.py
```
This script will attempt to write a test note and then perform a semantic search to retrieve it.
