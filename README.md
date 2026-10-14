<div align="center">

# bash_helper

**Bash aliases, Git shortcuts, a DNS switcher that sticks, and a one-command fix for flaky phone-hotspot Wi-Fi and stuck VPNs on Linux.**

[![Bash](https://img.shields.io/badge/Bash-4%2B-4EAA25?logo=gnubash&logoColor=white)](#install)
[![Linux](https://img.shields.io/badge/Linux-Ubuntu%20%7C%20Debian-FCC624?logo=linux&logoColor=black)](#requirements)
[![NetworkManager](https://img.shields.io/badge/NetworkManager-systemd--resolved-0A7BBB)](#dns-switcher)
[![Last commit](https://img.shields.io/github/last-commit/alphamarket/bash_helper-pub)](https://github.com/alphamarket/bash_helper-pub/commits/master)
[![Stars](https://img.shields.io/github/stars/alphamarket/bash_helper-pub?style=social)](https://github.com/alphamarket/bash_helper-pub/stargazers)

</div>

## TL;DR

```bash
# 1. Install the shell helpers (aliases, Git shortcuts, DNS switcher)
curl -fsSL https://raw.githubusercontent.com/alphamarket/bash_helper-pub/master/install | bash

# 2. Optional — stable phone-hotspot Wi-Fi, auto-healing VPN, pinned DNS (persists across reboots)
sudo ~/.bash_helper.d/net-setup
```

Open a new terminal. You now have:

| | What you get | Try |
|---|---|---|
| ⚡ | **Shell speed-ups** — 30+ aliases, handy functions, archive shortcuts, prefix history search | `ll`, `hl`, `myip`, `genpasswd` |
| 🌿 | **Git in one or two letters**, with a graph log and branch clean-up | `s`, `a`, `c "msg"`, `p`, `log` |
| 🌐 | **A DNS switcher that sticks** through reconnects, network changes and VPNs — no `sudo` | `dns-default`, `dns-proxy`, `dns-status` |
| 📶 | **Stable phone-hotspot Wi-Fi** — fixes *"Linux laptop keeps disconnecting from my phone's hotspot"* (Intel `iwlwifi` missed beacons) | `sudo net-setup` |
| 🛡️ | **A VPN watchdog** that revives a VPN showing *connected* but passing no traffic (OpenVPN stuck after `AUTH_FAILED`) | `journalctl -t vpn-watchdog -f` |

Modular and secret-safe: every feature is its own file, and machine-specific settings live in gitignored `*.local` files.

## Table of contents

- [Install](#install)
- [Prompt](#prompt)
- [Aliases](#aliases)
- [Functions](#functions)
- [Archive shortcuts](#archive-shortcuts)
- [Git shortcuts](#git-shortcuts)
- [DNS switcher](#dns-switcher)
- [Stable Wi-Fi & VPN: `net-setup`](#stable-wi-fi--vpn-net-setup)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Configuration](#configuration)
- [How it is organised](#how-it-is-organised)
- [Requirements](#requirements)
- [Uninstall](#uninstall)
- [Contributing](#contributing)

## Install

### One-liner

```bash
curl -fsSL https://raw.githubusercontent.com/alphamarket/bash_helper-pub/master/install | bash
```

The installer:

1. clones this repo into `~/.bash_helper.d`,
2. adds one `source` line to `~/.bashrc`,
3. downloads Git's official `git-prompt.sh` (for the branch name in the prompt).

Open a new terminal and everything is active.

### Manual

```bash
git clone https://github.com/alphamarket/bash_helper-pub.git ~/.bash_helper.d
echo 'if [ -f $HOME/.bash_helper.d/bash_helper ]; then . $HOME/.bash_helper.d/bash_helper; fi' >> ~/.bashrc
```

### Network fixes (optional, one time)

```bash
sudo ~/.bash_helper.d/net-setup
```

Safe to re-run at any time; `sudo ~/.bash_helper.d/net-setup --uninstall` reverts it. Details in [Stable Wi-Fi & VPN](#stable-wi-fi--vpn-net-setup).

### Update

```bash
git -C ~/.bash_helper.d pull
```

## Prompt

A two-line prompt with the current Git branch and a timestamp, so long-running commands are easy to time:

```
user@host:~/project (main) [Mon Oct 12 | 23:06:59]
$
```

## Aliases

Defined in `bh_aliases`.

| Alias | Does |
|---|---|
| `ll` / `la` | `ls -alF` / `ls -A` |
| `..` / `...` / `....` | Go up one / two / three directories |
| `~` | Go to your home directory |
| `hl` | Size of everything in the current directory, sorted |
| `myip` | Your public IP address |
| `now` | Current date and time (`2026/10/12 23:06:59`) |
| `ts` | Current Unix timestamp |
| `pp` | Continuous `ping 8.8.8.8` that also reports missed replies |
| `dl <url>` | Fast 16-connection download with `aria2c` |
| `dl-tor` / `dl-mtor` | Download a torrent with `aria2c` (to disk / in memory) |
| `pv <src> <dst>` | Copy with a progress bar (`rsync`) |
| `kill-port <port>` | Kill whatever is listening on a port |
| `open <file>` | Open with the default application |
| `n <file>` | Edit with `nano` |
| `g` / `h` | `grep` / `head` |
| `xclip` | Copy to the system clipboard |
| `apt` / `apt-get` | Always run with `sudo` |
| `x` | Click a window to kill it (`xkill`) |
| `mf` | Turn the monitor off |
| `logout` | Log out of every session of the current user |
| `nwp` | Kill stray `sleep` processes |
| `www` | `cd /var/www` |

> `l` is redefined by the Git shortcuts (last 5 commits); use `ls -CF` directly for the classic listing.

## Functions

Defined in `bh_functions`.

| Function | Does |
|---|---|
| `genpasswd [length]` | Random password with symbols (default 16 characters) |
| `genpasswd2 [length]` | Random password, letters/digits/`_-` only |
| `str_find <dir> <regex> [grep options]` | Find a pattern recursively, with line numbers |
| `str_replace <dir> <from> <to>` | Replace text in every matching file (keeps `.bak` backups) |
| `e <path>…` | Check whether files exist — green `[ YES ]` / red `[ NOP ]` |
| `has_output <command>` | Count the lines a command prints |
| `count_code_line <comment-prefix> <files>…` | Count lines of code, skipping blanks and comments |
| `niceproc <name> <niceness>` | Change the priority of a running process by name |
| `videos2mp3` | Extract MP3 audio from every video in the current directory |
| `videos2mp4 [ffmpeg options]` | Convert every video in the current directory to MP4 |
| `videos2sub` | Extract the first subtitle track of every video to `.srt` |
| `t` | Open a new terminal window in the current directory (Xfce, GNOME, KDE, MATE, LXDE…) |

## Archive shortcuts

Defined in `bh_aliases_compress` — one naming scheme for every format: `mk<format> <archive> <dir>` creates, `un<format> <archive>` extracts.

| Format | Create | Extract |
|---|---|---|
| `.tar` | `mktar` | `untar` |
| `.tar.gz` / `.tgz` | `mktar.gz` / `mktgz` | `untar.gz` / `untgz` |
| `.tar.bz2` | `mktar.bz2` | `untar.bz2` |
| `.tar.xz` | `mktar.xz` | `untar.xz` |
| `.tar.Z` | `mktar.Z` | `untar.Z` |
| `.gz` | `dogz` | `ungz` |
| `.bz2` | `dobz2` | `unbz2` |
| `.xz` | `mkxz` | `unxz` |
| `.Z` | `doZ` | `unZ` |
| `.7z` | `mk7z` | `un7z` |
| `.rar` | `mkrar` | `unrar` |
| `.lha` | `mklha` | `unlha` |

## Git shortcuts

Defined in `git_helper_aliases` and `git_helper_functions`.

**Everyday**

| Shortcut | Runs |
|---|---|
| `s` / `status` | `git status` |
| `a` | `git add -A :/` — stage everything in the repo |
| `c "message"` | `git commit -qam "message"` |
| `p` / `push` | `git push` |
| `pt` | `git push --tags` |
| `pall` | Push commits and tags |
| `log` | Colored graph log with branches, relative dates and authors |
| `l` | The last 5 commits of `log` |
| `diff` / `show` | `git diff` / `git show` |
| `ap` | Amend the last commit with all changes and force-push ⚠️ |

**Branches**

| Shortcut | Runs |
|---|---|
| `b` / `branch` | `git branch` |
| `co <branch>` | `git checkout` |
| `m` / `mm` / `d` | Check out `main` / `master` / `develop` |
| `mp` | Merge `develop` into `main`, then return to `develop` |
| `merge`, `pull`, `clone`, `add`, `commit`, `stash` | The plain Git command |
| `tag` / `tags` | List tags with their messages / `git describe` |
| `clean-merged-branches` | Delete local branches whose remote branch is gone |
| `commit-fixup <sha>` | Fold the staged changes into an older commit (autosquash rebase) |
| `rmt` | Delete editor backup files (`*~`) recursively |
| `gitsa` | Load a project-specific `.gitsa` alias file from the current directory |

`status`, `diff`, `show` and `push` first look for a local `./<command>-all` script (e.g. `./status-all`) and run it if present — handy for workspaces made of several repositories — otherwise they run plain Git.

## DNS switcher

Defined in `bh_dns`. Requires NetworkManager + systemd-resolved; **no `sudo` needed**.

Changing DNS on a modern Linux desktop is surprisingly hard: `/etc/resolv.conf` is a symlink that `systemd-resolved` rewrites on every network event, VPNs push their own resolvers, and every new network brings DHCP DNS. The switcher sets your resolvers on **every** saved NetworkManager connection — Wi-Fi, Ethernet and VPN — so the choice survives reconnects, network changes and VPN tunnels.

| Command | Description |
|---|---|
| `dns-default` | Public resolvers — Cloudflare `1.1.1.1` + Google `8.8.8.8` |
| `dns-proxy` | Your proxy/smart-DNS resolvers (default: Shecan) + optional keepalive |
| `dns-auto` | The network's automatic (DHCP) DNS |
| `dns-change <ip>…` | Any resolvers you choose |
| `dns-status` | Connection, active resolver, keepalive, boot mode and new-network pinning |
| `dns-help` | All commands and the configured resolvers |
| `dns-default-ip-setup [ip…]` | Change the resolvers `dns-default` uses |
| `dns-proxy-ip-setup [ip…]` | Change the resolvers `dns-proxy` uses |
| `dns-keepalive-setup [password]` | Store your private Shecan DDNS password (keeps your IP registered every 5 min) |
| `dns-uninstall` | Clean teardown of all DNS state |

How it behaves:

- **Every boot starts on `DNS_BOOT_MODE`** — Cloudflare + Google by default — so a proxy DNS never lingers by accident. Your choice then holds until the next reboot.
- **New networks are pinned too**, once [`net-setup`](#stable-wi-fi--vpn-net-setup) installs its NetworkManager hook.
- **Outage-proof** with `net-setup`: `systemd-resolved` falls back to `1.1.1.1` / `8.8.8.8` when no link has DNS, and keeps answering from cache through short Wi-Fi or VPN drops instead of failing with `ENOTFOUND`.

## Stable Wi-Fi & VPN: `net-setup`

One idempotent command that turns an unreliable phone-hotspot + VPN setup into a stable one. Every change is a config file or an enabled service, so it **persists across reboots**.

```bash
sudo ~/.bash_helper.d/net-setup              # install / update
sudo ~/.bash_helper.d/net-setup --uninstall  # revert everything
```

| What it sets up | Why it matters |
|---|---|
| **Missing dependencies** | Installs `iw`, `iwconfig`, `curl`, `ping`, `nmcli` and friends with `apt` if any are missing. |
| **Wi-Fi power saving off** | With it on, the card naps between beacons; Android hotspots beacon irregularly, so the link drops with *"Connection to AP lost"*. |
| **Patient link monitor** (`mac80211`) | Gives a silent access point ~60 s instead of ~1 s before disconnecting, so a brief hotspot pause no longer takes down the link, the VPN and every open session. |
| **Intel `iwlmvm` active power scheme** | Keeps Intel Wi-Fi cards (AX200/AX201/AX210…) fully awake for hotspot beacons. |
| **TCP tuned for slow / lossy links** (BBR, linear timeouts, unsent-queue cap) | A TCP-based VPN on 4G freezes for seconds on lost packets, and on a slow tunnel its send queue grows to seconds of delay in front of every ping. BBR and linear timeouts shorten the stalls; `tcp_notsent_lowat` keeps the queue small without capping upload speed. Safe on fast links such as Starlink too. |
| **DNS fallback + stale cache** (`systemd-resolved`) | Name resolution keeps working while a VPN tunnel restarts. |
| **DNS pinned on every connect** (NetworkManager hook) | Every network — even a brand-new one — uses your chosen resolvers. |
| **`vpn-watchdog`** (user service) | Reconnects a VPN that shows *connected* but has passed no traffic for ~30 s while Wi-Fi is fine — e.g. OpenVPN stuck after `AUTH_FAILED`, waiting for a password prompt that never appears. A slow-but-working tunnel is left alone, and a manual disconnect is respected. |
| **`dns-autoreset`** (user service) | Re-pins DNS to the boot mode at every login. |

Useful checks:

```bash
journalctl -t vpn-watchdog -f                 # watch the VPN watchdog
systemctl --user status vpn-watchdog          # is it running?
iwconfig wlp59s0 | grep -E 'Frequency|Power'  # 5 GHz? power management off?
dns-status                                    # current DNS setup
```

## Troubleshooting & FAQ

<details>
<summary><b>My Linux laptop keeps disconnecting from my phone's Wi-Fi hotspot</b></summary>

Typical lines in `journalctl -k`:

```
iwlwifi: missed beacons exceeds threshold, but receiving data. Stay connected, Expect bugs.
wlp59s0: Connection to AP xx:xx:xx:xx:xx:xx lost
```

1. Run `sudo net-setup` — it disables Wi-Fi power saving and makes the link monitor tolerant of beacon pauses.
2. On the phone, switch the hotspot to **5 GHz** (*Hotspot settings → AP band*). On many phones 2.4 GHz Wi-Fi shares one radio with Bluetooth, so the hotspot goes silent in bursts; on 5 GHz that cannot happen.
3. On the phone, turn off **Bluetooth scanning** and **Wi-Fi scanning** (*Location → Location services*), and keep it charging so battery saver doesn't throttle the hotspot.

</details>

<details>
<summary><b>The VPN says "connected" but nothing loads</b></summary>

Look for this in `journalctl -t nm-openvpn`:

```
Inactivity timeout (--ping-restart), restarting
AUTH: Received control message: AUTH_FAILED
ERROR: could not read Auth username/password/ok/string from management interface
```

OpenVPN restarted the tunnel, the server rejected the quick re-login, and the NetworkManager plugin is now waiting for a password nobody supplies. `vpn-watchdog` (installed by `net-setup`) detects the dead tunnel and reconnects it automatically within about 40 seconds.

</details>

<details>
<summary><b>Pings through the VPN freeze for seconds, then arrive all at once</b></summary>

Two causes, both handled by `net-setup`: a TCP-based VPN (`proto tcp`) holds back everything behind a single lost packet until it is resent (BBR + linear retransmission timeouts shorten that), and on a slow tunnel the VPN's send queue grows to hundreds of KB — seconds of delay — whenever something uploads (`tcp_notsent_lowat` caps the queue, not the speed). The complete cure for the first is a UDP VPN endpoint, if your provider offers one.

</details>

<details>
<summary><b><code>nslookup</code> shows <code>127.0.0.53</code> — is my DNS wrong?</b></summary>

No. `127.0.0.53` is the local `systemd-resolved` stub, which forwards to your real resolvers. Run `dns-status` or `resolvectl dns` to see the upstream servers actually in use.

</details>

<details>
<summary><b>I changed DNS and it reset after a reboot</b></summary>

That is intentional: each boot starts on `DNS_BOOT_MODE` (Cloudflare + Google by default). Set `DNS_BOOT_MODE='auto'` in `bh_dns.local` to start on DHCP DNS instead, or change the defaults with `dns-default-ip-setup`.

</details>

## Configuration

Override defaults in `~/.bash_helper.d/bh_dns.local` — gitignored, never committed:

```bash
DNS_DEFAULT_SERVERS='1.1.1.1 8.8.8.8'          # used by dns-default and at every boot
DNS_PROXY_SERVERS='178.22.122.101 185.51.200.1' # used by dns-proxy
DNS_BOOT_MODE='default'                         # default | auto (DHCP)
```

Or set them interactively with `dns-default-ip-setup`, `dns-proxy-ip-setup` and `dns-keepalive-setup`.

## How it is organised

| File | Contents |
|---|---|
| `bash_helper` | Entry point sourced from `~/.bashrc`; sets the prompt and loads the modules |
| `bh_aliases`, `bh_aliases_compress` | Aliases and archive shortcuts |
| `bh_functions` | Shell functions |
| `bh_inputrc` | <kbd>↑</kbd>/<kbd>↓</kbd> search history by what you have typed |
| `git_helper_aliases`, `git_helper_functions` | Git shortcuts |
| `bh_dns`, `bh_dns.local` | DNS switcher and your private settings (gitignored) |
| `net-setup` | One-time root setup for Wi-Fi, TCP, DNS and the user services |
| `dns-pin.dispatcher` | NetworkManager hook installed by `net-setup` |
| `dns-autoreset`, `vpn-watchdog` (+ `.service`) | Per-user services installed by `net-setup` |
| `install` | The one-line installer |

## Requirements

- **Bash 4+** on Linux — developed on Ubuntu 24.04; Debian/Ubuntu-based distros work out of the box.
- **DNS switcher and `net-setup`:** NetworkManager + systemd-resolved (the Ubuntu desktop default).
- **Optional tools** for related shortcuts: `aria2c`, `ffmpeg`, `rsync`, `xclip`, `npx` (`kill-port`), `7z`, `rar`, `lha`.

## Uninstall

```bash
sudo ~/.bash_helper.d/net-setup --uninstall   # revert the network changes
dns-uninstall                                 # reset DNS to automatic
rm -rf ~/.bash_helper.d                       # remove the helpers
```

Then delete the `bash_helper` and `git-prompt.sh` lines from `~/.bashrc`.

## Contributing

Issues and pull requests are welcome. Keep each feature in its own file, keep machine-specific values in `*.local` files, and check scripts with `bash -n` (and `shellcheck`, if available) before opening a pull request.

If this saved you from a flaky hotspot or a stuck VPN, a ⭐ helps others find it.
