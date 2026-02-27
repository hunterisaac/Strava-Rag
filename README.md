# Strava Data Archive — How it works

This project ingests a Strava CSV export, converts each activity row into a short natural-language narrative, creates embeddings for those narratives, stores them in a Chroma vector database, and supports natural-language queries that return answers produced by an LLM. The repository contains the CSV export and an example script `main.py` that demonstrates the full pipeline.

Repository layout
- `strava_data.csv` — source CSV export of activities (required for ingestion).
- `main.py` — example ingestion + query script (uses `ollama` for embeddings and LLM, and `chromadb` for the vector store).
- `strava_vectordb/` — local persistent Chroma store (contains `chroma.sqlite3` and collection files).

Quick prerequisites
- Python 3.8+
- Install minimal dependencies (suggested):

```
ollama
chromadb
pandas
```

How the pipeline works (detailed)

1) Chunking, narrative generation, and embedding
- The CSV is processed line-by-line (each row is treated as one chunk). For each activity the script generates a short narrative — for example: "On Tuesday, I went on a Morning Run that covered X meters...". Each narrative is converted into an embedding using an embedding model (in `main.py` via `ollama.embeddings(model="nomic-embed-text", prompt=narrative)`). The narrative, its embedding, and the original row (plus derived metadata like `month`, `year`, `day_of_week`, and `time_of_day`) are stored together in the Chroma collection. This makes each CSV line directly retrievable by semantic similarity.

2) Query embedding → retrieval → LLM answer
- When a user question is issued, the system creates an embedding of the question (again using `ollama.embeddings`) and uses that vector to query the Chroma collection for the top-matching narratives. The retrieved narratives provide context for answering the question. Those top results are fed into an LLM prompt (via `ollama.generate`) which composes the final answer.

3) Metadata to improve RAG relevance
- Each ingested activity stores metadata alongside the narrative. Metadata includes original CSV columns plus derived fields such as `month`, `year`, `day_of_week`, and `time_of_day`. The metadata is used to support structured filtering (`where` clauses) during retrieval, enabling the RAG pipeline to find more relevant chunks (for example filtering to only `type: Run` or `month: July`). The LLM is also asked to extract structured entities from user questions (via `build_where`) so the pipeline can apply metadata filters before or after semantic search.

4) Tool calls to address numeric/aggregate issues
- Early results were unsatisfactory because narratives—and the LLM—see many numeric values which can make precise aggregate answers (like sums) unreliable. To address this, the script implements a small tools layer: a routing prompt (`build_tool`) detects if the user is asking for an aggregate such as a `total` over a numeric CSV column (e.g., total `moving_time`). When detected, the tool computes the aggregate directly from the CSV using `pandas` and returns the computed value as structured tool output. That tool output is included in the context passed to the final LLM answer prompt. This pattern is extensible: you can add more tools (count, average, date-range filters, unit conversions) that perform deterministic computations against the CSV or metadata, improving reliability for numeric questions.

Running the example (`main.py`)

1. Ensure `strava_data.csv` exists in the repository root.
2. Install dependencies (example):

```bash
python -m pip install ollama chromadb pandas
```

3. Ensure your Ollama instance is running and the required models are available (embedding model and `llama3` used by the script).
4. Run the example script:

```bash
python main.py
```

Expected behavior
- On first run the script will ingest the CSV into `strava_vectordb` and print each generated narrative and metadata as it inserts them.
- After ingestion, `ask_strava` will run example queries and print LLM answers. If the DB already exists, ingestion is skipped.

Design notes & rationale
- Storing one narrative per CSV row keeps the retrieval granularity simple and interpretable.
- Narrative-based embeddings let semantic search match user questions to descriptive activity text rather than raw CSV column names.
- Metadata enables deterministic filtering, which reduces false positives from pure semantic matching.
- Tools perform deterministic numeric logic (sums, counts) outside the LLM to increase accuracy for aggregation queries.

Troubleshooting
- "Database already exists. Skipping import.": remove `strava_vectordb/` or its `chroma.sqlite3` to force re-ingest.
- Ollama errors: confirm the local Ollama daemon or API is reachable and the listed models (`nomic-embed-text`, `llama3`) are installed.
- Chroma errors: confirm `chromadb` is installed and the `strava_vectordb/` directory is writable.

Steps
1. I chunked the CSV file by each line then turned each line into a narrative and embedded it with a model and ChromaDB.
2. I then turned the user prompt into an embedding which retrieves top results and feeds them into an LLM for answer generation.
3. I created metadata to help the RAG pipeline find more relevant chunks (month, year, day_of_week, time_of_day, etc.).
4. The results weren't what I wanted because there are too many numbers, so I added tool calls which anyone can build more of (e.g., `total` which computes column sums directly from the CSV).



