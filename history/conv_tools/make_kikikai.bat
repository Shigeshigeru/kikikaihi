Echo off
REM メディアカイト版奇々怪界からのROM抽出バッチ

REM MPUROMとか作成
python3 Split_mpu_roms.py

REM カラーPROM作成
python3 make_proms.py Clrtable.bin

REM グラヒックROM作成
python3 ptrn_to_mame_kikikai.py PTRNIMG.BIN .

REM 代替MCU作成
python3 make_mcu_rom.py 01771197 a85-01_jph1020p.h8

Echo 作成されたa85から始まるファイルをkikikai.zipにまとめてください
pause