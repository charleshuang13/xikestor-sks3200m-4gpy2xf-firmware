#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
固件校验和工具（图形界面版）——兮克 SKS3200M 系列等使用同一镜像格式的设备

功能：
  1. 校验固件镜像的 header 校验和与载荷校验和，判断文件是否完整 / 有没有被人改过。
  2. 需要时把正确的校验和回写进 header（写入前自动备份原文件）。

只依赖 Python 自带的库（tkinter / struct / shutil），不需要 pip 安装任何东西。
Windows / macOS / Linux 都能跑；Windows 上双击本文件即可打开。

镜像格式（与命令行版 calcsum.py 完全一致）：
  头部 20 字节，大端 5 个 uint32：magic(0x12345678) / length / header_sum / payload_sum / reserved(0x332255FF)
  header_sum  = 20 字节头里把 header_sum 字段清零后的逐字节累加
  payload_sum = block1 + block2 + 0xFF x 20 + block3 的逐字节累加
                （header 那 20 字节按空白 0xFF 参与计算，即校验和先算、header 后盖上去）

两种镜像类型（看文件开头两字节的小端值）：
  0x4000  整片镜像 FULL    block1@0x1002 block2@0x1C000 header@0x1D000
  0x3412  升级包 UPDATE    header@0x000000 block1@0x0014 block2@0x3012 header副本@0x004012
