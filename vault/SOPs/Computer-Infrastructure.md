---
tags: [sop, infrastructure, server]
---

# SOP — Computer Infrastructure

## Checklist
- [ ] Port scan / service detection → https://shodan.io
- [ ] Identify hosting provider / ASN → https://bgp.he.net
- [ ] Check VirusTotal → https://virustotal.com
- [ ] Check URLScan → https://urlscan.io
- [ ] Check security headers → https://securityheaders.com
- [ ] Look for admin panels, login pages in subdomain enumeration
- [ ] Check DNS → [[SOPs/Domain-Name]]
- [ ] Check TLS certs → [[SOPs/Encryption-Certificates]]

## Tools
| Tool | URL | Purpose |
|------|-----|---------|
| Shodan | https://shodan.io | Ports, banners, services |
| Censys | https://censys.io | Internet scanning |
| URLScan | https://urlscan.io | Page scan + screenshot |
| VirusTotal | https://virustotal.com | Reputation |
| SecurityHeaders | https://securityheaders.com | HTTP header analysis |
| BGP.he.net | https://bgp.he.net | ASN/hosting |

---
*[[SOPs/README]] · [[vault]]*
