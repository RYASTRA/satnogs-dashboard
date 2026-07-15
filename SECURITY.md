# Security Policy

## Supported Versions

satnogs-dashboard is pre-1.0 and under active development. Only the most
recent version — currently the `0.1.x` line (latest `main`) — receives
security fixes. There are no maintained older release branches yet.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

**Please report security issues privately — do not open a public issue or PR.**

Use GitHub's private vulnerability reporting: open the
[**Security** tab](https://github.com/RYASTRA/satnogs-dashboard/security)
and click **Report a vulnerability**. This creates a private advisory
visible only to the maintainer.

This is a small, volunteer-maintained project, so please allow reasonable
time to investigate and ship a fix before any public disclosure — 90 days
is a sensible default. I'll acknowledge reports as soon as I'm able.

### Scope

The dashboard mounts the host Docker socket and shells out to sibling
engine containers (`satnogs-signal`, `satnogs-id`, `satnogs-decoder`) via
`docker exec`. Reports touching that trust boundary — container escape,
the exec command paths, or the mounted socket — are especially welcome.
