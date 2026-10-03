# 兮克 XikeStor SKS3200M-4GPY2XF 固件备份分析

分析对象：`SKS3200M-4GPY2XF 固件备份/` 目录（7 个文件，5.4 MB）
分析时间：2026-10-03

> 本文按**原始备份目录**里的文件名描述。
> 发布版仓库（`xikestor-sks3200m-4gpy2xf-firmware/`）里的文件名对应关系见文末第 9 节。

---

## 1. 一句话结论

这是一台**兮克（XikeStor）SKS3200M-4GPY2XF 轻管理交换机**的固件集合，里面有三种东西：

1. 用 CH341 编程器从 SPI Flash（FM25Q16，2 MB）里**整片读出来的原厂固件镜像**（V1.9，2024-01-03）——救砖用，最完整；
2. 官方**升级包**（C6_RF V1.9.1，2024-03-18，文件名 `..._0318.bin`）；
3. 上面这个升级包被**手工改过 1 个字节**的版本（就是 `.bin`，原始版被另存成 `.bin.bak`）。

外加一个校验和工具 `calcsum.py`，和一张记录改动的十六进制编辑器截图 `1.png`。

---

## 2. 设备与本机识别

| 项目 | 结论 |
|---|---|
| 型号 | XikeStor（兮克）SKS3200M-4GPY2XF |
| 形态 | 4 x 2.5GbE 电口 + 2 x SFP+（10G）Web 轻管理二层交换机，桌面式、无风扇 |
| 主控 | Realtek RTL8373 系列交换芯片；固件里大量 `..\dal\rtl8373\dal_rtl8373_*.c` |
| PHY | RTL8226B / RTL8221B（2.5G PHY，含 RTCT / SDS / patch 相关字符串） |
| 固件 MCU | **8051**（Keil C51 编译，`radare2 -a 8051` 可正常反汇编；代码带 bank 切换，代码地址 != 文件偏移） |
| 固件结构 | Loader（4 KB 引导，带 SPI FLASH VIEWER 菜单和 uboot 密码提示）+ Runtime Kernel（约 900 KB） |
| Web 管理 | 内置 HTTP 服务器（`lwps` 轻量协议栈 + `httpd.c` / `web_file.c`），cgi 接口 |
| 默认网络 | IP `192.168.10.12` / 掩码 `255.255.255.0` / 网关 `192.168.10.1` |
| 默认账号 | `admin` / `admin`（Flash 里存的是 `MD5("admin"+"admin")` = `f6fdffe48c908deb0f4c3bd36c032e72`，**固件内部也是这个值，属出厂默认**） |

### 从字符串里能确认的功能（V1.9.1）

VLAN(802.1Q) / 端口隔离 / 端口镜像 / 出入口限速 / Jumbo Frame / 风暴控制（广播、已知组播、未知单播、未知组播）/ EEE /
MAC 限制与静态 MAC / MAC 地址表查询与清空 / IGMP Snooping / DHCP Snooping / LACP(802.3ad 状态机) / STP+RSTP（带完整调试打印）/
环路检测与环路恢复 / QoS（端口-队列映射、队列权重 WRR、严格优先级、DSCP、802.1p）/ SNTP 时间同步 / 链路聚合 /
配置备份与恢复 / 固件在线升级 / 用户名密码修改 / 恢复出厂 / **Web logo 自定义** / **Web 配色自定义**。

### Loader（引导程序）里能确认的东西

```
==========Loader start===========
Press any key to start the normal procedure.
To run SPI flash viewer, press [v]
To enforce the download of the runtime kernel, press [ESC]
### Please input uboot password below: ###
=========================SPI FLASH VIEWER=============================
  b: reboot / e <addr>: Erase / ev <addr>: Erase+Verify / r <addr> <len>: dump
  c: check runtime kernel without boot / cb: check kernel and boot if checksum pass
  h: print header / l: load runtime kernel / v: verbose / m: menu / q: quit
```

内核镜像头校验：`magic_number / length / header_chksum / payload_chksum / reserved`，
错误提示 `Hdr Chksum Error` / `PayLoad Chksum Error` / `Chksum Correct!` / `RunTime Kernel Starting....`。

