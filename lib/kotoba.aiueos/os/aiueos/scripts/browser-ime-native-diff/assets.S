# The kernel's font and dictionary (the initramfs's), for the browser native differentials (JUN-708); run.sh puts in
# their paths. 4 KiB of zeros follow each, so a read a little past either is the same for both objects.
.section .rodata
.balign 64
.globl font_blob, font_blob_end, dict_blob, dict_blob_end
font_blob:
.incbin "@FONT@"
font_blob_end:
.skip 4096
.balign 64
dict_blob:
.incbin "@DICT@"
dict_blob_end:
.skip 4096
