# Bash Helper

A small, self-contained set of Bash helpers — aliases, functions, Git
shortcuts, and a robust DNS switcher — dropped into `~/.bash_helper.d` and
sourced from your `.bashrc`.

## Install

```bash
curl https://raw.githubusercontent.com/alphamarket/bash_helper-pub/master/install | bash
```

Clones the repo into `~/.bash_helper.d` and wires it into `~/.bashrc`. Open a
new shell and you're set.

## Features

- **Everyday aliases** — `ll`, `la`, `..`/`...`, `myip`, `dl`, `kill-port`, `now`, and more.
- **Handy functions** — `genpasswd`, `str_replace`/`str_find`, `videos2mp3`/`videos2mp4`, `t` (open a terminal in the current dir), …
- **Git shortcuts** — quick aliases and functions for everyday Git, with sensible fallbacks outside repos.
- **DNS switcher** — one-command DNS switching that survives reconnects, resets to automatic on reboot, and needs no `sudo`.
- **Drop-in & modular** — each feature is its own file, auto-sourced; bring only what you want.
- **Secret-safe** — machine-specific config and secrets live in gitignored `*.local` files, never in the repo.

## DNS switcher

| Command | Description |
|---------|-------------|
| `dns-proxy` | Switch to your proxy resolvers (default: Shecan) + start an optional keepalive. |
| `dns-default` | Switch to public resolvers (default: Cloudflare + Google). |
| `dns-auto` | Restore the network's automatic (DHCP) DNS. |
| `dns-change <ip…>` | Set any resolvers for the session. |
| `dns-status` | Show the active connection, resolvers, and keepalive state. |
| `dns-keepalive-setup` | Store your own (private) Shecan keepalive password locally. |
| `dns-uninstall` | Clean teardown of all DNS tooling state. |

**Highlights**

- Sticks through Wi-Fi reconnects (set on the NetworkManager connection), but
  resets to automatic on every reboot — so you always start from a known state.
- No `sudo`: relies on polkit, which desktop installs grant by default.
- Fully customizable without touching the source — set `DNS_PROXY_SERVERS`,
  `DNS_DEFAULT_SERVERS`, or your keepalive URL in `~/.bash_helper.d/bh_dns.local`.

**Requirements:** `systemd-resolved` + `NetworkManager`.
