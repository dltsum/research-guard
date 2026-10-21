# Documentation maintenance

Maintain the English and Chinese guides when behavior changes. Translate their
meaning naturally; headings, wording and length do not need mechanical identity.
Use the pair list in `assets/documentation-parity.json` as an index.

`python -X utf8 scripts/documentation_parity.py` is an optional health check for
readable, nonempty paired files. It reports missing local links as warnings.
Editing text, adding a document, changing headings or replacing an image needs
no digest refresh, revision marker, token list or provenance seal. The old
`--refresh-hashes` argument is accepted as a no-op compatibility alias.

Check explanations and examples against actual behavior. Preserve historical
test records as history; do not present an earlier run as validation of a new
revision. New instructions must use the current installation and workflow.
