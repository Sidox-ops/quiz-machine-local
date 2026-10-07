# Study data

The indexer recursively reads `.json`, `.md`, and `.txt` files from this
directory.

## Public reference data

`reference/ai103_starter_corpus.json` is included with the repository. It is a
compact AI-generated example containing 33 AI-103 demonstration chunks and is
loaded automatically when the RAG index is built. No human authorship is
claimed for its text.

Files under `data/reference/` may be committed only after provenance,
originality, accuracy, and licence review. See `reference/README.md` and
`../docs/PUBLISHABLE_CORPUS.md`.

## Private local data

Place personal notes and legally obtained study material in:

- `data/local/`
- `data/private/`

Both directories are ignored by Git. Third-party transcripts and derived
course corpora belong there unless redistribution is explicitly permitted.

Rebuild the index after changing any corpus file:

```bash
.venv/bin/python build_index.py
```

See `../docs/CORPUS_TUTORIAL.md` for the complete JSON schema and workflow.