---

## 3. 文件清单（含校验值）

| 文件 | 大小 | SHA256（前 16 位） | 说明 |
|---|---|---|---|
| `ch341_fm25q16_兮克_SKS3200M-4GPY2XF/ch341_fm25q16_兮克_SKS3200M-4GPY2XF` | 2,097,152 B (2 MB) | `108a560aa4cd18a6` | **整片 SPI Flash 原始镜像**，CH341 读出，含 loader + 内核 + web logo + 出厂参数 |
| `ch341_fm25q16_兮克_SKS3200M-4GPY2XF.rar` | 183,221 B | `d642388987fd295d` | 上面那个 2 MB 文件的压缩包，内容相同（包内只有一个文件） |
| `C6_RF_V1.9.1_SKS3200M-4GPY2XF_0318.bin` | 923,828 B | `e0a6b69401554825` | 官方升级包 V1.9.1，**被手工改过 1 个字节** |
| `C6_RF_V1.9.1_SKS3200M-4GPY2XF_0318.bin.bak` | 923,828 B | `f581617c35768285` | 同一个升级包的**未改动原版**（编辑器自动存的备份） |
| `calcsum.py` | 4,829 B | `4effa9105ae6409b` | 固件校验和工具（"SWTG Firmware Checksum Calculator"），只校验/可回写 |
| `1.png` | 1,500,799 B | `943e367966b45187` | 十六进制编辑器截图，光标停在 `0xC4418`，标记"已修改" |
| `.DS_Store` | 8 KB | — | macOS 垃圾文件，发布时删掉 |

MD5（备用）：dump `fd83d22ad7d919c6507bbe6b0f17389c`；bin `8ccd59d8e78e0f43ba244bbbe4d8dff7`；bak `c2e7bdb2a5b4e7da27d2ac143a60b320`。

---

## 4. 三个镜像的版本关系

| 镜像 | 版本 | 编译日期 | 说明 |
|---|---|---|---|
| Flash 实读 dump | **V1.9** | **Jan 03 2024** | 机器里原本跑的（出厂）固件 |
| `.bin` / `.bin.bak` | **V1.9.1** | **Mar 18 2024** | 官方升级包（比出厂固件新） |

两点要注意：

- dump 里**找不到** `Mar 18 2024` 也找不到 `V1.9.1` —— 所以 dump 不是"当前官方升级包的一份拷贝"，是更早的出厂版本，两者不能互相替代。
- dump 是**整片 Flash**：loader、内核、出厂 web logo、出厂默认参数区都在里面，能整片恢复（救砖必需）；
  官方 `.bin` **只含内核（kernel）**，刷进去不动 loader / logo / 参数区，只能用来升级。

---

## 5. 镜像格式（升级包 `.bin`）

```
偏移        长度        内容
0x000000    20 B        header #1
0x000014    0x2FFE      block1
0x003012    0x1000      block2
0x004012    20 B        header #2（同一个 header 的副本）
0x004026    907,404 B   block3（主体）
合计 payload = 923,808 B（= header.length 0x000E18A0），文件总长 923,828 B
```

### header 格式（大端，5 x uint32）

| 字段 | 值 | 说明 |
|---|---|---|
| magic | `0x12345678` | 固定 |
| length | `0x000E18A0` | payload 长度（不含 20 字节头） |
| header_sum | 变动 | 头校验：20 字节里把 header_sum 字段本身清零后逐字节累加（取低 32 位） |
| payload_sum | 变动 | 载荷校验：block1 + block2 + 0xFF x 20 + block3 逐字节累加 |
| reserved | `0x332255FF` | 固定 |

> 把 header 位置按 `0xFF` 参与计算，说明**校验和是先算好、再把 header 盖上去的**（原厂出厂流程）。

### `calcsum.py` 的用法

```bash
python3 calcsum.py firmware.bin          # 只校验、只打印 header
python3 calcsum.py -u firmware.bin       # 校验并回写 header_sum / payload_sum
```

