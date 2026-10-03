# XikeStor SKS3200M-4GPY2XF — Firmware & Full Flash Dump

Unofficial firmware archive for the **XikeStor (兮克) SKS3200M-4GPY2XF**, a fanless,
web-managed ("light managed") L2 switch: **4 x 2.5GbE RJ45 + 2 x SFP+ (10G)**.

Hardware: Realtek **RTL8373** switch ASIC, RTL8226B / RTL8221B 2.5G PHYs, and an
**8051** management MCU (Keil C51 firmware, ~900 KB with bank switching).

This repo exists so owners of this switch can **un-brick it or restore the factory firmware**.
The binaries are the vendor's property — see [Disclaimer](#disclaimer).

## Repository layout

```
firmware/
  SKS3200M-4GPY2XF_v1.9_full-flash_2MB.bin              complete 2 MB flash image (restore / un-brick)
  C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318.bin            vendor update image, V1.9.1
  C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318_patched.bin    same image with 1 opcode byte patched
tools/
  calcsum.py                                            header/payload checksum verify + re-stamp
docs/
  firmware-analysis.md                                  full analysis (device, layout, checksums, patch)
  web-ui-and-loader-notes.md                            loader menu, u-boot prompt, cgi endpoints, features
  factory-web-logo.png                                  web logo extracted from the flash dump
screenshots/
  hex-edit-0xC4418.png                                  hex editor showing the patched byte
checksums.sha256
```

## Files and checksums

| File | Size (bytes) | SHA256 |
|---|---|---|
| `firmware/SKS3200M-4GPY2XF_v1.9_full-flash_2MB.bin` | 2,097,152 | `108a560aa4cd18a66b7dadf4f95d770e4d1b4fa6d6f7d343b67a61f70e50bacf` |
| `firmware/C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318.bin` | 923,828 | `f581617c35768285aca21a83064a757fc4fbcb16be7ea38f440f913a70552ad1` |
| `firmware/C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318_patched.bin` | 923,828 | `e0a6b694015548256b5b55c92c0801d2ec017930da260d3ebf4ad23c89dc9606` |
| `tools/calcsum.py` | 4,829 | `4effa9105ae6409b7d550054da9507a7e4a60d8c40f500a72c92a53d9f9bfbb2` |

MD5: full flash dump `fd83d22ad7d919c6507bbe6b0f17389c`,
vendor update `c2e7bdb2a5b4e7da27d2ac143a60b320`,
patched update `8ccd59d8e78e0f43ba244bbbe4d8dff7`.

## Versions

| Image | Firmware version | Build date |
|---|---|---|
| Full flash dump | **V1.9** | Jan 03 2024 |
| Vendor update image | **V1.9.1** | Mar 18 2024 |

The dump does **not** contain the update package's build. The dump is a **whole-flash** image
(loader + kernel + factory logo + factory default settings); the `.bin` images are
**kernel-only** updates, so flashing them does not touch the loader, logo or settings area.
They are not interchangeable.

Defaults after a full restore: `http://192.168.10.12`, mask `255.255.255.0`, gateway
`192.168.10.1`, user `admin`, password `admin`
(the flash stores `MD5("admin"+"admin")` = `f6fdffe48c908deb0f4c3bd36c032e72`,
which is also the value compiled into the firmware — factory default, not a personal password).

## Update image format

```
0x000000   20 B        header #1
0x000014   0x2FFE      block1
0x003012   0x1000      block2
0x004012   20 B        header #2 (copy of header #1)
0x004026   907,404 B   block3 (main body)
                       payload = 923,808 B = header.length (0x000E18A0)
```

Header: 5 x uint32 **big-endian** — `magic 0x12345678`, `length`, `header_sum`,
`payload_sum`, `reserved 0x332255FF`.

* `header_sum` = byte sum of the 20 header bytes with the `header_sum` field zeroed.
* `payload_sum` = byte sum of `block1 + block2 + 0xFF x 20 + block3`. The header region is
  counted as blank `0xFF`, i.e. the checksum is computed *before* the header is stamped.

`tools/calcsum.py` (public "SWTG Firmware Checksum Calculator", not written by us) validates
this and can re-stamp it. **Without `-u` it never writes to the file.**

```bash
python3 tools/calcsum.py firmware/C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318.bin      # verify only
python3 tools/calcsum.py -u firmware/....bin                                       # verify + re-stamp
```

## Flash layout (2 MB FM25Q16)

Verified by cross-matching the flash dump against the vendor update image at three anchor
points, and by `calcsum.py` confirming the dump's stored payload checksum:

