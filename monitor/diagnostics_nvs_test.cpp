#include "../firmware/diagnostics/diagnostics_nvs.h"
#include <cassert>
int main() {
 diagnostics::State s;
 assert(diagnostics::load(s));
 bool dirty=true,ok=true,wrote=false;
 uint32_t last=0;
 diagnostics::record(s,diagnostics::NO_DEVICE,100,1);
 diagnostics::checkpoint(s,dirty,ok,1,last,wrote);
 assert(writes==1 && ok && !dirty);
 diagnostics::State restored;
 assert(diagnostics::load(restored) && restored.events[0].code==diagnostics::NO_DEVICE);
 dirty=true;
 diagnostics::record(s,diagnostics::OK,101,2);
 diagnostics::checkpoint(s,dirty,ok,600,last,wrote);
 assert(writes==1 && dirty);
 diagnostics::checkpoint(s,dirty,ok,601,last,wrote);
 assert(writes==2 && !dirty);
 assert(diagnostics::load(restored) && restored.events[0].code==diagnostics::OK);
 dirty=true;fail=true;
 diagnostics::checkpoint(s,dirty,ok,1201,last,wrote);
 assert(!ok && dirty);
 fail=false;
 diagnostics::checkpoint(s,dirty,ok,1202,last,wrote);
 assert(writes==2 && dirty);
 diagnostics::checkpoint(s,dirty,ok,1801,last,wrote);
 assert(writes==3 && ok && !dirty);
 // A corrupt/unknown blob is never interpreted as valid history.
 blob[0]=0;
 assert(!diagnostics::load(restored));
}
