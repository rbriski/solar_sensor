#pragma once
#include <cstddef>
#include <cstring>
using nvs_handle_t=int;
using esp_err_t=int;
constexpr int ESP_OK=0, ESP_ERR_NVS_NOT_FOUND=1, NVS_READONLY=0, NVS_READWRITE=1;
inline unsigned writes=0;
inline bool present=false, fail=false;
inline unsigned char blob[512];
inline size_t blob_size=0;
inline int nvs_open(const char*,int mode,int *h) { *h=1; return fail?2:(!present && mode==0?1:0); }
inline int nvs_get_blob(int,const char*,void *out,size_t *size) {
 if(!present)return 1;
 if(*size<blob_size)return 2;
 memcpy(out,blob,blob_size);*size=blob_size;return 0;
}
inline int nvs_set_blob(int,const char*,const void *in,size_t size) {
 memcpy(blob,in,size);blob_size=size;present=true;++writes;return 0;
}
inline int nvs_commit(int) {return 0;}
inline void nvs_close(int) {}
