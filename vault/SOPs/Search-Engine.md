---
tags: [sop, search]
---

# SOP — Search Engine Queries

## Checklist
- [ ] Google → https://www.google.com
- [ ] Bing → https://www.bing.com
- [ ] Yandex → https://www.yandex.com
- [ ] DuckDuckGo → https://duckduckgo.com
- [ ] Baidu → https://www.baidu.com (China-indexed content)

## Google Dork Operators

| Operator | Example | Purpose |
|----------|---------|---------|
| `"exact phrase"` | `"John Smith" "New York"` | Exact match |
| `site:` | `site:linkedin.com "John Smith"` | Limit to domain |
| `filetype:` | `filetype:pdf "company name"` | File type filter |
| `inurl:` | `inurl:profile "username"` | Term in URL |
| `intitle:` | `intitle:"John Smith"` | Term in page title |
| `cache:` | `cache:example.com` | Google cached version |
| `-` | `"John Smith" -actor` | Exclude term |
| `OR` | `"J Smith" OR "John Smith"` | Either term |

## Useful Dork Templates

```
# Find person on social media
"{{name}}" site:linkedin.com OR site:twitter.com OR site:instagram.com

# Find documents mentioning a person
"{{name}}" filetype:pdf OR filetype:doc

# Find cached/archived pages
"{{domain}}" site:web.archive.org

# Find email patterns for a company
"@{{domain}}" site:linkedin.com
```

---
*[[SOPs/README]] · [[vault]]*
