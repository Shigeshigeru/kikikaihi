"""最小限の6801アセンブラ(今回使う命令だけ)"""
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
