#!/usr/bin/env python3
"""
Clrtable.bin から kikikai 用カラーPROM 3本を作る。
  a85-08.g15 = 赤,  a85-10.g12 = 緑,  a85-09.g14 = 青
各ファイルは「256バイトの色データ + 残りを 0xFF で埋めた」ファイルになる(既定 512バイト)。

使い方:  python3 make_proms.py Clrtable.bin [出力フォルダ] [--size 512]
"""
import sys, os

def build(clr, size=512):
    ent = [tuple(clr[i*4:i*4+4]) for i in range(len(clr)//4)]       # 4バイト/色 (B,G,R,0) の並び
    def rgb4(e): return (e[2]//17, e[1]//17, e[0]//17)              # 0x11の倍数 -> 4ビット値
    sets = [[rgb4(ent[10 + 16*s + p]) for p in range(16)] for s in range(8)]   # 先頭10色は飛ばし、16色×8組
    R, G, B = (bytearray([0xFF]) * size for _ in range(3))          # 後半を 0xFF で埋める
    for code in range(16):                                           # 色番号0-15 に 8組を繰り返し割り当て
        s = sets[code % 8]
        for pen in range(16):
            r, g, b = s[pen]; i = code*16 + pen
            R[i], G[i], B[i] = r, g, b
    return {"a85-08.g15": R, "a85-10.g12": G, "a85-09.g14": B}

def main():
    a = sys.argv[1:]
    size = 512
    if "--size" in a:
        i = a.index("--size"); size = int(a[i+1]); del a[i:i+2]
    src = a[0]; dst = a[1] if len(a) > 1 else "."
    assert size >= 256, "サイズは256以上にしてください"
    os.makedirs(dst, exist_ok=True)
    for name, data in build(open(src, "rb").read(), size).items():
        open(os.path.join(dst, name), "wb").write(data)
        print(f"{name}: {len(data)} バイト (先頭256バイト=色データ, 以降=0xFF)")

if __name__ == "__main__":
    main()
