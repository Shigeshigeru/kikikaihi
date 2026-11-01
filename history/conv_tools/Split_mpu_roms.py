#!/usr/bin/env python3
"""
MPU1ROM.BIN / MPU1BROM.BIN / MPU2ROM.BIN から MAME(kikikai) 用の
  a85-17.h16 / a85-16.h18 / a85-11.f6  を作る。

  a85-17.h16 (64KB) = MPU1ROM.BIN (32KB) + MPU1BROM.BIN の後半32KB (0x10000以降)
  a85-16.h18 (64KB) = MPU1BROM.BIN の前半64KB (0x00000-0x0FFFF)
  a85-11.f6  (32KB) = MPU2ROM.BIN そのまま

使い方:  python3 split_mpu_roms.py [入力フォルダ] [出力フォルダ]
         (省略時は どちらもカレントフォルダ)
"""
import sys, os, zlib

EXPECTED = {"a85-17.h16": 0xC141D5AB, "a85-16.h18": 0x4094D750, "a85-11.f6": 0xCC3539DB}   # MAMEのCRC32

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    dst = sys.argv[2] if len(sys.argv) > 2 else "."
    def read(name):
        p = os.path.join(src, name)
        if not os.path.isfile(p): sys.exit(f"ファイルが見つかりません: {p}")
        return open(p, "rb").read()
    mpu1, mpu1b, mpu2 = read("MPU1ROM.BIN"), read("MPU1BROM.BIN"), read("MPU2ROM.BIN")
    if (len(mpu1), len(mpu1b), len(mpu2)) != (0x8000, 0x18000, 0x8000):
        sys.exit(f"サイズが想定と違います: MPU1ROM={len(mpu1):#x} MPU1BROM={len(mpu1b):#x} MPU2ROM={len(mpu2):#x}"
                 " (期待: 0x8000 / 0x18000 / 0x8000)")
    out = {
        "a85-17.h16": mpu1 + mpu1b[0x10000:],
        "a85-16.h18": mpu1b[:0x10000],
        "a85-11.f6":  mpu2,
    }
    os.makedirs(dst, exist_ok=True)
    for name, data in out.items():
        open(os.path.join(dst, name), "wb").write(data)
        crc = zlib.crc32(data) & 0xFFFFFFFF
        print(f"{name}: {len(data):6d} バイト  CRC32={crc:08x}  MAME期待値={EXPECTED[name]:08x}  "
              f"{'一致' if crc == EXPECTED[name] else '不一致'}")

if __name__ == "__main__":
    main()