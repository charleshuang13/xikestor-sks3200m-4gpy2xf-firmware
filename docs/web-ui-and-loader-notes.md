# Loader, web UI and feature notes

Everything below was derived from printable strings and disassembly of
`C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318.bin` (V1.9.1) and the full flash dump (V1.9),
plus the source-file paths the build leaked into the binary.

## Firmware architecture

| Piece | Evidence |
|---|---|
| 8051 MCU firmware, Keil C51 | code decodes cleanly with `radare2 -a 8051`; classic C51 library idioms; `MOV SP,#0x7F` startup |
| Banked code (image > 64 KB) | `lcall`/`ljmp` targets do **not** resolve to file offsets |
| Realtek RTL8373 SDK | `..\dal\rtl8373\dal_rtl8373_acl.c`, `dal_rtl8373_isolation.c`, `dal_rtl8373_trunk.c`, `salacl.c` |
| Realtek PHY code | `Rtl8226b_rtct_start need linkdown to trig RTCT`, `rtl8221b`, `Ver8372N=%lu`, `Ver8373N=%lu`, `phy_rtl826xb_patch_flow`, `RL6818C_pwr_on_patch_phy_v007` |
| Lightweight TCP/IP ("lwps") | `..\..\common\src\lwps\tcp.c`, `udp.c`, `etharp.c`, `icmp.c`, `rstp.c`, `lacp_fsm.c` |
| HTTP server + web files | `..\..\common\src\app\web\httpd.c`, `web_api.c`, `..\src\web\web_file.c` |
| Loader / runtime-kernel model | `SPI FLASH VIEWER`, `RunTime Kernel Starting....`, `rt_header->magic_number` |

Source paths use Windows separators, so the vendor built it with Keil on Windows.

## Loader (boot) console

```
==========Loader start===========
Press any key to start the normal procedure.
To run SPI flash viewer, press [v]
To enforce the download of the runtime kernel, press [ESC]
### Please input uboot password below: ###
Loader warm start
cmd %bd
Check Runtime Image.....
=========================SPI FLASH VIEWER=============================
  b                     reboot
  e <addr>              erase flash at <addr>
  ev <addr>             erase and verify
  r <addr> <len>        read flash and dump
  c                     check runtime kernel without boot
  cb                    check runtime kernel and boot if checksum passes
  h                     print header
  l                     load runtime kernel
  v                     verbose
  m                     print menu
  q                     quit
length=0x%x(%d).
Erase 0x%06lx: FAIL (may due to protected regions)
There %bd protected region(s).
 Portected region %bd: 0x%06lx-0x%06lx          (sic, vendor typo)
```

Kernel header checks produce: `Hdr Chksum Error`, `PayLoad Chksum Error`, `Chksum Correct!`,
then `RunTime Kernel Starting....` with a dump of `magic_number / length / header_chksum /
payload_chksum / reserved`. A u-boot style password prompt also exists (it is a static
string comparison in the loader, not stored in flash).

## Web UI

Frameset: `hidden.cgi` + `menu.cgi` + `info.cgi`, page title `Giga Ethernet Switch V1.0`,
styles in `style.css`, password hashing in the browser via `md5.js`
(`hex_md5(username + password)`), session via an `admin=` cookie.
HTTP Basic (`WWW-Authenticate: Basic realm="Switch"`) is implemented as well, and the server
identifies itself as `Web-Smart Server`. Upgrade POST is `multipart/form-data`, field name
`file`.

### cgi endpoints seen in the strings

| Endpoint | Purpose |
|---|---|
| `/httpug.cgi`, `/httpupg.cgi?cmd=fw_upgrade` | firmware upgrade (Enter Upgrade Mode / Loader Mode) |
| `/httpupg.cgi?cmd=conf_backup` | configuration backup (download) |
| `/config_back.cgi?cmd=conf_restore` | configuration restore (upload) |
| `/reboot.cgi` (`cmd=reboot`) | reboot |
| `/ip.cgi` (`cmd=ip`) | IP / mask / gateway (warns "Change IP address will lose connection") |
| `/mac.cgi?page=fwd_tbl` | MAC address table (`cmd=mactblclr` to clear dynamic entries) |
| `/mac.cgi?page=search` | MAC search (`macsearch`) |
| `/mac.cgi?page=static` / `?page=staticdel` | static MAC add/delete |
| `/mac_constraint.cgi` | MAC limit / constraint |
| `/user.cgi` | user account (new username / new password / confirm) |
| `/ftdft.cgi` | **factory default settings**: `devmodel`, `hdrVer`, `mac`, `ip`, `netmask`, `gateway`, `url`, `langen`, `langch`, `dftusr`, `dftpwd` (`hidpwd` carries the md5) |
| `/ftlogo.cgi` | customise the web logo (upload) |
| `/ftcolor.cgi` | customise web UI colours (`color%d` fields) |

The `ftdft` fields map exactly onto the parameter block stored at flash `0x1FD000`
(model string, `V1.0` hardware version, IP/mask/gateway, `admin`, password md5) — i.e. the
factory-default page writes straight into that region.

## Feature inventory (from strings)

* **L2**: 802.1Q VLAN (tagged/untagged/member/not-member, accepted frame type tag-only /
  untag-only), port isolation, port mirroring (rx/tx/both, mirroring + mirrored port lists),
  static MAC, MAC table search + clear, MAC limit per port ("Entry Limits", Unlimited),
  trunk / LAG with member + aggregated port display.
* **LACP**: full 802.3ad state machine (`lacp_fsm.c`) with receive/mux/periodic state dumps
  (`RCVM_*`, `MUXM_*`, `PRM_*`), marker handling, per-aggregator port masks.
* **STP / RSTP**: `rstp.c` with a complete variable dump (root/bridge/port priority,
  timers, state machine `17.22 Port Timers state machine`, roles Root/Designated/Alternate/
  Backup/Disabled, states Discarding/Learning/Forwarding).
* **Loop protection**: Loop Detection / Loop Prevention / Spanning Tree modes, time interval,
  recover time, per-port loop state (Disabled / Blocking / Listening / Forwarding).
* **Multicast**: IGMP snooping with static/dynamic router ports and an IGMP entry dump.
* **DHCP snooping**: global enable, DHCP server / client port roles.
* **QoS**: port-to-queue mapping, queue weight (WRR) and strict priority, 802.1p and DSCP
  (DSCP value / internal priority tables), queue-id and priority_id selects.
* **Rate limiting**: ingress / egress bandwidth control; storm control for broadcast, known
  multicast, unknown unicast, unknown multicast.
* **Other**: Jumbo frame enable, EEE, port statistics (Tx/Rx good/bad packets, link status),
  port speed/duplex/flow control, SNTP client (NTP server, server connected, current time),
  timed reboot (`isal_timedreboot`, `itimedreboot`), configuration save, factory reset,
  web logo / colour customisation, MD5-hashed login.

## Notes / open questions

* `0x004000 - 0x01C000` in the flash (≈96 KB) holds code that is **not** part of the update
  package and **not** covered by its checksum. Purpose unconfirmed.
* 8051 bank mapping (code address <-> file offset) has not been resolved, so `lcall` targets in
  the disassembly cannot be followed to their file offsets.
