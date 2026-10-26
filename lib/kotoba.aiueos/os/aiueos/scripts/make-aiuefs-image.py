#!/usr/bin/env python3
import argparse, hashlib, struct
from pathlib import Path

RSA_MODULUS = int("B4C41B61169AAB3FE99E2E57E8DCC2A51D944BDB086DAE3F32F4DC99FD979FC1ED688CE0A3C4A4BB0B7E665E5E76C2D9C712FBF1116999B9A86A08C1D2EEAD216F7696B4B8AAF0DEA41FEA7CB8171232F919AB756317A76E6CE3AFAE713BD1BC4AEBABE0AD302A8A5F5838857A81795BE7140AB4F7AA52379E659E0644A85EB93083302D5FEF5EEBAA47746F141703D62AA83097CC97848A5A1F7729F2FB213DCAC7CE4E2C7770496872F4127546A023B62F0BE557DF6D3C2217FBB3A1FF516B7C368DB25F897314BABC61BFB5A96A71AFD0100BE026E3B0E7C77384E1F5949AFDFB66F58F2ABCEC893F8F7AB9F95E5718D52F1C2914D8D00C7E70890E40B8A3",16)

def fnv(data):
    value=2166136261
    for byte in data: value=((value^byte)*16777619)&0xffffffff
    return value

def verify_signature(data,signature):
    if len(signature)!=256: return False
    digest=hashlib.sha256(data).digest()
    info=bytes.fromhex("3031300d060960864801650304020105000420")+digest
    wanted=b"\0\1"+b"\xff"*(256-len(info)-3)+b"\0"+info
    actual=pow(int.from_bytes(signature,"big"),65537,RSA_MODULUS).to_bytes(256,"big")
    return actual==wanted

parser=argparse.ArgumentParser()
parser.add_argument("--entry",action="append",required=True,metavar="ID,ELF,SIGNATURE")
parser.add_argument("--catalog-signature",required=True)
parser.add_argument("--output",required=True)
args=parser.parse_args()
if not 1<=len(args.entry)<=4: raise SystemExit("aiuefs catalog supports one to four apps")
apps=[]; next_sector=4
for specification in args.entry:
    parts=specification.split(",",2)
    if len(parts)!=3: raise SystemExit("entry must be ID,ELF,SIGNATURE")
    identity=parts[0].encode("ascii"); data=Path(parts[1]).read_bytes(); signature=Path(parts[2]).read_bytes()
    if not identity or len(identity)>15 or b"\0" in identity: raise SystemExit("app id must be 1..15 ASCII bytes")
    if not data or len(data)>98304 or not verify_signature(data,signature): raise SystemExit("app extent or RSA signature is invalid")
    data_sector=next_sector; signature_sector=data_sector+(len(data)+511)//512
    next_sector=signature_sector+1
    apps.append((identity,data,signature,data_sector,signature_sector))
catalog_sector=next_sector
entries=b"".join(struct.pack("<16sII32sII",identity,data_sector,len(data),hashlib.sha256(data).digest(),signature_sector,1)
                 for identity,data,_,data_sector,signature_sector in apps)
catalog=struct.pack("<8sII",b"AIUCAT1\0",1,len(apps))+entries
catalog_signature=Path(args.catalog_signature).read_bytes()
if len(catalog)>512 or not verify_signature(catalog,catalog_signature): raise SystemExit("catalog RSA signature is invalid")
catalog_signature_sector=catalog_sector+1
root=b"KOTOBASE-ROOT-V1"; image=bytearray(1024*1024)
header=struct.pack("<8s9I32s2I24s",b"AIUEFS1\0",3,108,1+len(apps),0,128,len(root),fnv(root),
                   catalog_sector,len(catalog),hashlib.sha256(catalog).digest(),catalog_signature_sector,1,bytes(24))
image[:len(header)]=header; image[128:128+len(root)]=root
for _,data,signature,data_sector,signature_sector in apps:
    image[data_sector*512:data_sector*512+len(data)]=data
    image[signature_sector*512:signature_sector*512+256]=signature
image[catalog_sector*512:catalog_sector*512+len(catalog)]=catalog
image[catalog_signature_sector*512:catalog_signature_sector*512+256]=catalog_signature
Path(args.output).write_bytes(image)
