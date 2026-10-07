# Build a publishable reference corpus

This guide distinguishes private source material from data that can be
redistributed with the project. It is an engineering policy, not legal advice.

The current example is
[`data/reference/ai103_starter_corpus.json`](../data/reference/ai103_starter_corpus.json).
It is represented by the project maintainers as AI-generated demonstration
content. No third-party transcript, course corpus, or copied question bank was
used as repository content, and no human authorship is claimed for its text.

AI generation does not by itself prove that an output is free of protected
expression. Public AI-generated datasets still require similarity and factual
review before release.

## 1. Use acceptable inputs

For every input, require at least one of these bases:

- public-domain or CC0 material
- a licence permitting redistribution and adaptation
- written permission covering the intended release
- factual claims independently verified against authoritative documentation

Unlicensed transcripts, paid course material, copied questions, distinctive
examples, and close paraphrases stay in `data/local/` or `data/private/`.
Anonymization and source count are not substitutes for permission.

## 2. Record provenance privately

Maintain a source register containing URL, title, publisher, access date,
licence, attribution requirements, and review notes. If rights are unclear,
treat the input as private-only.

Do not commit raw transcripts, private source registers, embeddings, or
intermediate model output merely to prove provenance.

## 3. Extract facts, then write independently

Create small technical claims by exam objective and verify them. Write new
explanations and scenarios from those claims without preserving a source's
wording, sequence, examples, metaphors, or chapter structure.

Do not ask a model to rewrite a source question or paraphrase a transcript.

## 4. Review the candidate dataset

Before release:

1. validate the schema and unique IDs
2. verify factual accuracy against current authoritative documentation
3. run exact, long-substring, and semantic similarity checks against private
   inputs
4. manually review the strongest matches
5. remove distinctive wording and source-specific structure
6. reject every item with uncertain provenance or originality

Similarity checks reduce risk; they do not prove legal safety.

## 5. Add release metadata

Each published corpus needs:

- a stable version and creation date
- its generation or authorship method and responsible maintainer
- a content licence and URL
- a description of included and excluded material
- known limitations and a correction or removal process

Use a content licence such as CC0 or CC BY 4.0. MIT and Apache-2.0 are software
licences and should not be the only licence for a study dataset.

The included AI-generated demo corpus uses CC0 1.0; its terms are in
[`data/reference/LICENSE`](../data/reference/LICENSE).

## 6. Commit only approved outputs

Place approved JSON in `data/reference/`. Keep raw inputs, rejected content,
similarity reports, embeddings, and private notes outside Git.

For every release, record hashes, reviewers, source-register version,
similarity-review outcome, limitations, and removal contact in the corpus
README or release process.

A project licence covers only rights the contributors can grant. It cannot
relicense third-party material beyond existing permission.

## Legal references

- [WIPO: copyright protects expression, not ideas or methods](https://www.wipo.int/en/web/copyright/protection)
- [French Intellectual Property Code, Article L122-4](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006278911)
- [EU Directive 2019/790, Articles 3 and 4](https://eur-lex.europa.eu/eli/dir/2019/790/oj)
- [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
- [Creative Commons CC0](https://creativecommons.org/publicdomain/zero/1.0/)
