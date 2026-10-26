#!/usr/bin/env python3
"""Independent GPT/FAT16 reader; never emits a disk or EFI format."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid
import zlib

def verify(image,efi):
 d=image.read_bytes();expected=efi.read_bytes();assert len(d)%512==0 and len(d)>=4194304
 sectors=len(d)//512;u=lambda at,fmt:struct.unpack_from('<'+fmt,d,at)
 assert d[510:512]==b'\x55\xaa' and d[450]==0xee and u(454,'II')==(1,sectors-1)
 headers=[]
 for lba,other in [(1,sectors-1),(sectors-1,1)]:
  at=lba*512;h=d[at:at+92];assert h[:8]==b'EFI PART' and u(at+8,'II')==(0x10000,92)
  c=bytearray(h);c[16:20]=bytes(4);assert zlib.crc32(c)==u(at+16,'I')[0]
  assert u(at+20,'I')==(0,) and u(at+24,'QQ')==(lba,other)
  first,last=u(at+40,'QQ');entry_lba,count,size,crc=u(at+72,'QIII')
  assert 34<=first<=last<sectors-1 and count==128 and size==128
  table=d[entry_lba*512:entry_lba*512+count*size];assert len(table)==count*size and zlib.crc32(table)==crc
  headers.append((h,table))
 assert headers[0][0][40:72]==headers[1][0][40:72] and headers[0][1]==headers[1][1]
 entry=headers[0][1][:128];assert uuid.UUID(bytes_le=entry[:16])==uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b')
 start,end,attrs=struct.unpack_from('<QQQ',entry,32);assert first<=start<=end<=last and attrs==0
 assert headers[0][1][128:]==bytes(127*128)
 at=start*512;bps,spc,reserved,fats,roots,total16,media,fatsz=struct.unpack_from('<HBHBHHBH',d,at+11)
 assert bps==512 and spc in (1,2,4,8,16,32,64,128) and reserved>=1 and fats==2 and fatsz>0
 total=total16 or u(at+32,'I')[0];assert total==end-start+1 and u(at+28,'I')[0]==start
 assert d[at+510:at+512]==b'\x55\xaa' and d[at+54:at+62]==b'FAT16   '
 root_sectors=(roots*32+511)//512;data_lba=start+reserved+fats*fatsz+root_sectors
 clusters=(total-reserved-fats*fatsz-root_sectors)//spc;assert 4085<=clusters<65525
 fat=d[(start+reserved)*512:(start+reserved+fatsz)*512]
 assert fat==d[(start+reserved+fatsz)*512:(start+reserved+2*fatsz)*512]
 assert struct.unpack_from('<HH',fat)==(0xff00|media,0xffff)
 def cluster(n):
  assert 2<=n<clusters+2
  base=(data_lba+(n-2)*spc)*512;return d[base:base+spc*512]
 def find(data,name):
  entries=[data[i:i+32] for i in range(0,len(data),32) if data[i] not in (0,0xe5) and data[i+11]!=0x0f]
  match=[e for e in entries if e[:11]==name];assert len(match)==1;return match[0]
 root=d[(start+reserved+fats*fatsz)*512:data_lba*512]
 e=find(root,b'EFI        ');assert e[11]==16
 e=find(cluster(struct.unpack_from('<H',e,26)[0]),b'BOOT       ');assert e[11]==16
 e=find(cluster(struct.unpack_from('<H',e,26)[0]),b'BOOTX64 EFI');assert e[11]==32
 n=struct.unpack_from('<I',e,28)[0];assert n==len(expected)
 current=struct.unpack_from('<H',e,26)[0];seen=set();parts=[]
 while current<0xfff8:
  assert current not in seen;seen.add(current);parts.append(cluster(current));current=struct.unpack_from('<H',fat,current*2)[0]
 assert len(parts)==(n+spc*512-1)//(spc*512)
 content=b''.join(parts);assert content[:n]==expected and content[n:]==bytes(len(content)-n)
 return dict(status='PASS_INDEPENDENT_NATIVE_GPT_FAT16_READBACK',image=dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest()),efi=dict(bytes=n,sha256=hashlib.sha256(expected).hexdigest()),partition=[start,end],fileClusters=len(parts),formatEmission=False,installer=False,physicalHardware=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--efi',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();r=verify(a.image,a.efi)
 if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n')
 print(r['status'])
