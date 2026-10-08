# Build and import a local study corpus

Quiz Machine can combine private Markdown notes with official Microsoft Learn
content while keeping embeddings and question generation in local Ollama.

## 1. Start the desktop application

Install Python 3, Ollama and Flutter, then run:

```bash
ollama serve
./start.sh
```

The workspace offers AI-901, AI-103 and AI-200. Microsoft Learn MCP supplies
official scoped evidence; imported notes supplement it and remain on this
computer. During onboarding, select one of the local generation models already
installed in Ollama. Quiz Machine does not download a model automatically.

## 2. Choose material you may use

Suitable private inputs include notes you wrote, original summaries of official
documentation, and material whose licence permits your use. Do not assume that
paraphrasing or combining third-party content creates redistribution rights.

## 3. Create a Markdown file

Copy the complete template from [`CORPUS_FORMAT.md`](CORPUS_FORMAT.md). Important
rules are:

1. keep the `quiz-machine-corpus/v1` frontmatter block at the first line;
2. give the file a unique lowercase `document_id`;
3. choose `AI-901`, `AI-103` or `AI-200`;
4. copy an exact domain name shown by the application;
5. make the single `#` heading identical to `title`;
6. put factual study content under one or more non-empty `##` sections.

The optional `learning_objective` gives retrieval a more precise label. The
optional `source_url` must be HTTPS.

## 4. Import it

Open **Import corpus** from setup or the quiz workspace. Drag one or more `.md`
files from Finder onto the drop zone, or click the zone to use the file picker.
Confirm that you have the necessary content rights.

Validation happens before import. A valid file shows its certification, domain
and semantic chunk count. An invalid file stays visible with the exact failed
rule, source line when available and a suggested repair. The import action is
enabled only when every selected file is valid.

On import, the backend stores the document in the ignored local data directory
and rebuilds `storage/index.json` with Ollama embeddings. If indexing fails, the
new file is rolled back.

## 5. Practise with hybrid evidence

Choose the certification declared by the corpus and start a mixed or
domain-specific session. When a local chunk is relevant, the question context
contains one local chunk plus up to two official Microsoft Learn chunks. The
app never sends more than three evidence chunks to Ollama.

The source coverage panel labels this mode **Microsoft Learn + local corpora**.
If MCP is temporarily unavailable, a correctly scoped local corpus remains a
fallback. Set `AI103_KNOWLEDGE_PROVIDER=local` only when you intentionally want
the legacy offline AI-103 mode.

## Repository boundaries

Public and tracked:

- `data/reference/`

Private or generated and ignored:

- `data/local/`
- `data/private/`
- `storage/*.json`
- `storage/*.log`

The older JSON `chunks` and `chapters` formats remain readable for compatibility,
but new in-app imports use structured Markdown v1.
