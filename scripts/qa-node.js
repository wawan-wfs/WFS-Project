// Trusted syntax checker inside a network-disabled Node sandbox.
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const cp=require('node:child_process');
let count=0;
function walk(dir){
  for(const ent of fs.readdirSync(dir,{withFileTypes:true})){
    const filename=path.join(dir,ent.name);
    if(ent.isSymbolicLink())throw Error('Symlink detected');
    if(ent.isDirectory()){walk(filename);continue;}
    if(!ent.isFile() || !/\.(?:js|mjs|cjs)$/.test(filename))continue;
    const result=cp.spawnSync(process.execPath,['--check',filename],{encoding:'utf8',timeout:10000});
    if(result.status!==0)throw Error(filename+': '+String(result.stderr).slice(0,1200));
    count++;
  }
}
walk('/workspace');
console.log(JSON.stringify({check:'node_js_syntax',files_checked:count,status:'pass',note:'JSX/TSX need Vite build'}));
