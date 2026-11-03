#!/usr/bin/env python3
"""
メディアカイト版 奇々怪界 から MAME(kikikai) 用ROMセット kikikai.zip を一括作成する。

必要な入力ファイル(すべて同じフォルダに置く):
  MPU1ROM.BIN / MPU1BROM.BIN / MPU2ROM.BIN   ... プログラム・サウンドROM
  Clrtable.bin                               ... カラーテーブル (カラーPROMを作成)
  PTRNIMG.BIN                                ... グラフィック (グラフィックROMを作成)

作成されるファイル (kikikai.zip の中に入る):
  a85-17.h16 a85-16.h18 a85-11.f6            ... メインCPU / サブCPU のROM
  a85-15.a1 a85-14.a3 a85-13.a4 a85-12.a6    ... グラフィックROM
  a85-08.g15 a85-10.g12 a85-09.g14           ... カラーPROM (Clrtable.bin から作成。MAMEのCRC32と一致)
  a85-01_jph1020p.h8                         ... 代替MCU (自作。CRC32のみ 01771197 に調整)

使い方:  python3 make_kikikai_zip.py [入力フォルダ] [出力zip]
         (省略時: 入力フォルダ=カレント, 出力zip=kikikai.zip)

注意: 代替MCUは本物のダンプではなく、自作の代替品です(CRC32のみ調整)。
      MAME はCRC32とSHA1を照合するため、MCUはSHA1が一致せず警告が出る場合があります(起動は可能)。
"""
import sys, os, zlib, zipfile, types

# =====================================================================
# 1) プログラムROM  (MPU1ROM / MPU1BROM / MPU2ROM -> a85-17.h16, a85-16.h18, a85-11.f6)
# =====================================================================
def make_program_roms(mpu1, mpu1b, mpu2):
    if (len(mpu1), len(mpu1b), len(mpu2)) != (0x8000, 0x18000, 0x8000):
        raise SystemExit(f"サイズが想定と違います: MPU1ROM={len(mpu1):#x} MPU1BROM={len(mpu1b):#x} MPU2ROM={len(mpu2):#x}"
                         " (期待: 0x8000 / 0x18000 / 0x8000)")
    return {
        "a85-17.h16": mpu1 + mpu1b[0x10000:],     # 固定32KB + バンク後半32KB
        "a85-16.h18": mpu1b[:0x10000],            # バンク前半64KB
        "a85-11.f6":  mpu2,
    }

# =====================================================================
# 2) グラフィックROM  (PTRNIMG.BIN -> a85-15.a1, a85-14.a3, a85-13.a4, a85-12.a6)
#    Windows版は 1ピクセル=1バイト, 8x8タイル連続, 各タイルが90度回転。
#    MAME(kikikai.cpp)の charlayout: planes{0x20000*8, 0x20000*8+4, 0, 4}, ROMREGION_INVERT
# =====================================================================
def make_graphics_roms(pix):
    if len(pix) != 8192 * 64:
        raise SystemExit(f"PTRNIMG.BIN のサイズが想定と違います: {len(pix):#x} (期待: 0x80000)")
    XOFF = [3, 2, 1, 0, 11, 10, 9, 8]; YOFF = [y * 16 for y in range(8)]
    PLANES = [0x20000 * 8, 0x20000 * 8 + 4, 0, 4]
    reg = bytearray(0x40000)
    for t in range(8192):
        for y in range(8):
            for x in range(8):
                v = pix[t * 64 + x * 8 + (7 - y)] & 15      # MAME(x,y) <- Windows版(7-y, x)
                for pi, po in enumerate(PLANES):
                    if (v >> (3 - pi)) & 1:                  # plane0 が最上位ビット
                        n = t * 128 + YOFF[y] + XOFF[x] + po
                        reg[n >> 3] |= 0x80 >> (n & 7)
    out = bytes(b ^ 0xFF for b in reg)                       # ROMREGION_INVERT
    names = ["a85-15.a1", "a85-14.a3", "a85-13.a4", "a85-12.a6"]
    return {n: out[i * 0x10000:(i + 1) * 0x10000] for i, n in enumerate(names)}

