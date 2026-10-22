#include "../firmware/diagnostics/diagnostics.h"
#include <cassert>
#include <cstring>
#include <iostream>
int main() {
  using namespace diagnostics;
  State s;
  assert(discovery(0,false)==NO_DEVICE);
  assert(discovery(2,true)==MULTIPLE);
  assert(discovery(1,false)==WRONG_FAMILY);
  assert(discovery(1,true)==READ_FAILED);
  s.boots=1;
  record(s,BOOT,0,0,1);
  assert(probe(s,OK,100,1));
  assert(!probe(s,OK,101,2));
  assert(s.last_good==101 && s.streak==0);
  assert(probe(s,NO_DEVICE,102,3));
  assert(!probe(s,NO_DEVICE,103,4));
  assert(s.streak==2 && s.last_good==101);
  assert(delivery(s,WIFI_DOWN,104,5));
  assert(!delivery(s,WIFI_DOWN,105,6));
  assert(s.count==4 && s.transitions==4);
  // Serialization of retained blob preserves history; a reboot adds its cause.
  State recovered; memcpy(&recovered,&s,sizeof(s));
  ++recovered.boots; record(recovered,BOOT,0,0,12);
  assert(recovered.events[0].detail==12 && recovered.events[1].code==WIFI_DOWN);
  assert(probe(recovered,OK,107,1) && recovered.streak==0);
  char json[700];
  json[sizeof(json)-1]='!';
  diagnostics::json(recovered,json,sizeof(json),1,10,2,-1,true,true);
  assert(strlen(json)<sizeof(json)-1);
  std::cout<<json;
}
