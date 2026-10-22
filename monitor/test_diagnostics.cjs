const {test}=require('node:test');
const assert=require('node:assert/strict');
const {describe}=require('./diagnostics.js');
test('old firmware is explicit',()=>assert.match(describe({latest:{}}),/require updated/));
test('fault, pending storage and reset cause remain visible',()=>{
 const text=describe({latest:{power_mode:'usb',reset_reason:12,diagnostics:{probe:1,devices:0,streak:3,last_good:0,boots:2,uptime:10,delivery:11,http:0,wifi_disconnects:1,storage_ok:false,pending:true,history:[[20,0,2,0,12]]}}});
 assert.match(text,/No probe discovered/);assert.match(text,/storage error/);assert.match(text,/awaiting flash/);assert.match(text,/reset reason 12/);assert.match(text,/Time unknown/);
});