# =====================================================================
# 3) カラーPROM  (Clrtable.bin -> a85-08.g15(赤), a85-10.g12(緑), a85-09.g14(青))
#    256バイトのまま、128バイト目以降は 0x00。
# =====================================================================
def make_proms(clr, size=256, fill_from=128):
    ent = [tuple(clr[i * 4:i * 4 + 4]) for i in range(len(clr) // 4)]      # 4バイト/色 (B,G,R,0)
    def rgb4(e): return (e[2] // 17, e[1] // 17, e[0] // 17)
    if len(ent) < 10 + 16 * 8:
        raise SystemExit(f"Clrtable.bin が小さすぎます ({len(clr)} バイト)")
    sets = [[rgb4(ent[10 + 16 * s + p]) for p in range(16)] for s in range(8)]
    R, G, B = (bytearray([0x00]) * size for _ in range(3))
    for code in range(16):
        s = sets[code % 8]
        for pen in range(16):
            r, g, b = s[pen]; i = code * 16 + pen
            if i < fill_from:
                R[i], G[i], B[i] = r, g, b
    return {"a85-08.g15": bytes(R), "a85-10.g12": bytes(G), "a85-09.g14": bytes(B)}

# =====================================================================
# 4) 代替MCU  (6801アセンブラを内蔵 -> a85-01_jph1020p.h8, CRC32を 01771197 に調整)
# =====================================================================
# ---- 最小限の6801アセンブラ ----
def _load_asm_module():
    m = types.ModuleType("asm6801")
    exec(compile(ASM6801_SOURCE, "asm6801", "exec"), m.__dict__)
    return m

def force_crc32(data, pos, target):
    """data[pos:pos+4] を書き換えて zlib.crc32(data) == target にする (GF(2)上の連立方程式を解く)"""
    base = bytearray(data); base[pos:pos + 4] = b"\0\0\0\0"
    c0 = zlib.crc32(base) & 0xFFFFFFFF
    cols = []
    for bit in range(32):
        t = bytearray(base); t[pos + bit // 8] |= 1 << (bit % 8)
        cols.append((zlib.crc32(t) & 0xFFFFFFFF) ^ c0)
    need = target ^ c0
    basis = []
    for i in range(32):
        val, comb = cols[i], 1 << i
        for pb, bv, bc in basis:
            if val >> pb & 1: val ^= bv; comb ^= bc
        if val: basis.append((val.bit_length() - 1, val, comb))
    sol = 0
    for pb, bv, bc in sorted(basis, key=lambda x: -x[0]):
        if need >> pb & 1: need ^= bv; sol ^= bc
    if need: raise ValueError("このCRC32には調整できません")
    out = bytearray(data); patch = bytearray(4)
    for bit in range(32):
        if sol >> bit & 1: patch[bit // 8] |= 1 << (bit % 8)
    out[pos:pos + 4] = patch
    assert zlib.crc32(out) & 0xFFFFFFFF == target
    return bytes(out)

def make_mcu(target_crc=0x01771197):
    ADJ = 0x0F00                                   # 未使用領域(MCUアドレス 0xFF00)の4バイトでCRCを調整
    out, _ = _load_asm_module().assemble(MCU_ASM, 0xF000)
    rom = bytearray([0x01] * 0x1000)               # 未使用領域は NOP
    for addr, val in out.items(): rom[addr - 0xF000] = val
    assert not any((a - 0xF000) in range(ADJ, ADJ + 4) for a in out), "調整領域が使用中です"
    return {"a85-01_jph1020p.h8": force_crc32(bytes(rom), ADJ, target_crc)}

# =====================================================================
# メイン
# =====================================================================
MAME_CRC = {  # MAME(kikikai)のCRC32。ここにあるものは一致確認を表示する
    "a85-17.h16": 0xC141D5AB, "a85-16.h18": 0x4094D750, "a85-11.f6": 0xCC3539DB,
    "a85-15.a1": 0xAEBC8C32, "a85-14.a3": 0xA9DF0453, "a85-13.a4": 0x3EEAF878, "a85-12.a6": 0x91E58067,
    "a85-08.g15": 0xD15F61A8, "a85-10.g12": 0x8FC3FA86, "a85-09.g14": 0xB931C94D,
}
NOTE = {"a85-01_jph1020p.h8": "自作の代替MCU(CRC32のみ調整)"}
ORDER = ["a85-17.h16", "a85-16.h18", "a85-11.f6", "a85-15.a1", "a85-14.a3", "a85-13.a4", "a85-12.a6",
         "a85-08.g15", "a85-10.g12", "a85-09.g14", "a85-01_jph1020p.h8"]
INPUTS = ["MPU1ROM.BIN", "MPU1BROM.BIN", "MPU2ROM.BIN", "Clrtable.bin", "PTRNIMG.BIN"]

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    dst = sys.argv[2] if len(sys.argv) > 2 else "kikikai.zip"
    missing = [n for n in INPUTS if not os.path.isfile(os.path.join(src, n))]
    if missing:
        sys.exit("入力ファイルが見つかりません: " + ", ".join(missing) + f"\n(探した場所: {os.path.abspath(src)})")
    rd = lambda n: open(os.path.join(src, n), "rb").read()
    files = {}
    print("プログラムROMを作成中..."); files.update(make_program_roms(rd("MPU1ROM.BIN"), rd("MPU1BROM.BIN"), rd("MPU2ROM.BIN")))
    print("グラフィックROMを作成中(数秒かかります)..."); files.update(make_graphics_roms(rd("PTRNIMG.BIN")))
    print("カラーPROMを作成中..."); files.update(make_proms(rd("Clrtable.bin")))
    print("代替MCUを作成中..."); files.update(make_mcu())
    print()
    for n in ORDER:
        crc = zlib.crc32(files[n]) & 0xFFFFFFFF
        if n in MAME_CRC: note = "MAMEと一致" if crc == MAME_CRC[n] else "MAMEと不一致"
        else: note = ""
        extra = NOTE.get(n, "")
        print(f"  {n:20s} {len(files[n]):6d} バイト  CRC32={crc:08x}  {note}{extra if not note else ''}")
    bad = [n for n in ("a85-17.h16", "a85-16.h18", "a85-11.f6", "a85-15.a1", "a85-14.a3", "a85-13.a4", "a85-12.a6")
           if zlib.crc32(files[n]) & 0xFFFFFFFF != MAME_CRC[n]]
    if bad: print("\n警告: 次のファイルがMAMEのCRC32と一致しません:", ", ".join(bad))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ORDER:
            zi = zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, files[n])
    print(f"\n{dst} を作成しました ({len(ORDER)} ファイル)")

# =====================================================================
# 内蔵データ (6801アセンブラ本体と、代替MCUのアセンブリソース)
# =====================================================================
ASM6801_SOURCE = r'''
OPS = {  # mnemonic: {mode: opcode}
 "ldaa":{"imm":0x86,"dir":0x96,"ext":0xB6,"idx":0xA6}, "ldab":{"imm":0xC6,"dir":0xD6,"ext":0xF6,"idx":0xE6},
 "staa":{"dir":0x97,"ext":0xB7,"idx":0xA7}, "stab":{"dir":0xD7,"ext":0xF7,"idx":0xE7},
 "ldx":{"imm":0xCE}, "lds":{"imm":0x8E}, "cmpa":{"imm":0x81,"dir":0x91}, "cmpb":{"imm":0xC1}, "cpx":{"imm":0x8C},
 "anda":{"imm":0x84,"dir":0x94}, "oraa":{"imm":0x8A,"dir":0x9A}, "suba":{"imm":0x80,"dir":0x90}, "adda":{"imm":0x8B}, "addb":{"imm":0xCB},
 "bra":{"rel":0x20}, "beq":{"rel":0x27}, "bne":{"rel":0x26}, "bhi":{"rel":0x22}, "bcc":{"rel":0x24}, "bcs":{"rel":0x25}, "bsr":{"rel":0x8D},
 "jsr":{"ext":0xBD}, "jmp":{"ext":0x7E},
 "rts":{"imp":0x39}, "coma":{"imp":0x43}, "asla":{"imp":0x48}, "lsra":{"imp":0x44}, "rti":{"imp":0x3B}, "nop":{"imp":0x01}, "sei":{"imp":0x0F}, "clra":{"imp":0x4F}, "clrb":{"imp":0x5F},
 "inx":{"imp":0x08}, "dex":{"imp":0x09}, "inca":{"imp":0x4C}, "incb":{"imp":0x5C}, "decb":{"imp":0x5A}, "deca":{"imp":0x4A},
 "tab":{"imp":0x16}, "tba":{"imp":0x17}, "tsta":{"imp":0x4D}, "tstb":{"imp":0x5D}, "abx":{"imp":0x3A},
 "psha":{"imp":0x36}, "pula":{"imp":0x32}, "pshb":{"imp":0x37}, "pulb":{"imp":0x33},
}
def assemble(src, org):
    lines=[]; labels={}; pc=org
    items=[]
    for raw in src.splitlines():
        t=raw.split(";")[0].strip()
        if not t: continue
        if t.endswith(":"): labels[t[:-1]]=pc; continue
        if t.lower().startswith(".org"): pc=int(t.split()[1].replace("$","0x"),0); items.append(("org",pc)); continue
        if t.lower().startswith(".byte"):
            vals=[int(x.strip().replace("$","0x"),0) for x in t[5:].split(",")]
            items.append(("raw",pc,bytes(vals))); pc+=len(vals); continue
        if t.lower().startswith(".word"):
            toks=[x.strip() for x in t[5:].split(",")]
            items.append(("word",pc,toks)); pc+=2*len(toks); continue
        parts=t.split(None,1); m=parts[0].lower(); arg=parts[1].strip() if len(parts)>1 else None
        modes=OPS[m]
        if arg is None: mode="imp"; size=1
        elif m in("bra","beq","bne","bhi","bcc","bcs","bsr"): mode="rel"; size=2
        elif arg.startswith("#"): mode="imm"; size=3 if m in("ldx","lds","cpx") else 2
        elif arg.lower().endswith(",x"): mode="idx"; size=2
        else:
            mode="ext" if ("ext" in modes and ("dir" not in modes or arg[0].isalpha() or int(arg.replace("$","0x"),0)>0xff)) else "dir"
            if m in("jsr","jmp"): mode="ext"
            size=3 if mode=="ext" else 2
        items.append(("ins",pc,m,mode,arg)); pc+=size
    out={}
    def val(s):
        s=s.strip()
        if s.startswith("#"): s=s[1:]
        if s.lower().endswith(",x"): s=s[:-2]
        if s[0] in "<>":   # <label=下位, >label=上位
            v=val(s[1:]); return v&0xff if s[0]=="<" else v>>8
        if s in labels: return labels[s]
        return int(s.replace("$","0x"),0)
    for it in items:
        if it[0]=="org": continue
        if it[0]=="raw":
            for i,b in enumerate(it[2]): out[it[1]+i]=b
        elif it[0]=="word":
            for i,tk in enumerate(it[2]):
                v=val(tk); out[it[1]+2*i]=v>>8; out[it[1]+2*i+1]=v&0xff
        else:
            _,p,m,mode,arg=it; op=OPS[m][mode]; out[p]=op
            if mode=="imp": continue
            if mode=="rel":
                d=labels[arg]-(p+2)
                assert -128<=d<=127,(m,arg,d)
                out[p+1]=d&0xff
            elif mode in("imm","dir","idx"):
                v=val(arg)
                if mode=="imm" and m in("ldx","lds","cpx"): out[p+1]=(v>>8)&0xff; out[p+2]=v&0xff
                else: out[p+1]=v&0xff
            elif mode=="ext":
                v=val(arg); out[p+1]=v>>8; out[p+2]=v&0xff
    return out, labels
'''

MCU_ASM = r'''
; KiKi KaiKai 代替MCU 試作v2  (MC6801U4 内蔵ROM 4KB, 0xF000-0xFFFF)
; 根拠: MAME kikikai.cpp(MCUポート配線) / KKKAIKAI.exe(Windows版のMCU相当処理) / Z80 ROM(a85-17,16)の解析
;  P1: 入力=コイン(bit0,1が1=押下)  出力 bit4,5=コインロックアウト
;  P2: bit0=読出し先(1:共有RAM 0:入力ポート) bit2=クロック(1->0で実行) bit4=方向(1:読出し 0:書込み)
;  P3: データ  P4: 共有RAM(0xE800+)の下位アドレス
; 内部RAM使用: $80-$81 WR用 / $84-$86 コマンド・入力 / $87-$88 コイン / $8A-$8B 入力ビット入替
;              $8C-$8D ミラー / $91-$99 当たり判定 / $9A-$9E 範囲判定 / $A0-$A7 敵データ / $B0-$B9 E890-E899の影 (E8E0コマンド応答は E8E1-E8EF)
.org $F000
START:
  sei
  lds #$00FF
  clra
  ldx #$00B0
  ldab #10
INITLP:
  staa 0,x
  inx
  decb
  bne INITLP
  staa $87
  ldaa #$FF
  staa $01        ; DDR2 全ビット出力
  staa $05        ; DDR4 全ビット出力 (共有RAMアドレス)
  ldaa #$B0
  staa $00        ; DDR1: bit4,5,7 出力
  ldaa #$30
  staa $02        ; ロックアウト解除
  ldaa #$04
  staa $03
LOOP:
  jsr CMDSVC
  jsr COINSVC
  jsr INPSVC
  jsr CONSTS
  jsr DUPB
  jsr MIRROR
  jsr COLLIDE
  jmp LOOP

; ---------- コマンド E8E0 (1..3 で15バイトのテーブルを E8E1-E8EF へ返し、E8E0=FF で応答) ----------
CMDSVC:
  ldab #$E0
  jsr RD
  cmpa #$FF
  beq CMDEND
  tsta
  beq CMDEND
  cmpa #$01
  bcs CMDEND
  cmpa #$03
  bhi CMDEND
  staa $84
  ldx #TABLE
  deca
  beq COPY
ADDLP:
  ldab #15
  abx
  deca
  bne ADDLP
COPY:
  clra
  staa $85
CPLP:
  ldaa 0,x
  ldab $85
  addb #$E1
  jsr WR
  inx
  ldaa $85
  inca
  staa $85
  cmpa #15
  bne CPLP
  ldaa #$FF
  ldab #$E0
  jsr WR
CMDEND:
  rts

; ---------- コイン: P1 bit0/1 の立ち上がりで E801(クレジット)+1, E80A=1 ----------
COINSVC:
  ldaa $02
  anda #$03
  staa $88
  ldaa $87
  coma
  anda $88
  beq COINEND
  ldab #$01
  jsr RD
  cmpa #$63
  bcc COINSND
  inca
  ldab #$01
  jsr WR
COINSND:
  ldaa #$01
  ldab #$0A
  jsr WR
COINEND:
  ldaa $88
  staa $87
  rts

; ---------- 入力 (左右ビットを入替えて E802/E81B/E803 へ) ----------
INPSVC:
  ldab #$00
  jsr RDIN
  jsr SWAP
  staa $86
  ldab #$02
  jsr WR
  ldaa $86
  ldab #$1B
  jsr WR
  ldab #$01
  jsr RDIN
  jsr SWAP
  ldab #$03
  jsr WR
  rts
SWAP:               ; bit2 <-> bit3
  staa $8A
  anda #$F3
  staa $8B
  ldaa $8A
  anda #$04
  asla
  oraa $8B
  staa $8B
  ldaa $8A
  anda #$08
  lsra
  oraa $8B
  rts

; ---------- 定数 ----------
CONSTS:
  ldaa #$03
  ldab #$07
  jsr WR
  ldaa #$B3
  ldab #$F1
  jsr WR
  ldaa #$FF
  ldab #$06
  jsr WR
  ldaa #$FF
  ldab #$D0
  jsr WR
  ldaa #$FF
  ldab #$F0
  jsr WR
  rts

; ---------- E8B0-E8BE(偶数)の書込みを次のバイトにも複製 ----------
DUPB:
  clra
  staa $8C
DLP:
  ldab $8C
  addb #$B0
  jsr RD
  ldab $8C
  addb #$B1
  jsr WR
  ldaa $8C
  adda #$02
  staa $8C
  cmpa #16
  bne DLP
  rts

; ---------- E890-E899 が変化したら E8C0+n = 値+2 ----------
MIRROR:
  clra
  staa $8C
MLP:
  ldab $8C
  addb #$90
  jsr RD
  staa $8D
  ldx #$00B0
  ldab $8C
  abx
  ldaa 0,x
  cmpa $8D
  beq MNEXT
  ldaa $8D
  staa 0,x
  adda #$02
  ldab $8C
  addb #$C0
  jsr WR
MNEXT:
  ldaa $8C
  inca
  staa $8C
  cmpa #10
  bne MLP
  rts

; ---------- 当たり判定: 自機(E8A0,E8A1)と敵7体(E820+8n)。命中で E8A2=FF ----------
COLLIDE:
  ldab #$A0
  jsr RD
  staa $98
  ldab #$A1
  jsr RD
  staa $99
  ldaa #$20
  staa $91
  ldaa #7
  staa $92
CLP:
  jsr READENT
  jsr TESTENT
  tsta
  beq CNEXT
  ldaa #$FF
  ldab #$A2
  jsr WR
  rts
CNEXT:
  ldaa $91
  adda #$08
  staa $91
  ldaa $92
  deca
  staa $92
  bne CLP
  rts
READENT:
  ldab $91
  jsr RD
  staa $A0
  ldab $91
  addb #$01
  jsr RD
  staa $A1
  ldab $91
  addb #$02
  jsr RD
  staa $A2
  ldab $91
  addb #$03
  jsr RD
  staa $A3
  ldab $91
  addb #$04
  jsr RD
  staa $A4
  ldab $91
  addb #$05
  jsr RD
  staa $A5
  ldab $91
  addb #$06
  jsr RD
  staa $A6
  ldab $91
  addb #$07
  jsr RD
  staa $A7
  rts
TESTENT:
  ldaa $A0
  cmpa #$0A
  bne T2CHK
  ldaa $A1
  cmpa #$0B
  bne T2CHK
  ldaa $A2
  cmpa #$04
  bne T2CHK
  ldaa $A3
  cmpa #$03
  bne T2CHK
  ldaa #5
  staa $93
  ldaa #13
  staa $94
  ldaa #7
  staa $95
  ldaa #13
  staa $96
  jmp DOTEST
T2CHK:
  ldaa $A0
  cmpa #$08
  bne T3CHK
  ldaa $A1
  cmpa #$0B
  bne T3CHK
  ldaa $A2
  cmpa #$08
  bne T3CHK
  ldaa $A3
  cmpa #$06
  bne T3CHK
  ldaa #1
  staa $93
  ldaa #14
  staa $94
  ldaa #4
  staa $95
  ldaa #16
  staa $96
  jmp DOTEST
T3CHK:
  ldaa $A0
  cmpa #$0B
  bne NOHIT
  ldaa $A1
  cmpa #$10
  bne NOHIT
  ldaa $A2
  cmpa #$FD
  bne NOHIT
  ldaa $A3
  cmpa #$FF
  bne NOHIT
  ldaa #10
  staa $93
  ldaa #4
  staa $94
  ldaa #16
  staa $95
  ldaa #14
  staa $96
DOTEST:
  ldaa $A4
  staa $9A
  ldaa $A5
  staa $9B
  ldaa $98
  staa $9C
  ldaa $93
  staa $9D
  ldaa $94
  staa $9E
  jsr CHK
  tsta
  beq NOHIT
  ldaa $A6
  staa $9A
  ldaa $A7
  staa $9B
  ldaa $99
  staa $9C
  ldaa $95
  staa $9D
  ldaa $96
  staa $9E
  jsr CHK
  rts
NOHIT:
  clra
  rts
; 範囲判定: 敵座標(16bit: $9A:$9B) - 自機(8bit: $9C) が -$9D 以上 +$9E 以下なら A=1
CHK:
  ldaa $9A
  bne CHKMISS
  ldaa $9B
  cmpa $9C
  bcs CHKNEG
  suba $9C
  cmpa $9E
  bhi CHKMISS
  bra CHKHIT
CHKNEG:
  ldaa $9C
  suba $9B
  cmpa $9D
  bhi CHKMISS
CHKHIT:
  ldaa #$01
  rts
CHKMISS:
  clra
  rts

; ---------- 共有RAM/入力アクセス ----------
WR:                 ; A=値 B=アドレス下位
  staa $80
  stab $81
  ldaa #$FF
  staa $04
  ldaa $81
  staa $07
  ldaa $80
  staa $06
  ldaa #$04
  staa $03
  ldaa #$00
  staa $03
  rts
RD:                 ; B=アドレス下位 -> A
  clra
  staa $04
  stab $07
  ldaa #$04
  staa $03
  ldaa #$11
  staa $03
  ldaa $06
  rts
RDIN:               ; B=0/1 -> A=IN1/IN2
  clra
  staa $04
  stab $07
  ldaa #$04
  staa $03
  ldaa #$10
  staa $03
  ldaa $06
  rts

.org $F600
TABLE:
  .byte $40,$48,$50,$58,$60,$68,$70,$78,$80,$88,$00,$00,$00,$00,$00
  .byte $04,$08,$0C,$10,$14,$18,$1C,$20,$31,$2B,$35,$00,$00,$00,$00
  .byte $0C,$0D,$0E,$0F,$10,$11,$12,$03,$0A,$0B,$14,$00,$00,$00,$00
.org $F700
DUMMYISR:
  rti
.org $FFF0
  .word DUMMYISR,DUMMYISR,DUMMYISR,DUMMYISR,DUMMYISR,DUMMYISR,DUMMYISR,START
'''

if __name__ == "__main__":
    main()
