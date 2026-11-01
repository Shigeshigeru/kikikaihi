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
