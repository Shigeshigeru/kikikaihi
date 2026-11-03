一括変換してkikikai.zipにまとめるスクリプト、make_kikikai_zip.pyを作りました。あわせて、バッチファイルの簡略版(make_kikikai.bat)もお渡しします。

使い方
次の5つの入力ファイルを、スクリプトと同じフォルダに置いて、実行します。

MPU1ROM.BIN
MPU1BROM.BIN
MPU2ROM.BIN
Clrtable.bin
PTRNIMG.BIN
python3 make_kikikai_zip.py . kikikai.zip

入力フォルダとzipの名前は、省略できます(省略時は、カレントフォルダとkikikai.zip)。バッチファイルのほうは、ダブルクリックで同じ処理が走ります。

スクリプトの内容
これまでに作った処理は、すべて1つのファイルに入れてあります。他のスクリプト(split_mpu_roms.py、make_proms.py、ptrn_to_mame_kikikai.py、make_mcu_rom.py、asm6801.py)や、アセンブリのソースは、不要です。zipの中身は、a85から始まる11ファイルです。

種類	ファイル
プログラムROM	a85-17.h16、a85-16.h18、a85-11.f6
グラフィックROM	a85-15.a1、a85-14.a3、a85-13.a4、a85-12.a6
カラーPROM	a85-08.g15、a85-10.g12、a85-09.g14
代替MCU	a85-01_jph1020p.h8

確認できたこと
お手元のファイルで試したところ、次の結果でした。

11ファイルすべてが、これまで個別のスクリプトで作ったファイルと、同一でした。
zipの検査も、問題ありませんでした。
入力ファイルが足りないときは、足りないファイルの名前を表示して止まります。

注目してほしい点
カラーPROM3本のCRC32が、MAMEの値(d15f61a8、8fc3fa86、b931c94d)と一致しました。Clrtable.binから作ったPROMは、MAME用のオリジナルのPROMと同じ内容と考えてよさそうです(SHA1は確認していません)。プログラムROMとグラフィックROMも、すべてMAMEのCRC32と一致しています。MAMEのCRC32と一致しないのは、代替MCUだけです。

注意
代替MCUは、自作の代替品です。CRC32は01771197に合わせてありますが、SHA1は一致しないので、MAMEが警告を出す場合があります。起動して動くことは、確認済みです。