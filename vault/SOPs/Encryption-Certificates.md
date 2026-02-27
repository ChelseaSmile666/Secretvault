---
tags: [sop, ssl, tls, certificate]
---

# SOP — Encryption Certificates

## Checklist
- [ ] Certificate transparency search → https://crt.sh
- [ ] Check SANs (Subject Alternative Names) for related domains
- [ ] Check historic certs for old email addresses or org names
- [ ] Cross-reference org name with [[SOPs/Business-Name]]
- [ ] Cross-reference emails found with [[SOPs/Email-Address]]

## crt.sh Query Examples
```
# All certs for a domain
%.example.com

# Certs by organisation
O=Company Name

# Certs by email
example@domain.com
```

## Fields to Extract
| Field | Notes |
|-------|-------|
| Common Name | Primary domain |
| SANs | All domains on cert |
| Org name | May reveal true owner |
| Email in cert | Contact email |
| Issued date | Infrastructure age |
| Issuer | CA used |

---
*[[SOPs/README]] · [[vault]]*
