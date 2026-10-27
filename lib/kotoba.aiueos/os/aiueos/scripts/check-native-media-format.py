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

def verify_iso(image,disk,efi):
 # Parse ISO9660 and the EFI El Torito catalog independently of the native
 # writer, then compare its complete FAT16 image with the qualified GPT ESP.
 disk_result=verify(disk,efi)
 d=disk.read_bytes();start,end=disk_result['partition']
 boot=d[start*512:(end+1)*512]
 iso=image.read_bytes();block=2048
 assert len(iso)%block==0 and len(iso)>=24*block
 pvd=iso[16*block:17*block];brvd=iso[17*block:18*block]
 term=iso[18*block:19*block]
 assert pvd[:7]==b'\x01CD001\x01' and brvd[:7]==b'\x00CD001\x01'
 assert term[:7]==b'\xffCD001\x01'
 assert brvd[7:39].rstrip(b'\x00')==b'EL TORITO SPECIFICATION'
 assert struct.unpack_from('<I',pvd,80)[0]==len(iso)//block
 assert struct.unpack_from('>I',pvd,84)[0]==len(iso)//block
 assert struct.unpack_from('<H',pvd,128)[0]==block
 assert struct.unpack_from('>H',pvd,130)[0]==block
 catalog_lba=struct.unpack_from('<I',brvd,71)[0]
 catalog=iso[catalog_lba*block:(catalog_lba+1)*block]
 assert len(catalog)==block and catalog[0:2]==b'\x01\xef'
 assert catalog[30:32]==b'\x55\xaa'
 assert sum(struct.unpack_from('<16H',catalog))%65536==0
 entry=catalog[32:64]
 assert entry[:2]==b'\x88\x00'
 sectors=struct.unpack_from('<H',entry,6)[0]
 image_lba=struct.unpack_from('<I',entry,8)[0]
 assert sectors==len(boot)//512 and image_lba>=23
 assert len(boot)==sectors*512
 payload=iso[image_lba*block:image_lba*block+len(boot)]
 assert payload==boot
 assert iso[image_lba*block+len(boot):]==bytes(len(iso)-(image_lba*block+len(boot)))
 root_lba=struct.unpack_from('<I',pvd,158)[0]
 root=iso[root_lba*block:(root_lba+1)*block]
 records=[];at=0
 while at<len(root) and root[at]:
  record=root[at:at+root[at]];assert len(record)==root[at]
  records.append(record);at+=len(record)
 assert len(records)>=3
 file_record=records[2]
 assert file_record[33:33+file_record[32]]==b'ESP.IMG;1'
 assert struct.unpack_from('<I',file_record,2)[0]==image_lba
 assert struct.unpack_from('<I',file_record,10)[0]==len(boot)
 return dict(status='PASS_INDEPENDENT_NATIVE_EL_TORITO_ISO_READBACK',
             iso=dict(bytes=len(iso),sha256=hashlib.sha256(iso).hexdigest()),
             bootImage=dict(bytes=len(boot),sha256=hashlib.sha256(boot).hexdigest()),
             gpt=disk_result['image'],formatEmission=False,release=False,physicalHardware=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--efi',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();r=verify(a.image,a.efi)
 if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n')
 print(r['status'])
