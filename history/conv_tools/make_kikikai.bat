Echo off
REM メディアカイト版奇々怪界からのROM抽出バッチ
REM 同じフォルダに MPU1ROM.BIN MPU1BROM.BIN MPU2ROM.BIN Clrtable.bin PTRNIMG.BIN を置いて実行

python3 make_kikikai_zip.py . kikikai.zip

pause