```
0x000000 - 0x001002   loader (4 KB): SPI FLASH VIEWER menu, u-boot style password prompt
0x001002 - 0x004000   kernel block1 (0x2FFE)         <- .bin offset 0x0014
0x004000 - 0x01C000   ~96 KB code region: not in the update package and not covered by the
                      checksum (purpose not confirmed)
0x01C000 - 0x01D000   kernel block2 (0x1000)         <- .bin offset 0x3012
0x01D000 - 0x01D014   kernel header (20 B)           <- .bin offset 0x4012
0x01D014 - 0x0FA8A0   kernel block3 (main body)      <- .bin offset 0x4026
0x0FA8A0 - 0x100000   tail remnants (includes a WebKit multipart boundary from an upload)
0x100000 - 0x1F9008   blank (0xFF)
0x1F9008 - 0x1FA389   factory web logo: uint32 length 0x1377 + PNG 190x65 (brand logo)
0x1FD000 - 0x1FD240   factory default settings (model, HW V1.0, IP/mask/gateway, admin, MD5)
0x1FD14C - 0x1FD1FF   web UI colour table (#F2F2F3 #000000 #DCDCDC #173267 ...)
0x1FE000 - 0x1FEA42   runtime config (nvcfg: port properties, trunk/aggregation, counters)
0x1FEA42 - 0x200000   blank (0xFF)
```

Details, strings-based feature inventory and the checksum math: `docs/firmware-analysis.md`.

## The one-byte patch

`..._patched.bin` differs from the vendor image by 5 bytes: 4 checksum fields plus one opcode
at `0xC4418` (`0x60 -> 0x80`):

```asm
0xC4414  12 2C D5     lcall 0x2CD5
0xC4417  EF           mov   a, r7
0xC4418  60 2A        jz    0x4444      ; vendor image / factory dump: JZ = 0x60
0xC4418  80 2A        sjmp  0x4444      ; patched: SJMP = 0x80
0xC4444  22           ret
```

The vendor path skips a short block only when the called routine returns 0; the patched
version skips it **unconditionally**, i.e. the block at `0xC441A - 0xC4443` is disabled and the
function returns immediately. `0x60` is the original value in the vendor image *and* in the
factory dump (`0xDD405`), so this is a deliberate modification, not a vendor difference.

Note: the 8051 runs banked code, so **code addresses are not file offsets** — `lcall` targets
cannot be resolved to file offsets without first working out the bank mapping.

## Restoring / un-bricking

1. **3.3 V** programmer only (CH341A + FM25Q16, SOP-8 clip or desolder).
2. Read the chip **twice** and compare the two dumps before writing anything.
3. Write `SKS3200M-4GPY2XF_v1.9_full-flash_2MB.bin`, then verify.
4. First boot should come up on the factory defaults listed above.

No guarantee that these images are correct for your board revision — everything here was read
from a single retail unit.

## Provenance

The full flash dump was read from a single retail unit with a CH341A programmer (Feb 2026);
the vendor update image was obtained through the vendor's ordinary download channels.
Archived and documented by [@charleshuang13](https://github.com/charleshuang13).

## Related

* ServeTheHome review of this model (May 2024): `xikestor-sks3200m-4gpy2xf-review-managed-4-port-2-5gbe-switch`
* Vendor manual (SKS32 series, applies to this model): `SKS32Series_Web-Managed-Switch-Manual`

## Disclaimer

The firmware binaries in this repository are the property of their respective rights holders
(Realtek and/or the ODM and/or XikeStor). They are archived solely for **repair and research by
people who own this hardware**. No licence is claimed over the binaries, and no licence file is
provided for them. `tools/calcsum.py` is third-party public code; `docs/` was written for this
archive. If you are a rights holder and want a file removed, please open an issue.

---
---

# 中文说明

兮克（XikeStor）SKS3200M-4GPY2XF 交换机的固件 / 整片 Flash 备份，用途是**救砖和恢复出厂固件**。

- `SKS3200M-4GPY2XF_v1.9_full-flash_2MB.bin`：用 CH341 读出的 **2 MB 全片镜像**，
  含 loader + 内核 + 出厂 web logo + 出厂参数区，整片写回即可恢复。版本 V1.9 / 2024-01-03。
- `C6_RF_v1.9.1_..._20240318.bin`：官方**升级包**，只含内核，版本 V1.9.1 / 2024-03-18；
  刷它不会动 loader、logo 和参数区，所以两者不能互相替代。
- `C6_RF_v1.9.1_..._patched.bin`：上面那个升级包被**手工改过 1 个字节**
  （`0xC4418`：`60 JZ` 改成 `80 SJMP`，等于把那一小段逻辑无条件跳过）。
- `tools/calcsum.py`：校验/回写镜像头部校验和。**不带 `-u` 只读不写**。

默认地址 `http://192.168.10.12`，账号 `admin` / `admin`（flash 里存的是出厂默认哈希，
不是私人密码）。

硬件：Realtek RTL8373 方案 + 8051 管理固件（Keil C51，带 bank 切换）；
4 x 2.5G 电口 + 2 x SFP+ 万兆，无风扇桌面式。

版权归原厂所有，本仓库仅为持有该设备的人提供维修/研究用途，二进制部分不声明任何许可。
