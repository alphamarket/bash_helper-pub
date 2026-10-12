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
- **DNS switcher** — one-command DNS switching that survives reconnects and VPNs, starts every boot on Cloudflare + Google, and needs no `sudo`.
- **Drop-in & modular** — each feature is its own file, auto-sourced; bring only what you want.
- **Secret-safe** — machine-specific config and secrets live in gitignored `*.local` files, never in the repo.

## DNS switcher

| Command | Description |
|---------|-------------|
| `dns-proxy` | Switch to your proxy resolvers (default: Shecan) + start an optional keepalive. |
| `dns-default` | Switch to public resolvers (default: Cloudflare + Google). |
| `dns-auto` | Restore the network's automatic (DHCP) DNS until the next boot. |
| `dns-change <ip…>` | Set any resolvers until the next boot. |
| `dns-status` | Show the active connection, resolvers, and keepalive state. |
| `dns-keepalive-setup` | Store your own (private) Shecan keepalive password locally. |
| `dns-uninstall` | Clean teardown of all DNS tooling state. |
| `sudo net-setup` | Optional one-time system setup: Wi-Fi power saving off + a patient link monitor (stops phone-hotspot drops), resolver fallback + stale cache through outages, and DNS pinned on every connect — including brand-new networks. `--uninstall` reverts it. |

**Highlights**

- Sticks through Wi-Fi reconnects, network switches and VPN tunnels (set on
  every saved NetworkManager connection), and every boot starts on
  `DNS_BOOT_MODE` — `default` (Cloudflare + Google) unless set to `auto` (DHCP).
- No `sudo` for the commands: relies on polkit, which desktop installs grant by default.
- Fully customizable without touching the source — set `DNS_PROXY_SERVERS`,
  `DNS_DEFAULT_SERVERS`, `DNS_BOOT_MODE`, or your keepalive URL in `~/.bash_helper.d/bh_dns.local`.

**Requirements:** `systemd-resolved` + `NetworkManager`.
