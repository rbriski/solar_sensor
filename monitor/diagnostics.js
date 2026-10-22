/* Diagnostics from the last received sample; no claim of live device access. */
(function(root){
const labels={0:'Probe read OK',1:'No probe discovered',2:'Multiple devices discovered',3:'Unexpected probe family',4:'Probe read failed',10:'Delivery acknowledged',11:'Wi-Fi disconnected',12:'Clock not synchronized',13:'HTTP/transport failed',14:'Acknowledgement mismatch',20:'Restart',21:'Probe reinitialization attempted'};
function describe(data){
 const l=data.latest;if(!l)return 'No sensor reports yet.';
 const d=l.diagnostics;if(!d)return 'Detailed diagnostics require updated sensor firmware.';
 const good=(data.history||[]).slice().reverse().find(x=>x.temp_ok);
 const last=d.last_good?new Date(d.last_good*1000).toLocaleString():good?new Date(good.received_at*1000).toLocaleString()+' (receiver time)':'Not available';
 const solar=l.power_mode!=='usb';
 const lines=[labels[d.probe]+' · discovered devices: '+d.devices+' · consecutive failed samples: '+d.streak,
 'Last good temperature: '+last,
 'Restarts: '+d.boots+' · reset reason: '+l.reset_reason+' · '+(solar?'estimated elapsed time including sleeps':'uptime')+': '+d.uptime+' sec',
 'Previous delivery state: '+(labels[d.delivery]||'Not yet recorded')+' · HTTP: '+d.http+(solar?'':' · Wi-Fi disconnects this boot: '+d.wifi_disconnects),
 'Saved history: '+(d.storage_ok?'storage available':'storage error')+(d.pending?' · recent changes awaiting flash checkpoint':''),
 'Recent transitions (newest first; retained across restarts):'];
 for(const e of d.history) lines.push((e[1]?new Date(e[1]*1000).toLocaleString():'Time unknown')+' · '+(labels[e[0]]||'Unknown')+' · boot '+e[2]+' +'+e[3]+' sec'+(e[0]===20?' · reset reason '+e[4]:''));
 return lines.join('\n');
}
root.sensorDiagnostics=describe;
if(typeof module!=='undefined')module.exports={describe};
})(typeof globalThis!=='undefined'?globalThis:this);