脚本按文件头两个字节自动判断类型（小端 `0x4000` = FULL 整片镜像，`0x3412` = UPDATE 升级包）：
- UPDATE 的 block 偏移 = 0x14 / 0x3012 / 0x4012
- FULL 的 block 偏移 = 0x1002 / 0x1C000 / 0x1D000（就是下面这张 Flash 地图）

**不传 `-u` 它绝不写文件**；带 `-u` 才会改校验和字段。你那份 `.bin` 和 `.bin.bak` 的校验和差异就是这么来的。

---

## 6. Flash 地图（2 MB FM25Q16，实测）

用「dump 与官方 .bin 三处交叉比对 + `calcsum.py` 对 dump 校验通过」确认的对应关系：

```
0x000000 - 0x001002   Loader / 引导程序（4 KB，含 SPI FLASH VIEWER、uboot 密码提示）
0x001002 - 0x004000   kernel block1 (0x2FFE)          <-- 对应 .bin 的 0x0014
0x004000 - 0x01C000   96 KB 代码区（约 0x18000）      <-- 升级包里没有、也不参与校验，用途未查清
0x01C000 - 0x01D000   kernel block2 (0x1000)          <-- 对应 .bin 的 0x3012（V1.9 与 V1.9.1 这段 94% 相同）
0x01D000 - 0x01D014   kernel header (20 B)            <-- 对应 .bin 的 0x4012
0x01D014 - 0x0FA8A0   kernel block3（主体）           <-- 对应 .bin 的 0x4026
0x0FA8A0 - 0x100000   镜像尾部残留（含一段 "------WebKitFormBoundary...--" 上传残留）
0x100000 - 0x1F9008   空白（全 0xFF，约 1 MB）
0x1F9008 - 0x1FA389   出厂 web logo：4 字节长度 0x1377 + PNG（190x65，"兮" + "XIKE" 品牌 logo）+ multipart 边界尾
0x1FD000 - 0x1FD240   工厂默认参数区（ftdft）：型号 SKS3200M-4GPY2XF / HW V1.0 / IP / 掩码 / 网关 / admin / MD5(adminadmin)
0x1FD14C - 0x1FD1FF   Web 配色表（#F2F2F3 #000000 #DCDCDC #173267 ...，用 '#' 分隔的文本）
0x1FE000 - 0x1FEA42   运行配置 nvcfg（端口属性、trunk/聚合、计数等结构化数据）
0x1FEA42 - 0x200000   空白（全 0xFF）
```

---

## 7. 那 1 个字节的改动（`.bin` vs `.bin.bak`）

两份文件**只差 5 个字节**：4 个是校验和字段（`0x0B` `0x0F` `0x401D` `0x4021`），第 5 个是唯一的数据改动：

```
偏移 0xC4418：.bin.bak = 0x60    .bin = 0x80
```

用 `radare2 -a 8051` 反汇编这一小段：

```asm
0xC4414  12 2C D5     lcall 0x2CD5
0xC4417  EF           mov   a, r7
0xC4418  60 2A        jz    0x4444        ; <-- 原厂（.bak）
0xC4418  80 2A        sjmp  0x4444        ; <-- 你改的（.bin）
0xC441A  ...          （0xC441A - 0xC4443 一整段被跳过）
0xC4444  22           ret
```

**机制**：原厂是"上一步返回 0 才跳过这一小段"；改成 `SJMP` 后变成"**无条件跳过**"，
也就是说 `0xC441A - 0xC4443`（清 XRAM 0x8096 → 调用子程序 → 读 XRAM 0x8091 的 bit0 →
以 DPTR=0x871F 调用 0x26C6 → 打印 → 调用 0x51ED）这段逻辑被**整段禁用**，函数直接返回。

旁证：同样的指令序列 `7E 00 7F 10 ... EF 60 2A`（19 处）在两个版本里都是 `0x60`（JZ），
出厂 dump 的对应位置（`0xDD405`）也是 `0x60`。所以 **`0x60` 是原厂值，`0x80` 是人为改的**，方向明确。

> `1.png` 里十六进制编辑器光标正好停在 `C4418` 并标"已修改"，和上面完全对上。

