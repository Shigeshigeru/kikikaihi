#!/usr/bin/env python3
"""
kikikai_mcu_v2.asm をアセンブルして a85-01_jph1020p.h8 (4096バイト) を作り、
未使用領域の4バイトを調整して CRC32 を指定値に合わせる。

使い方:  python3 make_mcu_rom.py [目標CRC32(16進)] [出力ファイル]
  例:    python3 make_mcu_rom.py 01771197 a85-01_jph1020p.h8
必要:    asm6801.py と kikikai_mcu_v2.asm が同じフォルダにあること

注意: これは自作の代替MCUです。CRC32を合わせても本物のダンプにはなりません。
      MAMEはCRC32だけでなくSHA1も照合するため、SHA1が違えば警告は残ります。
"""
import sys, zlib, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm6801 import assemble

ADJ_OFFSET = 0x0F00          # ファイル内オフセット (= MCUアドレス 0xFF00)。コード/テーブル/ベクタのどれにも使われていない
FILL = 0x01                  # 未使用領域は NOP で埋める

def build_rom(asm_path):
    src = open(asm_path, encoding="utf-8").read()
    out, _ = assemble(src, 0xF000)
    rom = bytearray([FILL] * 0x1000)
    for addr, val in out.items():
        rom[addr - 0xF000] = val
    # 調整用4バイトが他の用途と重なっていないことを確認
    used = {a - 0xF000 for a in out}
    assert not any(o in used for o in range(ADJ_OFFSET, ADJ_OFFSET + 4)), "調整領域が使用中です"
    return rom

def force_crc32(data, pos, target):
    """data[pos:pos+4] を書き換えて zlib.crc32(data) == target にする (GF(2)上の連立方程式を解く)"""
    base = bytearray(data); base[pos:pos + 4] = b"\0\0\0\0"
    c0 = zlib.crc32(base) & 0xFFFFFFFF
    cols = []
    for bit in range(32):
        t = bytearray(base); t[pos + bit // 8] |= 1 << (bit % 8)
        cols.append((zlib.crc32(t) & 0xFFFFFFFF) ^ c0)       # 各ビットを立てたときのCRC変化量
    need = target ^ c0
    # ガウスの消去法: sum(x_i * cols[i]) = need
    rows = [(cols[i], 1 << i) for i in range(32)]            # (CRC変化量, どのビットの組合せか)
    basis = []                                               # (pivotビット, 値, 組合せ)
    for val, comb in rows:
        for pb, bv, bc in basis:
            if val >> pb & 1: val ^= bv; comb ^= bc
        if val:
            basis.append((val.bit_length() - 1, val, comb))
    sol = 0
    for pb, bv, bc in sorted(basis, key=lambda x: -x[0]):
        if need >> pb & 1: need ^= bv; sol ^= bc
    if need: raise ValueError("このCRC32には調整できません")
    out = bytearray(data)
    patch = bytearray(4)
    for bit in range(32):
        if sol >> bit & 1: patch[bit // 8] |= 1 << (bit % 8)
    out[pos:pos + 4] = patch
    assert zlib.crc32(out) & 0xFFFFFFFF == target
    return out

def main():
    target = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x01771197
    dst = sys.argv[2] if len(sys.argv) > 2 else "a85-01_jph1020p.h8"
    here = os.path.dirname(os.path.abspath(__file__))
    rom = build_rom(os.path.join(here, "kikikai_mcu_v2.asm"))
    rom = force_crc32(rom, ADJ_OFFSET, target)
    open(dst, "wb").write(rom)
    print(f"{dst}: {len(rom)} バイト  CRC32={zlib.crc32(rom) & 0xFFFFFFFF:08x}  "
          f"調整バイト(0x{ADJ_OFFSET:03X}-0x{ADJ_OFFSET+3:03X})={rom[ADJ_OFFSET:ADJ_OFFSET+4].hex(' ')}")

if __name__ == "__main__":
    main()
