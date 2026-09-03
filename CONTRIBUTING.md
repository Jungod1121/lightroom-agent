# Contributing

## Bilingual docs

These files are pairs. Update **both** in the same change:

| English | 中文 |
|---|---|
| `README.md` | `README.zh-CN.md` |
| `docs/architecture.svg` | `docs/architecture.zh-CN.svg` |

Do not add a “what changed vs last week” section to either README. Describe the product as it is now.

## Tests

```bash
cd server
./.venv/bin/python -m unittest discover -s tests
```
