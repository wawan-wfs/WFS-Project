// Trusted Node Web preview wrapper. Runs inside restricted Docker, not on host.
'use strict';
const {spawn} = require('node:child_process');
const app = spawn(process.execPath, ['/workspace/server.js'], {
  cwd:'/workspace',env:{...process.env,PORT:'8000',HOST:'0.0.0.0'},
  stdio:'inherit'
});
let closing=false;
function stop(){
  if(closing)return;closing=true;
  app.kill('SIGTERM');
  setTimeout(()=>{try{app.kill('SIGKILL');}catch{}process.exit(0);},3000).unref();
}
setTimeout(stop,15*60*1000);
process.on('SIGTERM',stop);
process.on('SIGINT',stop);
app.on('exit',code=>process.exit(Number.isInteger(code)?code:0));