关于地址：8051 代码空间是 64 KB + bank 切换，**代码地址不等于文件偏移**（`lcall 0x2CD5` 里的
0x2CD5 在文件里是别的东西），所以这次只解出了"这一字节改成什么"，没解出"那个被调用的函数在文件哪里"。
要往下挖需要先把 bank 映射解出来。

---

## 8. 发布前的隐私 / 合规检查

### 隐私：干净

逐项检查了 dump 里属于"这台机器特有"的数据：

- 账号：`admin`，口令哈希 `f6fdffe48c908deb0f4c3bd36c032e72` = `MD5("adminadmin")`
  → **和固件内置的出厂默认值一模一样**，不是私人密码；
- 网络参数：`192.168.10.12 / 255.255.255.0 / 192.168.10.1` → 出厂默认；
- web logo：从 flash 里提取出来看过了（`analysis/logo-from-flash.png`），是品牌 logo「兮 + XIKE」，
  **不是私人图片**；
- 配色：出厂配色表；
- 全片扫了一遍，没有 MAC 字符串、没有用户名、没有配置痕迹。

结论：dump 里没有能定位到你本人或你内网的信息。（如果以后你改过 logo / 配色 / 账号再读片子，就要重新检查。）

### 版权：需要一句免责

固件是 Realtek 系 ODM 的成果，兮克只是贴牌。GitHub 上放厂商固件做救砖/研究是常见做法，但：

- **不要给二进制文件加 LICENSE，不要声称版权归你**；README 里写清楚"版权归原厂，仅供持有该设备的人维修/研究"；
- 你的 `calcsum.py`（如果不是你写的）同样不要声明成自己的，注明来源不明 / 来自公开资料；
- 真要留许可证，只对一个你自己写的文档/脚本部分生效，并明确"不覆盖 firmware/ 下的二进制"。

---

## 9. 发布版仓库（已建好）

```
xikestor-sks3200m-4gpy2xf-firmware/
├── README.md                                           英文为主 + 中文段，可直接用
├── checksums.sha256
├── .gitignore
├── firmware/
│   ├── SKS3200M-4GPY2XF_v1.9_full-flash_2MB.bin         <- ch341 dump（2 MB 整片）
│   ├── C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318.bin       <- bin.bak（官方原版）
│   └── C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318_patched.bin <- bin（改过 0xC4418 的版本）
├── tools/
│   └── calcsum.py
├── docs/
│   ├── firmware-analysis.md         本文
│   ├── web-ui-and-loader-notes.md   loader 菜单 / uboot 提示 / cgi 接口表 / 功能清单 / 源码路径
│   └── factory-web-logo.png         从 flash 里抠出来的出厂 logo
└── screenshots/
    └── hex-edit-0xC4418.png         原 1.png
```

命名对照：`ch341_fm25q16_兮克_...` → `SKS3200M-4GPY2XF_v1.9_full-flash_2MB.bin`；
`..._0318.bin.bak` → `..._20240318.bin`（**原版**）；`..._0318.bin` → `..._20240318_patched.bin`（**改过的**）。

规则：

- 文件名全部 ASCII（中文名在 GitHub 上会变成 `%E5%85%AE%E5%85%8B` 这种乱码链接）；
- 2 MB 文件直接 git 提交，不用 Git LFS；
- `.rar` 不放（和 dump 内容重复），`.DS_Store` 删掉并在 `.gitignore` 里屏蔽；
- 不提供 LICENSE 文件：二进制版权归原厂，不给它们加许可比加错许可安全。

---

## 10. 还没查清 / 待确认

1. `0x004000 - 0x01C000` 那 96 KB 代码区：不在升级包里、不参与校验和，性质未确认
   （可能是出厂/备用区，也可能是 loader 用的另一段镜像）。
2. `0xC4418` 改动的**目的**：机制已经解出来了（无条件跳过一小段逻辑），但"为什么要关掉它"只有你知道——
   如果告诉我当时的现象，我可以把那段函数完整反汇编出来。
3. 代码地址 ↔ 文件偏移的 bank 映射：没解出来，导致 `lcall` 目标无法定位。要做完整反汇编得先解它。
