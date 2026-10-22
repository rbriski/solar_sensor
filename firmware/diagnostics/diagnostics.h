#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
namespace diagnostics {
// Wire codes are stable. History times are zero until wall time is available.
enum Code : uint32_t { OK=0, NO_DEVICE=1, MULTIPLE=2, WRONG_FAMILY=3, READ_FAILED=4,
  DELIVERY_OK=10, WIFI_DOWN=11, CLOCK_UNSET=12, HTTP_FAILED=13, ACK_FAILED=14, BOOT=20 };
struct Event { uint32_t code=0, epoch=0, boot=0, uptime=0, detail=0; };
struct State {
  uint32_t magic=0x44494131, boots=0, probe=99, delivery=99, streak=0;
  uint32_t last_good=0, transitions=0, count=0;
  Event events[4]{};
};
inline void increment(uint32_t &v) { if (v != UINT32_MAX) ++v; }
inline bool record(State &s, uint32_t code, uint32_t epoch, uint32_t uptime, uint32_t detail=0) {
  for (unsigned i=3;i>0;--i) s.events[i]=s.events[i-1];
  s.events[0]={code,epoch,s.boots,uptime,detail};
  if(s.count<4) ++s.count;
  increment(s.transitions); return true;
}
inline bool probe(State &s, uint32_t code, uint32_t epoch, uint32_t uptime) {
  if(code==OK) { s.streak=0; if(epoch) s.last_good=epoch; }
  else increment(s.streak);
  if(s.probe==code) return false;
  s.probe=code; return record(s,code,epoch,uptime);
}
inline bool delivery(State &s, uint32_t code, uint32_t epoch, uint32_t uptime) {
  if(s.delivery==code) return false;
  s.delivery=code; return record(s,code,epoch,uptime);
}
inline uint32_t discovery(unsigned count, bool family) {
  return count==0 ? NO_DEVICE : count>1 ? MULTIPLE : !family ? WRONG_FAMILY : READ_FAILED;
}
// Compact history entries: [code,unix_seconds,boot,uptime_seconds,detail], newest first.
inline void json(const State &s, char *out, size_t size, unsigned devices,
                 uint32_t uptime, uint32_t disconnects, int http, bool stored, bool pending) {
  char history[320]; size_t pos=0;
  history[pos++]='[';
  for(unsigned i=0;i<s.count && i<4;++i) {
    const auto &e=s.events[i];
    int n=snprintf(history+pos,sizeof(history)-pos,"%s[%lu,%lu,%lu,%lu,%lu]",i?",":"",
      (unsigned long)e.code,(unsigned long)e.epoch,(unsigned long)e.boot,(unsigned long)e.uptime,(unsigned long)e.detail);
    if(n<0 || size_t(n)>=sizeof(history)-pos) break;
    pos+=n;
  }
  snprintf(history+pos,sizeof(history)-pos,"]");
  snprintf(out,size,"{\"version\":1,\"probe\":%lu,\"devices\":%u,\"streak\":%lu,"
    "\"last_good\":%lu,\"boots\":%lu,\"uptime\":%lu,\"wifi_disconnects\":%lu,"
    "\"delivery\":%lu,\"http\":%d,\"storage_ok\":%s,\"pending\":%s,\"transitions\":%lu,\"history\":%s}",
    (unsigned long)s.probe,devices,(unsigned long)s.streak,(unsigned long)s.last_good,
    (unsigned long)s.boots,(unsigned long)uptime,(unsigned long)disconnects,
    (unsigned long)s.delivery,http,stored?"true":"false",pending?"true":"false",
    (unsigned long)s.transitions,history);
}
} // namespace diagnostics
