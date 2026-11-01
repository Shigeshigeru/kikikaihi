#!/usr/bin/env python3
"""
PTRNIMG.BIN (1byte=1pixel, 8x8タイル連続, 各タイルは90度回転して格納) -> MAME kikikai の gfx1 ROM 4本 に変換
 MAMEの定義(kikikai.cpp):
   ROM_REGION(0x40000,"gfx1",ROMREGION_INVERT)  a85-15.a1 / a85-14.a3 / a85-13.a4 / a85-12.a6 (各64KB)
   charlayout: 8x8, 8192タイル, 4bpp, planes{0x20000*8, 0x20000*8+4, 0, 4},
               xoff{3,2,1,0,11,10,9,8}, yoff{0,16,...,112}, 1タイル=16バイト
使い方: python3 ptrn_to_mame_kikikai.py PTRNIMG.BIN 出力フォルダ
"""
import sys, os, zlib
XOFF=[3,2,1,0,11,10,9,8]; YOFF=[y*16 for y in range(8)]
PLANES=[0x20000*8, 0x20000*8+4, 0, 4]
NAMES=["a85-15.a1","a85-14.a3","a85-13.a4","a85-12.a6"]
WANT=[0xaebc8c32,0xa9df0453,0x3eeaf878,0x91e58067]

def convert(pix):
    assert len(pix)==8192*64, "サイズが 0x80000 ではありません"
    reg=bytearray(0x40000)
    for t in range(8192):
        for y in range(8):
            for x in range(8):
                v=pix[t*64+x*8+(7-y)] & 15     # Windows版は各タイルが90度回転: MAME(x,y) <- PC(7-y,x)
                for pi,po in enumerate(PLANES):
                    if (v>>(3-pi))&1:               # plane0 が最上位ビット
                        n=t*128+YOFF[y]+XOFF[x]+po
                        reg[n>>3] |= 0x80>>(n&7)
    return bytes(b^0xff for b in reg)               # ROMREGION_INVERT 分を戻す

def main():
    src,dst=sys.argv[1:3]
    out=convert(open(src,"rb").read())
    os.makedirs(dst,exist_ok=True)
    for i,n in enumerate(NAMES):
        d=out[i*0x10000:(i+1)*0x10000]
        open(os.path.join(dst,n),"wb").write(d)
        c=zlib.crc32(d)&0xffffffff
        print(f"{n}: crc32={c:08x}  MAME期待値={WANT[i]:08x}  {'一致' if c==WANT[i] else '不一致'}")
if __name__=="__main__": main()