"""

import os
import re
import shutil
import struct
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "固件校验和工具 — SKS3200M 系列"
APP_VERSION = "1.0"

HEADER_MAGIC = 0x12345678
HEADER_RESERVED = 0x332255FF
HEADER_LENGTH = 20
BLOCK1_LENGTH = 0x2FFE
BLOCK2_LENGTH = 0x1000

TYPE_FULL = "full"      # 整片 flash 镜像
TYPE_UPDATE = "update"  # 内核升级包
TYPE_UNKNOWN = "unknown"

# 每种类型的 block 位置
LAYOUT = {
    TYPE_FULL: {"block1": 0x1002, "block2": 0x1C000, "headers": [0x1D000]},
    TYPE_UPDATE: {"block1": 0x14, "block2": 0x3012, "headers": [0x000000, 0x4012]},
}

TYPE_NAME = {
    TYPE_FULL: "整片 Flash 镜像（FULL）",
    TYPE_UPDATE: "内核升级包（UPDATE）",
    TYPE_UNKNOWN: "无法识别",
}

COLOR_OK = "#1a7f37"
COLOR_BAD = "#c62828"
COLOR_WARN = "#9a6700"
COLOR_TEXT = "#202124"
COLOR_DIM = "#5f6368"


# ----------------------------------------------------------------------------
# 纯逻辑部分（不涉及界面，方便单独测试）
# ----------------------------------------------------------------------------

def read_u32_be(buf, off):
    return struct.unpack(">I", buf[off:off + 4])[0]


def header_to_dict(buf, off):
    """读 20 字节头，返回字段字典（若越界返回 None）"""
    if off + HEADER_LENGTH > len(buf):
        return None
    magic, length, header_sum, payload_sum, reserved = struct.unpack(
        ">5I", buf[off:off + HEADER_LENGTH])
    return {
        "offset": off,
        "magic": magic,
        "length": length,
        "header_sum": header_sum,
        "payload_sum": payload_sum,
        "reserved": reserved,
    }


def calc_header_sum(hdr_bytes):
    """20 字节头，把 header_sum 字段（第 8~11 字节）清零后逐字节累加"""
    b = bytearray(hdr_bytes)
    b[8:12] = b"\x00\x00\x00\x00"
    return sum(b)


def pack_header(hdr):
    """按大端打包成 20 字节"""
    return struct.pack(">5I", hdr["magic"], hdr["length"], hdr["header_sum"],
                       hdr["payload_sum"], hdr["reserved"])


def detect_type(buf):
    if len(buf) < HEADER_LENGTH:
        return TYPE_UNKNOWN, "文件太小（不足 20 字节），不可能是固件镜像"
    first2 = int.from_bytes(buf[0:2], byteorder="little")
    if first2 == 0x4000:
        return TYPE_FULL, ""
    if first2 == 0x3412:
        if len(buf) < 0x4012 + HEADER_LENGTH:
            return TYPE_UNKNOWN, "文件长度不足，不像是完整的升级包"
        if len(buf) >= HEADER_LENGTH:
            length = read_u32_be(buf, 4)
            if length + HEADER_LENGTH != len(buf):
                return TYPE_UNKNOWN, (
                    "文件开头是升级包的标志，但长度对不上（header 里写 %d，"
                    "文件实际 %d）——文件不完整或被截断" % (length + HEADER_LENGTH, len(buf)))
        return TYPE_UPDATE, ""
    return TYPE_UNKNOWN, "文件开头不是本工具的镜像标志（0x4000 或 0x3412）"


def guess_version(buf):
    """猜固件版本与编译日期（只是参考，图个方便）"""
    version = ""
    # 版本字符串后面紧跟着硬件版本，形如 "V1.9.1\x00V1.0"
    m = re.search(rb"V(\d+\.\d+(?:\.\d+)?)\x00V\d+\.\d+", buf)
    if m:
        version = m.group(1).decode("ascii", "replace")
    date = ""
    m = re.search(rb"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [ 0-9]\d \d{4}", buf)
    if m:
        date = m.group(0).decode("ascii", "replace")
    return version, date


def analyse(path):
    """校验一个文件，返回结果字典（供界面显示）"""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        buf = f.read()

    r = {
        "path": path,
        "size": size,
        "type": TYPE_UNKNOWN,
        "type_name": TYPE_NAME[TYPE_UNKNOWN],
        "notes": [],
        "headers": [],
        "payload_calc": None,
        "version": "",
        "date": "",
        "verdict": "unknown",   # ok / bad / unknown
        "message": "",
    }
    r["version"], r["date"] = guess_version(buf)

    kind, why = detect_type(buf)
    r["type"] = kind
    r["type_name"] = TYPE_NAME[kind]
    if kind == TYPE_UNKNOWN:
        r["message"] = why or "无法识别"
        return r

    lay = LAYOUT[kind]
    for hoff in lay["headers"]:
        h = header_to_dict(buf, hoff)
        if h is None:
            r["notes"].append("header @0x%X 越界，读到文件末尾了" % hoff)
            continue
        h["magic_ok"] = (h["magic"] == HEADER_MAGIC)
        h["reserved_ok"] = (h["reserved"] == HEADER_RESERVED)
        raw = buf[hoff:hoff + HEADER_LENGTH]
        h["header_sum_calc"] = calc_header_sum(raw)
        h["header_sum_ok"] = (h["header_sum_calc"] == h["header_sum"])
        r["headers"].append(h)

    if not r["headers"]:
        r["message"] = "读不到 header，文件可能不完整"
        return r

    last = r["headers"][-1]
    if not last["magic_ok"]:
        r["notes"].append("header 里的 magic 不是 0x12345678，不像是本格式的镜像")

    # 载荷校验和
    total = BLOCK1_LENGTH + BLOCK2_LENGTH + HEADER_LENGTH
    b3_len = last["length"] - total
    if b3_len < 0:
        r["notes"].append("header 里的 length 太小（0x%X），算不出载荷长度" % last["length"])
        r["message"] = "header 内容异常，无法计算载荷校验和"
        return r

    p1 = buf[lay["block1"]:lay["block1"] + BLOCK1_LENGTH]
    p2 = buf[lay["block2"]:lay["block2"] + BLOCK2_LENGTH]
    b3_start = last["offset"] + HEADER_LENGTH
    p3 = buf[b3_start:b3_start + b3_len]

    if len(p1) != BLOCK1_LENGTH:
        r["notes"].append("block1 长度不足（读到 %d / 需要 %d）" % (len(p1), BLOCK1_LENGTH))
    if len(p2) != BLOCK2_LENGTH:
        r["notes"].append("block2 长度不足（读到 %d / 需要 %d）" % (len(p2), BLOCK2_LENGTH))
    if len(p3) != b3_len:
        r["notes"].append("block3 长度不足（读到 %d / 需要 %d）" % (len(p3), b3_len))

    r["block_sizes"] = (len(p1), len(p2), len(p3))
    r["payload_calc"] = sum(p1) + sum(p2) + 0xFF * HEADER_LENGTH + sum(p3)
    r["payload_ok"] = (r["payload_calc"] == last["payload_sum"])

    hdr_ok = all(h["header_sum_ok"] for h in r["headers"])
    magic_ok = all(h["magic_ok"] for h in r["headers"])

    if r["payload_ok"] and hdr_ok and magic_ok:
        r["verdict"] = "ok"
        r["message"] = "校验通过：文件内容与校验和一致"
    elif not r["payload_ok"]:
        r["verdict"] = "bad"
        r["message"] = ("校验失败：载荷校验和对不上——文件被改过但没重算校验和，或者已经损坏")
    else:
        r["verdict"] = "bad"
        r["message"] = "校验失败：header 校验和对不上"
    return r


def restamp(path, result=None):
    """把正确的校验和写回 header（先自动备份），返回 (是否成功, 说明, 备份路径)"""
    if result is None:
        result = analyse(path)
    if result["type"] == TYPE_UNKNOWN:
        return False, "无法识别这个文件，不做写入", ""
    if result["payload_calc"] is None:
        return False, "算不出载荷校验和，不做写入", ""

    with open(path, "rb") as f:
        buf = bytearray(f.read())

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = "%s.bak-%s" % (path, stamp)
    shutil.copy2(path, backup)

    for h in result["headers"]:
        hdr = dict(h)
        hdr["payload_sum"] = result["payload_calc"]
        hdr["header_sum"] = calc_header_sum(pack_header({**hdr, "header_sum": 0}))
        buf[h["offset"]:h["offset"] + HEADER_LENGTH] = pack_header(hdr)

    with open(path, "wb") as f:
        f.write(buf)
    return True, "已写入 %d 个 header 的校验和" % len(result["headers"]), backup


# ----------------------------------------------------------------------------
# 图形界面
# ----------------------------------------------------------------------------

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE + "  v" + APP_VERSION)
        self.geometry("820x620")
        self.minsize(700, 520)
        self.configure(bg="white")
        self.result = None
        self.path_var = tk.StringVar()

        self._build_ui()

    # ---------------- 界面搭建 ----------------
    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        # 1) 选文件
        top = ttk.Frame(root)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="固件文件：").grid(row=0, column=0, sticky="w")
        self.path_entry = ttk.Entry(top, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="浏览…", command=self.on_browse).grid(row=0, column=2)
        ttk.Button(top, text="校验", command=self.on_check).grid(row=0, column=3, padx=(8, 0))

        # 2) 文件信息
        info = ttk.LabelFrame(root, text=" 文件信息 ", padding=10)
        info.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        info.columnconfigure(1, weight=1)
        info.columnconfigure(3, weight=1)
        self.lbl_size = self._info_row(info, 0, 0, "文件大小：")
        self.lbl_type = self._info_row(info, 0, 2, "镜像类型：")
        self.lbl_ver = self._info_row(info, 1, 0, "固件版本（推测）：")
        self.lbl_date = self._info_row(info, 1, 2, "编译日期（推测）：")

        # 3) 结论
        self.lbl_verdict = tk.Label(root, text="请选择固件文件后点「校验」", bg="white",
                                    fg=COLOR_DIM, anchor="w", justify="left",
                                    font=("", 13, "bold"), wraplength=760)
        self.lbl_verdict.grid(row=2, column=0, sticky="ew", pady=(12, 0))

        # 4) 校验和明细
        detail = ttk.LabelFrame(root, text=" 校验和明细 ", padding=10)
        detail.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        detail.columnconfigure(0, weight=1)
        self.txt = tk.Text(detail, height=11, wrap="none", bg="#f8f9fa", fg=COLOR_TEXT,
                           relief="flat", font=("Consolas" if sys.platform == "win32" else "Menlo", 11))
        self.txt.grid(row=0, column=0, sticky="ew")
        self.txt.configure(state="disabled")

        # 5) 日志
        logf = ttk.LabelFrame(root, text=" 操作记录 ", padding=10)
        logf.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        self.log = tk.Text(logf, height=6, wrap="word", bg="#f8f9fa", fg=COLOR_DIM,
                           relief="flat", font=("", 10))
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.configure(state="disabled")

        # 6) 按钮
        btns = ttk.Frame(root)
        btns.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        btns.columnconfigure(2, weight=1)
        self.btn_write = ttk.Button(btns, text="写入校验和（修正 header）",
                                    command=self.on_write, state="disabled")
        self.btn_write.grid(row=0, column=0)
        ttk.Button(btns, text="清空记录", command=self.on_clear).grid(row=0, column=1, padx=(8, 0))
        tk.Label(btns, text="写入前会自动生成一份 .bak-日期时间 备份，原文件不会被直接覆盖。",
                 bg="white", fg=COLOR_DIM).grid(row=0, column=2, sticky="e")

    def _info_row(self, parent, row, col, label):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w")
        v = tk.Label(parent, text="—", bg="white", fg=COLOR_TEXT, anchor="w")
        v.grid(row=row, column=col + 1, sticky="w", padx=(0, 20))
        return v

    # ---------------- 动作 ----------------
    def log_line(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("[%H:%M:%S] ") + text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_text(self, lines):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(lines))
        self.txt.configure(state="disabled")

    def on_browse(self):
        p = filedialog.askopenfilename(
            title="选择固件文件",
            filetypes=[("固件镜像", "*.bin"), ("所有文件", "*.*")])
        if p:
            self.path_var.set(p)
            self.on_check()

    def on_check(self):
        path = self.path_var.get().strip().strip('"')
        if not path:
            messagebox.showinfo("提示", "请先选择固件文件")
            return
        if not os.path.isfile(path):
            self.lbl_verdict.configure(text="找不到这个文件：" + path, fg=COLOR_BAD)
            self.set_text([])
            self.btn_write.configure(state="disabled")
            return

        self.log_line("开始校验：" + path)
        try:
            r = analyse(path)
        except Exception as e:                                  # noqa: BLE001
            self.log_line("出错：" + repr(e))
            messagebox.showerror("出错", "读文件时出错：\n%s" % e)
            return
        self.result = r

        self.lbl_size.configure(text="%s 字节（%.2f MB）" % (f"{r['size']:,}", r["size"] / 1048576))
        self.lbl_type.configure(text=r["type_name"])
        self.lbl_ver.configure(text=("V" + r["version"]) if r["version"] else "—")
        self.lbl_date.configure(text=r["date"] or "—")

        color = {"ok": COLOR_OK, "bad": COLOR_BAD, "unknown": COLOR_WARN}[r["verdict"]]
        self.lbl_verdict.configure(text=r["message"], fg=color)

        lines = []
        for h in r["headers"]:
            lines.append("header @ 0x%06X" % h["offset"])
            lines.append("  magic        : 0x%08X  %s" % (
                h["magic"], "正常" if h["magic_ok"] else "异常！应为 0x%08X" % HEADER_MAGIC))
            lines.append("  length       : 0x%08X  (%d 字节)" % (h["length"], h["length"]))
            lines.append("  reserved     : 0x%08X  %s" % (
                h["reserved"], "正常" if h["reserved_ok"] else "异常！应为 0x%08X" % HEADER_RESERVED))
            lines.append("  header_sum   : 文件里 0x%08X   算出来 0x%08X   %s" % (
                h["header_sum"], h["header_sum_calc"],
                "一致" if h["header_sum_ok"] else "不一致 ←"))
        if r["payload_calc"] is not None:
            last = r["headers"][-1]
            lines.append("")
            lines.append("载荷（block1 %d + block2 %d + header 20x0xFF + block3 %d 字节）"
                         % r["block_sizes"])
            lines.append("  payload_sum  : 文件里 0x%08X   算出来 0x%08X   %s" % (
                last["payload_sum"], r["payload_calc"],
                "一致" if r["payload_ok"] else "不一致 ←"))
        for n in r["notes"]:
            lines.append("")
            lines.append("注意：" + n)
        self.set_text(lines)

        for n in r["notes"]:
            self.log_line("注意：" + n)
        self.log_line("结论：" + r["message"])

        can_write = (r["type"] != TYPE_UNKNOWN) and (not r["payload_ok"]) and os.access(path, os.W_OK)
        self.btn_write.configure(state="normal" if can_write else "disabled")
        if r["type"] != TYPE_UNKNOWN and not r["payload_ok"] and not os.access(path, os.W_OK):
            self.log_line("文件只读，无法写入校验和（先去掉只读属性）")

    def on_write(self):
        path = self.path_var.get().strip().strip('"')
        if not self.result or self.result["path"] != path:
            self.on_check()
        if not self.result or self.result["type"] == TYPE_UNKNOWN:
            return
        last = self.result["headers"][-1]
        msg = ("将把算出来的校验和写回 header：\n\n"
               "  payload_sum  0x%08X ← 0x%08X\n"
               "  header_sum   0x%08X ← 0x%08X\n\n"
               "改动位置：%s\n\n"
               "写入前会自动生成 .bak-日期时间 备份。要继续吗？" % (
                   last["payload_sum"], self.result["payload_calc"],
                   last["header_sum"], last["header_sum_calc"],
                   "、".join("0x%06X" % h["offset"] for h in self.result["headers"])))
        if not messagebox.askyesno("确认写入", msg):
            self.log_line("已取消写入")
            return
        try:
            ok, note, backup = restamp(path, self.result)
        except Exception as e:                                  # noqa: BLE001
            self.log_line("写入失败：" + repr(e))
            messagebox.showerror("写入失败", str(e))
            return
        if not ok:
            self.log_line(note)
            messagebox.showwarning("没有写入", note)
            return
        self.log_line(note)
        self.log_line("备份文件：" + backup)
        self.log_line("重新校验一次…")
        self.on_check()
        if self.result and self.result["verdict"] == "ok":
            self.log_line("完成：现在校验通过")
            messagebox.showinfo("完成", "校验和已写入，并且重新校验通过。\n\n备份在：\n" + backup)
        else:
            messagebox.showwarning("注意", "已经写入，但重新校验仍然不一致，请检查文件是否完整。")

    def on_clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")


def selftest():
    """无界面自检：造两个假镜像，验证「校验 → 改坏能发现 → 回写 → 再校验通过」整条链路。
    不打开窗口，可以在没有桌面的机器（比如 CI）上跑。"""
    import tempfile

    def build_update():
        b1 = bytes((i * 7 + 3) & 0xFF for i in range(BLOCK1_LENGTH))
        b2 = bytes((i * 11 + 5) & 0xFF for i in range(BLOCK2_LENGTH))
        b3 = bytes((i * 13 + 9) & 0xFF for i in range(1000))
        length = BLOCK1_LENGTH + BLOCK2_LENGTH + HEADER_LENGTH + len(b3)
        payload = sum(b1) + sum(b2) + 0xFF * HEADER_LENGTH + sum(b3)
        hdr = {"magic": HEADER_MAGIC, "length": length, "header_sum": 0,
               "payload_sum": payload, "reserved": HEADER_RESERVED}
        hdr["header_sum"] = calc_header_sum(pack_header(hdr))
        raw = pack_header(hdr)
        return raw + b1 + b2 + raw + b3

    def build_full():
        b1 = bytes((i * 3 + 1) & 0xFF for i in range(BLOCK1_LENGTH))
        b2 = bytes((i * 5 + 2) & 0xFF for i in range(BLOCK2_LENGTH))
        b3 = bytes((i * 9 + 7) & 0xFF for i in range(600))
        buf = bytearray(0x1D014 + len(b3))
        buf[0] = 0x00
        buf[1] = 0x40
        buf[0x1002:0x1002 + BLOCK1_LENGTH] = b1
        buf[0x1C000:0x1C000 + BLOCK2_LENGTH] = b2
        buf[0x1D014:0x1D014 + len(b3)] = b3
        length = BLOCK1_LENGTH + BLOCK2_LENGTH + HEADER_LENGTH + len(b3)
        payload = sum(b1) + sum(b2) + 0xFF * HEADER_LENGTH + sum(b3)
        hdr = {"magic": HEADER_MAGIC, "length": length, "header_sum": 0,
               "payload_sum": payload, "reserved": HEADER_RESERVED}
        hdr["header_sum"] = calc_header_sum(pack_header(hdr))
        buf[0x1D000:0x1D014] = pack_header(hdr)
        return bytes(buf)

    results = []
    for name, data in (("升级包 UPDATE", build_update()), ("整片镜像 FULL", build_full())):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "selftest.bin")
            with open(p, "wb") as f:
                f.write(data)

            r = analyse(p)
            results.append((name + "：正确的镜像应判为通过", r["verdict"] == "ok", r["verdict"]))

            ba = bytearray(open(p, "rb").read())
            ba[0x3000] ^= 0x5A                      # 在载荷里改坏一个字节
            open(p, "wb").write(ba)
            r = analyse(p)
            results.append((name + "：改坏一个字节应判为失败", r["verdict"] == "bad", r["verdict"]))

            ok, note, bak = restamp(p, r)
            results.append((name + "：回写校验和后应重新通过",
                            ok and analyse(p)["verdict"] == "ok", note))

            with open(p, "rb") as f:
                fixed = f.read()
            expect = bytearray(data)
            expect[0x3000] ^= 0x5A
            # 回写只应该动 header 那几处，载荷一个字节都不能碰
            hdr_idx = set()
            for o in LAYOUT[r["type"]]["headers"]:
                hdr_idx.update(range(o, o + HEADER_LENGTH))
            results.append((name + "：回写只改 header，载荷一字节没动",
                            len(fixed) == len(data)
                            and any(fixed[i] != data[i] for i in hdr_idx)
                            and all(fixed[i] == expect[i] for i in range(len(expect))
                                    if i not in hdr_idx),
                            "备份 " + os.path.basename(bak)))

    ok_all = True
    for title, ok, detail in results:
        print(("通过  " if ok else "失败  ") + title + "  (" + str(detail) + ")")
        ok_all = ok_all and ok
    print("自检结果：" + ("全部通过" if ok_all else "有失败项"))
    return 0 if ok_all else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
