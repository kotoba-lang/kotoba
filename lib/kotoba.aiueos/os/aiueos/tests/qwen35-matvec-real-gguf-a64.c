#define _DARWIN_C_SOURCE 1
#include <stdint.h>
int aiueos_qwen35_dequantize_row(uint32_t type, const uint8_t *data,
                                  uint64_t elements, float *output);
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <sys/mman.h>
#include <unistd.h>
#include <sys/types.h>

/* Full Bonsai blk.0.ffn_down.weight: GGUF [17408, 5120], PTQ1_0. */
typedef uint64_t (*Matvec)(uint64_t,uint64_t,uint64_t,uint64_t);
#define ROWS 5120U
#define COLS 17408U
#define BLOCKS (COLS/128U)
#define ROW_BYTES (BLOCKS*28U)
#define REPEATS 4U
#define SAMPLES 7U
static uint32_t rng=0x13579bdfU;
static uint32_t next_u32(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void wr32(uint8_t*p,uint32_t v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static void plan32(uint8_t*p,uint32_t o,uint32_t v){wr32(p+o,v);}
static void plan64(uint8_t*p,uint32_t o,uint64_t v){wr32(p+o,(uint32_t)v);wr32(p+o+4,(uint32_t)(v>>32));}
static float dot_scalar(const float*a,const float*b,uint64_t n){float s0=0,s1=0,s2=0,s3=0;uint64_t i=0;for(;i+4<=n;i+=4){s0+=a[i]*b[i];s1+=a[i+1]*b[i+1];s2+=a[i+2]*b[i+2];s3+=a[i+3]*b[i+3];}float s=(s0+s1)+(s2+s3);for(;i<n;i++)s+=a[i]*b[i];return s;}
static int c_matvec(const uint8_t*w,const float*in,float*out,float*row){for(uint32_t r=0;r<ROWS;r++){if(!aiueos_qwen35_dequantize_row(143,w+(uint64_t)r*ROW_BYTES,COLS,row))return 0;out[r]=dot_scalar(row,in,COLS);}return 1;}
/* KEXE hidden metering context: x7 points at a block with fuel at +8. */
static uint64_t call_kotoba(Matvec fn,uint64_t a0,uint64_t a1,uint64_t a2,uint64_t a3,uint64_t*ctx){
 register uint64_t x0 __asm__("x0")=a0,x1 __asm__("x1")=a1,x2 __asm__("x2")=a2,x3 __asm__("x3")=a3;
 register uint64_t x7 __asm__("x7")=(uint64_t)(uintptr_t)ctx; register Matvec x16 __asm__("x16")=fn;
 __asm__ volatile("blr x16" : "+r"(x0),"+r"(x1),"+r"(x2),"+r"(x3),"+r"(x7),"+r"(x16) :: "x4","x5","x6","x8","x9","x10","x11","x12","x13","x14","x15","x17","x30","memory","cc"); return x0;
}
static Matvec load_code(const char*path,uint64_t offset,void**mapping,size_t*map_len){FILE*f=fopen(path,"rb");if(!f){perror("fopen code");exit(2);}fseek(f,0,SEEK_END);long z=ftell(f);rewind(f);if(z<=0||offset>=(uint64_t)z){fprintf(stderr,"bad code size/offset\n");exit(2);}long p=sysconf(_SC_PAGESIZE);size_t n=(size_t)z,rounded=(n+(size_t)p-1)/(size_t)p*(size_t)p;uint8_t*m=mmap(NULL,rounded,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);if(m==MAP_FAILED){perror("mmap");exit(2);}if(fread(m,1,n,f)!=n){fprintf(stderr,"short code read\n");exit(2);}fclose(f);if(mprotect(m,rounded,PROT_READ|PROT_EXEC)){perror("mprotect");exit(2);}*mapping=m;*map_len=rounded;return (Matvec)(void*)(m+offset);}
static uint64_t kotoba_matvec(Matvec fn,uint8_t*arena,uint64_t arena_bytes,uint8_t*plan,uint64_t*ctx){uint64_t ptr=(uint64_t)(uintptr_t)arena;for(uint32_t first=0;first<ROWS;){uint32_t end=first+120U;if(end>ROWS)end=ROWS;plan64(plan,64,first);plan64(plan,72,end);ctx[1]=UINT64_C(9007199254740991);uint64_t rc=call_kotoba(fn,ptr,arena_bytes,(uint64_t)(uintptr_t)plan,96,ctx);if(rc)return rc;first=end;}return 0;}
static uint64_t now_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000ULL+(uint64_t)t.tv_nsec;}
static double timed_c(const uint8_t*w,const float*in,float*out,float*row){uint64_t t0=now_ns();for(uint32_t i=0;i<REPEATS;i++)if(!c_matvec(w,in,out,row))exit(7);return (now_ns()-t0)/1e6;}
static double timed_k(Matvec fn,uint8_t*arena,uint64_t arena_bytes,uint8_t*plan,uint64_t*ctx){uint64_t t0=now_ns();for(uint32_t i=0;i<REPEATS;i++)if(kotoba_matvec(fn,arena,arena_bytes,plan,ctx))exit(8);return (now_ns()-t0)/1e6;}
static double median(double a[SAMPLES]){for(uint32_t i=0;i<SAMPLES;i++)for(uint32_t j=i+1;j<SAMPLES;j++)if(a[j]<a[i]){double t=a[i];a[i]=a[j];a[j]=t;}return a[SAMPLES/2];}
static void read_weights(const char*path,uint64_t offset,uint8_t*w,uint64_t bytes){FILE*f=fopen(path,"rb");if(!f){perror("fopen GGUF");exit(2);}if(fseeko(f,(off_t)offset,SEEK_SET)){perror("seek GGUF tensor");exit(2);}if(fread(w,1,(size_t)bytes,f)!=(size_t)bytes){fprintf(stderr,"short GGUF tensor read\n");exit(2);}fclose(f);}
int main(int argc,char**argv){if(argc!=5){fprintf(stderr,"usage: bench code.bin entry-offset GGUF tensor-absolute-offset\n");return 2;}uint64_t tensor_offset=strtoull(argv[4],NULL,10);void*mapping;size_t mapping_len;Matvec fn=load_code(argv[1],strtoull(argv[2],NULL,10),&mapping,&mapping_len);uint64_t wb=(uint64_t)ROWS*ROW_BYTES,ib=(uint64_t)COLS*4U,ob=(uint64_t)ROWS*4U,io=wb,oo=io+ib,so=oo+ob,total=so+ib;uint8_t*arena=calloc(1,(size_t)total);uint8_t plan[96]={0};uint64_t ctx[8]={0};float*in=(float*)(void*)(arena+io),*out=(float*)(void*)(arena+oo),*row=(float*)malloc((size_t)ib),*native_out=(float*)malloc((size_t)ob);if(!arena||!row||!native_out)return 2;uint8_t*w=arena;read_weights(argv[3],tensor_offset,w,wb);for(uint64_t i=0;i<ib/4;i++)in[i]=((int32_t)(next_u32()>>8)-8388608)/8388608.0f;plan32(plan,0,143);plan64(plan,8,ROWS);plan64(plan,16,COLS);plan64(plan,24,0);plan64(plan,32,wb);plan64(plan,40,io);plan64(plan,48,oo);plan64(plan,56,so);plan64(plan,64,0);plan64(plan,72,ROWS);if(kotoba_matvec(fn,arena,total,plan,ctx))return 3;memcpy(native_out,out,(size_t)ob);if(!c_matvec(w,in,out,row))return 4;double maxdiff=0;for(uint32_t i=0;i<ROWS;i++){double d=fabs((double)out[i]-native_out[i]);if(d>maxdiff)maxdiff=d;}if(maxdiff!=0){fprintf(stderr,"parity failed maxdiff=%.9g\n",maxdiff);return 5;}for(int i=0;i<2;i++){(void)timed_c(w,in,out,row);(void)timed_k(fn,arena,total,plan,ctx);}double cs[SAMPLES],ks[SAMPLES];for(uint32_t i=0;i<SAMPLES;i++){if(i&1U){ks[i]=timed_k(fn,arena,total,plan,ctx);cs[i]=timed_c(w,in,out,row);}else{cs[i]=timed_c(w,in,out,row);ks[i]=timed_k(fn,arena,total,plan,ctx);}printf("sample=%u C-ms=%.3f Kotoba-ms=%.3f\n",i+1,cs[i],ks[i]);}double cm=median(cs),km=median(ks);printf("M4_BONSAI_REAL_PTQ1_MATVEC tensor=blk.0.ffn_down.weight rows=%u cols=%u repeats=%u samples=%u tensor-absolute-offset=%llu tensor-bytes=%llu median-C-ms=%.3f median-Kotoba-ms=%.3f Kotoba-throughput-vs-C=%.3fx parity-maxdiff=%.9g total-elements=%.0f\n",ROWS,COLS,REPEATS,SAMPLES,(unsigned long long)tensor_offset,(unsigned long long)wb,cm,km,cm/km,maxdiff,(double)ROWS*COLS*REPEATS);free(native_out);free(row);free(arena);munmap(mapping,mapping_len);return 0;}
