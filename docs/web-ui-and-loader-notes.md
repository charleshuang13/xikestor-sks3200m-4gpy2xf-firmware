# Loader、Web 界面与功能笔记

下面这些内容来自 `C6_RF_v1.9.1_SKS3200M-4GPY2XF_20240318.bin`（V1.9.1）和整片 flash dump（V1.9）
里的可打印字符串与反汇编，外加编译时泄进二进制里的源码路径。

## 固件架构

| 部件 | 依据 |
|---|---|
| 8051 单片机固件，Keil C51 编译 | 用 `radare2 -a 8051` 能干净反汇编；标准 C51 库特征；启动处是 `MOV SP,#0x7F` |
| 代码分 bank（镜像大于 64 KB） | `lcall` / `ljmp` 的目标**不能**对应到文件偏移 |
| Realtek RTL8373 SDK | `..\dal\rtl8373\dal_rtl8373_acl.c`、`dal_rtl8373_isolation.c`、`dal_rtl8373_trunk.c`、`salacl.c` |
| Realtek PHY 代码 | `Rtl8226b_rtct_start need linkdown to trig RTCT`、`rtl8221b`、`Ver8372N=%lu`、`Ver8373N=%lu`、`phy_rtl826xb_patch_flow`、`RL6818C_pwr_on_patch_phy_v007` |
| 自家轻量 TCP/IP 栈（叫 lwps） | `..\..\common\src\lwps\tcp.c`、`udp.c`、`etharp.c`、`icmp.c`、`rstp.c`、`lacp_fsm.c` |
| HTTP 服务器 + web 文件 | `..\..\common\src\app\web\httpd.c`、`web_api.c`、`..\src\web\web_file.c` |
| Loader / 运行内核模型 | `SPI FLASH VIEWER`、`RunTime Kernel Starting....`、`rt_header->magic_number` |

源码路径用的是 Windows 反斜杠，所以厂商是在 Windows 上用 Keil 编译的。

## Loader（引导）控制台

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
  b                     重启
  e <addr>              擦除 <addr> 处的 flash
  ev <addr>             擦除并校验
  r <addr> <len>        读取并 dump
  c                     只校验运行内核，不启动
  cb                    校验内核，通过才启动
  h                     打印 header
  l                     载入运行内核
  v                     详细输出
  m                     打印菜单
  q                     退出
length=0x%x(%d).
Erase 0x%06lx: FAIL (may due to protected regions)
There %bd protected region(s).
 Portected region %bd: 0x%06lx-0x%06lx          （原文如此，厂商自己的拼写错误）
```

内核头校验会打印：`Hdr Chksum Error`、`PayLoad Chksum Error`、`Chksum Correct!`，
随后是 `RunTime Kernel Starting....` 以及 `magic_number / length / header_chksum /
payload_chksum / reserved` 的数值。另外还有一个 uboot 风格的密码提示
（是 loader 里的字符串比较，不存放在 flash 里）。

## Web 界面

页面用 frameset：`hidden.cgi` + `menu.cgi` + `info.cgi`，标题 `Giga Ethernet Switch V1.0`，
样式在 `style.css`，密码在浏览器端用 `md5.js` 做哈希（`hex_md5(用户名 + 密码)`），
会话靠名为 `admin=` 的 cookie。同时也实现了 HTTP Basic
（`WWW-Authenticate: Basic realm="Switch"`），服务器自称 `Web-Smart Server`。
升级上传用 `multipart/form-data`，字段名 `file`。

### 字符串里出现的 cgi 接口

| 接口 | 用途 |
|---|---|
| `/httpug.cgi`、`/httpupg.cgi?cmd=fw_upgrade` | 固件升级（Enter Upgrade Mode / Loader Mode） |
| `/httpupg.cgi?cmd=conf_backup` | 配置备份（下载） |
| `/config_back.cgi?cmd=conf_restore` | 配置恢复（上传） |
| `/reboot.cgi`（`cmd=reboot`） | 重启 |
| `/ip.cgi`（`cmd=ip`） | IP / 掩码 / 网关（会提示「改 IP 会掉线」） |
| `/mac.cgi?page=fwd_tbl` | MAC 地址表（`cmd=mactblclr` 清空动态表项） |
| `/mac.cgi?page=search` | MAC 查询（`macsearch`） |
| `/mac.cgi?page=static` / `?page=staticdel` | 静态 MAC 增删 |
| `/mac_constraint.cgi` | MAC 限制 / 约束 |
| `/user.cgi` | 账号管理（新用户名 / 新密码 / 确认密码） |
| `/ftdft.cgi` | **出厂默认设置**：`devmodel`、`hdrVer`、`mac`、`ip`、`netmask`、`gateway`、`url`、`langen`、`langch`、`dftusr`、`dftpwd`（`hidpwd` 带 md5） |
| `/ftlogo.cgi` | 自定义 web logo（上传） |
| `/ftcolor.cgi` | 自定义 web 配色（`color%d` 字段） |

`ftdft` 那些字段，和 flash 里 `0x1FD000` 那块参数区（型号字符串、硬件版本 `V1.0`、IP/掩码/网关、
`admin`、口令 md5）是一一对应的——也就是说这个「出厂默认设置」页面直接往那个区域写。

## 功能清单（从字符串整理）

* **二层**：802.1Q VLAN（tagged / untagged / member / not member，接收帧类型 tag-only /
  untag-only）、端口隔离、端口镜像（收 / 发 / 双向，含镜像端口与被镜像端口列表）、静态 MAC、
  MAC 表查询与清空、单口 MAC 数量限制（Entry Limits / Unlimited）、
  链路聚合（Trunk，成员口与聚合口显示）。
* **LACP**：完整 802.3ad 状态机（`lacp_fsm.c`），带接收 / 复用 / 周期状态打印
  （`RCVM_*`、`MUXM_*`、`PRM_*`）、marker 处理、每个聚合组的端口掩码。
* **STP / RSTP**：`rstp.c`，能打印全套变量（根桥 / 本桥 / 端口优先级、各定时器、
  `17.22 Port Timers state machine` 状态机，角色 Root/Designated/Alternate/Backup/Disabled，
  状态 Discarding/Learning/Forwarding）。
* **环路保护**：环路检测 / 环路预防 / 生成树三种模式，检测间隔、恢复时间，
  每端口环路状态（Disabled / Blocking / Listening / Forwarding）。
* **组播**：IGMP Snooping，含静态 / 动态路由器端口和 IGMP 表项打印。
* **DHCP Snooping**：全局开关、DHCP 服务器 / 客户端端口角色。
* **QoS**：端口到队列映射、队列权重（WRR）与严格优先级、802.1p 与 DSCP
  （DSCP 值 / 内部优先级表）、队列号与优先级选择。
* **限速**：入方向 / 出方向带宽控制；风暴控制（广播、已知组播、未知单播、未知组播）。
* **其它**：巨型帧开关、EEE、端口统计（收 / 发好包坏包、链路状态）、端口速率 / 双工 / 流控、
  SNTP 客户端（NTP 服务器、连接状态、当前时间）、定时重启（`isal_timedreboot`、`itimedreboot`）、
  配置保存、恢复出厂、web logo / 配色自定义、MD5 口令登录。

## 待查项

* flash 里 `0x004000 - 0x01C000`（约 96 KB）是代码，但**不在**升级包里、也**不参与**升级包的校验和，用途未确认。
* 8051 的 bank 映射（代码地址 <-> 文件偏移）还没解出来，所以反汇编里的 `lcall` 目标没法跟到文件偏移。
