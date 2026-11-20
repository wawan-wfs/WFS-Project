/* WFS PROJECT — original dependency-free WebGL2 office renderer.
 * Actual 3D triangles, depth-tested geometry, lighting, orbit/zoom camera.
 * The renderer consumes the same authenticated office snapshot as the 2.5D fallback.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const host = $('office-3d-stage');
  if (!host) return;
  const canvas = $('office-3d-canvas');
  const hint = $('office-3d-error');
  const buttons = $('office-3d-rooms');
  const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)');
  const localAssets=window.WFSOfficeAssets;
  let meshLibrary={},lastOffice={agents:[]};
  let roomAnchors=[],isBuilding=false,selectedRoom=null;
  let cameraX=0,cameraZ=0,targetX=0,targetZ=0,hasLiveMotion=false;
  const names = {
    1:['Management','Architecture','Operations'],
    2:['Engineering','Creative Studio','AI & Data','Documentation'],
    3:['Quality Lab','Infrastructure','Security']
  };
  const accents = {
    'Management':'#d6b88b','Architecture':'#a998ed','Operations':'#89b8e8',
    'Engineering':'#6ccedc','Creative Studio':'#ed95bc','AI & Data':'#9ebeff',
    'Documentation':'#d4b4d8','Quality Lab':'#7ddebd','Infrastructure':'#9faef2','Security':'#e5b57f'
  };
  const hex = s => [1,3,5].map(i=>parseInt(s.slice(i,i+2),16)/255);
  const safe = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const gl = canvas.getContext('webgl2', {antialias:true, alpha:true, powerPreference:'default'}) || window.WFSCreateSoftwareGL?.(canvas);
  if (!gl) {
    hint.hidden=false;
    hint.textContent='WebGL2 tidak tersedia. Tampilan kantor 2.5D tetap dapat digunakan.';
    host.dataset.support='fallback';
    window.WFSOffice3D = {supported:false,update(){},setVisible(){},dispose(){}};
    return;
  }
  const vert = `#version 300 es
    precision highp float;
    in vec3 aPos; in vec3 aNormal; in vec3 aColor; in float aGlow; in float aMotion; in float aMetal; in float aRough;
    uniform mat4 uVP; uniform float uTime; uniform bool uAnimate;
    out vec3 vColor; out vec3 vNormal; out vec3 vWorld; out float vGlow; out float vDistance; out float vMetal; out float vRough;
    void main() {
      vec3 p=aPos;
      if(uAnimate && aMotion>0.5) p.y += sin(uTime*2.4 + aPos.x*0.7)*0.075;
      gl_Position=uVP*vec4(p,1.0);
      vNormal=aNormal; vColor=aColor; vGlow=aGlow; vMetal=aMetal; vRough=aRough; vWorld=p;
      vDistance=length(p-vec3(0.0,0.8,0.0));
    }`;
  const frag = `#version 300 es
    precision highp float;
    in vec3 vColor; in vec3 vNormal; in vec3 vWorld; in float vGlow; in float vDistance; in float vMetal; in float vRough;
    uniform float uTime; uniform vec3 uEye;
    out vec4 fragColor;
    const float PI=3.14159265;
    void main() {
      vec3 N=normalize(vNormal), L=normalize(vec3(-0.46,0.90,0.67));
      vec3 V=normalize(uEye-vWorld), H=normalize(L+V);
      float nl=max(dot(N,L),0.0), nv=max(dot(N,V),0.001);
      float nh=max(dot(N,H),0.001), vh=max(dot(V,H),0.001);
      float rough=clamp(vRough,0.12,1.0), metal=clamp(vMetal,0.0,1.0);
      float a=rough*rough, a2=a*a;
      float denom=nh*nh*(a2-1.0)+1.0;
      float D=a2/max(PI*denom*denom,0.001);
      float k=(rough+1.0)*(rough+1.0)/8.0;
      float G=(nv/(nv*(1.0-k)+k))*(nl/(nl*(1.0-k)+k));
      vec3 F0=mix(vec3(0.04),vColor,metal);
      vec3 F=F0+(vec3(1.0)-F0)*pow(1.0-vh,5.0);
      vec3 spec=(D*G*F)/max(4.0*nv*nl,0.001);
      vec3 diffuse=(vec3(1.0)-F)*(1.0-metal)*vColor/PI;
      vec3 c=vColor*0.40+(diffuse+spec)*nl*2.20;
      c+=vColor*vGlow*(0.21+0.12*sin(uTime*1.7));
      c=mix(c,vec3(0.050,0.067,0.119),clamp((vDistance-12.0)/26.0,0.0,.43));
      c=c/(c+vec3(0.85));
      fragColor=vec4(pow(max(c,vec3(0.0)),vec3(0.77)),1.0);
    }`;
  function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
  let program;
  try{
    program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vert));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,frag));gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
  }catch(e){hint.hidden=false;hint.textContent='Renderer gagal dibuat: '+e.message;window.WFSOffice3D={supported:false,update(){},setVisible(){},dispose(){}};return;}
  gl.useProgram(program);
  const stride=13*4;
  const loc={pos:gl.getAttribLocation(program,'aPos'),norm:gl.getAttribLocation(program,'aNormal'),color:gl.getAttribLocation(program,'aColor'),glow:gl.getAttribLocation(program,'aGlow'),motion:gl.getAttribLocation(program,'aMotion'),metal:gl.getAttribLocation(program,'aMetal'),rough:gl.getAttribLocation(program,'aRough')};
  const uniform={vp:gl.getUniformLocation(program,'uVP'),time:gl.getUniformLocation(program,'uTime'),animate:gl.getUniformLocation(program,'uAnimate'),eye:gl.getUniformLocation(program,'uEye')};
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  [['pos',3,0],['norm',3,3],['color',3,6],['glow',1,9],['motion',1,10],['metal',1,11],['rough',1,12]].forEach(([k,size,offset])=>{
    gl.enableVertexAttribArray(loc[k]);gl.vertexAttribPointer(loc[k],size,gl.FLOAT,false,stride,offset*4);
  });
  gl.enable(gl.DEPTH_TEST);gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);
  let data=[],count=0,visible=false,running=false,frame=0,mode={motion:true,demo:false},floor=1;
  let yaw=0.41, pitch=0.81, dist=17.3, drag=null, lastSnapshot='';
  let desiredYaw=yaw,desiredPitch=pitch,desiredDist=dist,lastFrame=0;
  let quality='auto',frameSamples=0,elapsedSamples=0,startSamples=0;
  let totalSubmitMs=0,drawCalls=0;
  // GPU timer queries are OPTIONAL hardware metrics; CPU submit duration is never GPU FPS.
  const gpuTimer=!gl.isSoftware && typeof gl.getExtension==='function'?gl.getExtension('EXT_disjoint_timer_query_webgl2'):null;
  const gpuPending=[];
  let gpuTimeTotalNs=0,gpuTimeSamples=0,observedSubmitFps=null;
  const C = (s)=>hex(s);
  const vertex=(v,n,c,g=0,m=0,metal=.04,rough=.72)=>data.push(...v,...n,...c,g,m,metal,rough);
  function face(a,b,c,d,n,col,g=0,m=0){vertex(a,n,col,g,m);vertex(b,n,col,g,m);vertex(c,n,col,g,m);vertex(a,n,col,g,m);vertex(c,n,col,g,m);vertex(d,n,col,g,m);}
  // Six-sided solid mesh with outward normal, all dimensions in world units.
  function box(x,y,z,w,h,d,color,glow=0,motion=0){
    const [x0,x1]=[x-w/2,x+w/2], [y0,y1]=[y-h/2,y+h/2], [z0,z1]=[z-d/2,z+d/2], c=C(color);
    face([x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1],[0,0,1],c,glow,motion);
    face([x1,y0,z0],[x0,y0,z0],[x0,y1,z0],[x1,y1,z0],[0,0,-1],c,glow,motion);
    face([x1,y0,z1],[x1,y0,z0],[x1,y1,z0],[x1,y1,z1],[1,0,0],c,glow,motion);
    face([x0,y0,z0],[x0,y0,z1],[x0,y1,z1],[x0,y1,z0],[-1,0,0],c,glow,motion);
    face([x0,y1,z1],[x1,y1,z1],[x1,y1,z0],[x0,y1,z0],[0,1,0],c,glow,motion);
    face([x0,y0,z0],[x1,y0,z0],[x1,y0,z1],[x0,y0,z1],[0,-1,0],c,glow,motion);
  }
  function sphere(cx,cy,cz,r,color,glow=0,motion=0){
    const c=C(color),lat=7,lon=11;
    for(let iy=0;iy<lat;iy++)for(let ix=0;ix<lon;ix++){
      const point=(t,p)=>{const s=Math.sin(t);return [cx+r*s*Math.cos(p),cy+r*Math.cos(t),cz+r*s*Math.sin(p)];};
      const a=point(Math.PI*iy/lat,2*Math.PI*ix/lon),b=point(Math.PI*(iy+1)/lat,2*Math.PI*ix/lon);
      const d=point(Math.PI*iy/lat,2*Math.PI*(ix+1)/lon),e=point(Math.PI*(iy+1)/lat,2*Math.PI*(ix+1)/lon);
      const norm=p=>[(p[0]-cx)/r,(p[1]-cy)/r,(p[2]-cz)/r];
      if(iy>0){vertex(a,norm(a),c,glow,motion);vertex(d,norm(d),c,glow,motion);vertex(b,norm(b),c,glow,motion);}
      if(iy<lat-1){vertex(d,norm(d),c,glow,motion);vertex(e,norm(e),c,glow,motion);vertex(b,norm(b),c,glow,motion);}
    }
  }
  // Instantiate original GLB vertex-colour meshes into the existing 3D triangle pipeline.
  // Renderer remains self-contained, no npm dependency or privileged API access.
  function asset(name,x,y,z,scale=1,angle=0,motion=0){
    const triangles=meshLibrary[name];
    if(!triangles)return false;
    const sn=Math.sin(angle),cs=Math.cos(angle);
    for(const tri of triangles){
      const n=tri.normal;const norm=[n[0]*cs+n[2]*sn,n[1],-n[0]*sn+n[2]*cs];
      tri.verts.forEach((v,i)=>vertex([x+scale*(v[0]*cs+v[2]*sn),y+scale*v[1],z+scale*(-v[0]*sn+v[2]*cs)],norm,tri.colors[i],0,motion,tri.metal,tri.rough));
    }
    return true;
  }
  function line(x,y,z,w,d,color){box(x,y,z,w,.025,d,color,.22);}
  function plant(x,z){if(asset('botanical_planter',x,.03,z,1.0))return;box(x,.25,z,.38,.44,.38,'#9d785f');sphere(x,.63,z,.33,'#2f7d79');sphere(x-.2,.86,z,.24,'#43a99c');sphere(x+.19,.83,z,.24,'#285f76');}
  function desk(x,z,accent,active,index,occupants=0){
    box(x,.74,z,2.45,.14,1.15,'#496076');
    for(const dx of [-1,1])for(const dz of [-1,1])box(x+dx*1.04,.38,z+dz*.42,.095,.7,.09,'#202d48');
    box(x,.77,z+.23,1.6,.027,.5,'#253a54');
    const modelled=asset('dual_console',x,.73,z-.10,1.0);
    if(!modelled){box(x,1.18,z-.12,1.14,.66,.07,'#0d162d');
    box(x,1.19,z-.065,1.02,.54,.017,active?accent:'#30405e',active?1:.08);
    box(x,1.17,z-.045,.82,.04,.016,active?'#d3effe':'#51687d',active?.7:.08);
    box(x-.10,1.30,z-.035,.60,.023,.016,active?'#ffffff':'#607789',active?.9:.06);
    box(x+.08,1.05,z-.032,.46,.025,.016,active?'#e7c1ef':'#607789',active?.5:.06);
    box(x,.91,z-.13,.075,.14,.07,'#1d2b42');}
    box(x,.85,z-.12,.40,.045,.27,'#243951');
    box(x-.76,.83,z+.28,.40,.025,.24,'#0f2039');
    box(x+.75,.85,z+.27,.20,.05,.19,'#a5b9d7');
    // Original licensed mesh when GPU asset support is available; procedural fallback otherwise.
    const hasChair=asset('ergonomic_chair',x,.03,z+1.08,1.0);
    if(!hasChair){box(x,.44,z+1.08,.77,.15,.62,'#1b2c4b');box(x,.84,z+1.28,.74,.89,.15,'#263c65');
    box(x,.30,z+1.12,.13,.5,.14,'#3c5374');box(x,.11,z+1.10,.75,.09,.13,'#3c5374');}
    // One avatar per authenticated active specialist, capped to three locally rendered
    // people for bounded geometry. The HTML room card still reports the full count.
    if(active){
      const body=accent;
      for(let seat=0;seat<Math.min(3,occupants);seat++){
        const offset=occupants===1?0:(seat-(Math.min(3,occupants)-1)/2)*.55;
        const ax=x+offset;
        if(!asset('agent_avatar',ax,.34,z+1.08,.55,0,1)){
          sphere(ax,.98,z+1.1,.205,body,.25,1);
          sphere(ax,1.31,z+1.1,.185,'#e2bbaa',.10,1);
          box(ax-.22,1.02,z+.84,.09,.36,.13,body,.12,1);
          box(ax+.22,1.02,z+.84,.09,.36,.13,body,.12,1);
        }
      }
    } // Idle chair stays empty: a recorded run is not live execution.

    // room identifier floor glow plate
    line(x,.08,z+2.05,2.25,.04,active?accent:'#39516b');
  }
  function renderBuilding(){
    // Three-level physical building navigator; floor lights are wayfinding, not agent telemetry.
    const widths=[15.8,15.8,15.8],palette=['#9b8ded','#66bbce','#dab77f'];
    box(0,-.32,0,17.7,.46,11.8,'#141f37');
    for(let lev=0;lev<3;lev++){
      const y=lev*3.35,color=palette[lev];
      // Three structurally separate slabs with illuminated edges and glazing bands.
      box(0,y,0,widths[lev],.24,10.1,'#293a57');
      box(0,y+.13,5.06,15.85,.045,.07,color,.8);
      box(0,y+.14,-5.04,15.85,.045,.07,color,.45);
      for(const x of [-7.82,0,7.82])for(const z of [-4.86,4.86])
        box(x,y+1.65,z,.22,3.1,.22,'#677994');
      // Interior per-floor warm light ceiling and open office windows.
      for(let x=-6.1;x<=6.1;x+=2.42){
        box(x,y+2.18,-4.84,2.04,1.36,.045,'#2f6577',.18);
        box(x,y+2.18,4.84,2.04,1.36,.045,'#396577',.14);
        box(x,y+1.35,4.92,2.04,.028,.052,color,.48);
        box(x,y+2.9,4.92,2.04,.028,.052,'#b8c9eb',.22);
      }
      box(0,y+3.29,0,16.1,.16,10.4,'#364461');
      box(0,y+3.39,0,16.12,.045,10.44,color,.14);
      // Luminous portal indicates a navigable floor, never an active worker.
      box(-5.9,y+1.22,5.11,1.56,2.12,.08,'#212e50');
      box(-5.9,y+2.35,5.17,1.22,.09,.04,color,.68);
      box(-5.9,y+.25,5.17,1.22,.08,.05,color,.46);
      roomAnchors.push({name:'Floor 0'+(lev+1),x:0,z:0,y:y+1.4,floor:lev+1});
    }
    // Roof terrace: canopy, air vents and slender mast.
    box(0,10.18,0,17.0,.32,11.0,'#384b69');
    box(0,10.47,-3.4,13.6,.12,.2,'#94a5cb');
    for(const x of [-5,0,5]){
      box(x,10.62,-3.5,.12,.5,.11,'#67789e');
      box(x,10.91,-3.5,2.8,.09,.60,'#b3c9e8',.30);
    }
    box(5.8,10.52,2.2,2.0,.50,1.25,'#253953');
    box(-5.9,11.1,0,.11,1.65,.10,'#9aaccf');
    box(-5.9,11.98,0,.45,.12,.45,'#d6bddb',.7);
    selectedRoom=null;inspectRoom(null);
    // A dedicated UI list provides semantic floor selection outside the canvas.
    const titles=['Strategy · Planning','Production · Engineering','Reliability · Quality'];
    buttons.innerHTML=titles.map((title,i)=>`<button type="button" class="office3d-room" data-building-floor="${i+1}" aria-label="Buka lantai ${i+1}: ${title}"><span class="office3d-dot"></span><span><strong>FLOOR 0${i+1}</strong><small>${title} · floor navigation, not agent status</small></span><span aria-hidden="true">↗</span></button>`).join('');
    buttons.querySelectorAll('[data-building-floor]').forEach(b=>b.onclick=()=>
      document.querySelector(`[data-visual-floor="${b.dataset.buildingFloor}"]`)?.click());
    $('office-3d-floor-number').textContent='01—03';
    $('office-3d-selection').textContent='Pilih lantai untuk melihat divisi dan status agent. Tampilan gedung tidak menyatakan aktivitas live semua lantai.';
    $('office-3d-mode').textContent='3D BUILDING · FLOOR NAVIGATION';
    const arr=new Float32Array(data);count=arr.length/13;
    gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,arr,gl.STATIC_DRAW);
    requestDraw();
  }
  function rebuild(snapshot){
    lastOffice=snapshot;data=[];roomAnchors=[];
    if(isBuilding){renderBuilding();return;}
    hasLiveMotion=mode.demo || (snapshot.agents||[]).some(a=>a.live===true);
    const namesOnFloor=names[floor]||names[1];
    // Ground plate & subfloor, architectural grid, edge LEDs.
    // Outer trim is segmented to keep the software rasterizer painter order correct.
    for(let gx=-8;gx<=8;gx+=1)box(gx,-.19,-6.2,.98,.35,.19,'#17213e');
    for(let gx=-8;gx<=8;gx+=1)box(gx,-.19,6.2,.98,.35,.19,'#17213e');
    for(let gz=-5.5;gz<=5.5;gz+=1)box(-8.65,-.19,gz,.19,.35,.98,'#17213e');
    for(let gz=-5.5;gz<=5.5;gz+=1)box(8.65,-.19,gz,.19,.35,.98,'#17213e');
    for(let tx=-8;tx<=8;tx+=1.0)for(let tz=-5.5;tz<=5.5;tz+=1.0){
      const variant=(Math.round(tx+tz)&1)?'#1e3050':'#203351';
      box(tx,.02,tz,.99,.043,.99,variant);
    }
    line(0,.064,-6.04,17,.045,'#6a75bf');line(0,.064,6.04,17,.045,'#56a9cb');
    box(-8.54,.06,0,.045,.05,12,'#8e80d9',.45);box(8.54,.06,0,.045,.05,12,'#8e80d9',.45);
    for(let x=-8;x<9;x+=1.6)box(x,.064,0,.013,.012,11.97,'#283e5b');
    for(let z=-5.5;z<=5.5;z+=1.5)box(0,.066,z,17,.012,.013,'#283e5b');
    // Glass walls and uplighters
    box(0,1.28,-5.93,17.05,2.58,.10,'#283d5d');
    box(0,2.56,-5.88,17.05,.07,.11,'#7b7eaa',.14);
    for(let x=-7.1;x<=7.1;x+=2.6){
      box(x,1.56,-5.84,2.14,1.47,.025,'#285b72',.12);
      box(x,.82,-5.81,2.14,.026,.035,'#77c3ca',.35);
      box(x,2.28,-5.81,2.14,.027,.035,'#77c3ca',.35);
    }
    plant(-7.6,-4.6);plant(7.6,-4.6);
    // Architectural details: elevated beam rhythm, structural mullions, ceiling coves.
    for(let x=-8.2;x<=8.2;x+=1.8){
      box(x,2.64,-5.78,.085,.31,.16,'#57738c');
      box(x,.18,-5.62,.05,.29,.08,'#4a637f');
    }
    for(let x of [-7.8,7.8]){
      box(x,1.35,4.8,.14,2.7,.14,'#415272');
      box(x,2.64,4.8,1.2,.10,1.0,'#b8dce9',.55);
    }
    // Modular glass suite partitions create a recognizable 3D office wing.
    for(const x of [-7.9,7.9]){
      box(x,1.30,-.35,.08,2.35,8.95,'#233e53');
      for(const z of [-3.9,-1.6,.7,3.0]){
        box(x,1.47,z,.10,1.72,1.7,'#2a5667',.05);
        box(x,2.37,z,.11,.04,1.84,'#a3cfdb',.20);
      }
    }
    // Original spatial kit: lounge, conference table, guide kiosk. Local GLBs use PBR material factors.
    if(!asset('lounge_sofa',-6.8,.04,4.87,.62))box(-6.8,.43,4.87,1.7,.73,.70,'#405879');
    if(!asset('conference_table',0,.03,4.13,.68))box(0,.51,4.13,2.2,.22,.79,'#7b8fae');
    if(!asset('floor_kiosk',6.65,.05,5.04,.72))box(6.65,.71,5.04,.62,1.18,.22,'#52738c');
    // Small meeting / lounge nook at front-left of the floor, clear of main desks.
    box(-6.87,.46,5.15,1.35,.09,.79,'#7b8fae');
    box(-6.87,.29,5.15,.09,.50,.09,'#37475f');
    for(const cx of [-7.60,-6.17])box(cx,.38,5.18,.47,.56,.43,'#354d78');
    if(floor===3){
      for(const x of [-7.3,-5.9,5.9,7.3]){
        if(!asset('server_rack',x,.08,-4.35,.72)){
          box(x,.93,-4.3,.78,1.81,.60,'#25334f');
          for(let j=0;j<5;j++)line(x,.34+j*.28,-3.99,.50,.02,'#5ab6a7');
        }
      }
    }
    if(floor===2){
      for(const x of [-7.35,7.35]){
        box(x,1.28,-4.65,.75,.93,.08,'#111e3c');
        box(x,1.33,-4.59,.62,.73,.012,'#48768e',.45);
        line(x,2.1,-4.55,.82,.035,'#8cc1ca');
      }
    }
    if(floor===1){
      box(0,.16,4.1,2.6,.18,.75,'#40506e');
      box(0,.37,4.1,2.25,.13,.54,'#9a8cad');
      box(0,.13,3.6,2.2,.04,.09,'#b49ce5');
    }
    // Suspended ceiling luminaires, back wall feature.
    for(let x of [-5.3,0,5.3])box(x,2.63,-3.8,3.3,.06,.14,'#c8ceee',.8);
    box(0,2.1,-5.72,3.35,.36,.07,'#151b3e');
    box(0,2.1,-5.67,3.10,.26,.022,'#9885e2',.7);
    const positions=namesOnFloor.length===4?[[-4.35,-1.65],[4.35,-1.65],[-4.35,3.0],[4.35,3.0]]:[[-5.10,.15],[0,.15],[5.10,.15]];
    namesOnFloor.forEach((name,i)=>{
      const [x,z]=positions[i], accent=accents[name];
      roomAnchors.push({name,x,z});
      const runs=(snapshot.agents||[]).filter(a=>a.division===name);
      const activeCount=runs.filter(a=>a.live===true).length;
      const active=activeCount>0;
      const w=namesOnFloor.length===4?7.6:4.75;
      // Room floor only uses trim; avoid depth artifacts from giant overlapping polygons.
      line(x,.083,z-1.93,w-.35,.05,selectedRoom===name?'#efdcaa':active?accent:'#384c70');
      if(selectedRoom===name)line(x,.086,z+1.78,w-.8,.05,'#efdcaa');
      box(x,.07,z-2.04,w-.55,.03,.045,active?accent:'#46607d',active?.5:0);
      if(namesOnFloor.length!==4 && i<2)box(x+2.52,1.1,0,.11,2.1,8.7,'#405473');
      if(namesOnFloor.length===4)box(0,1.02,0,.11,2,9.3,'#354967');
      desk(x,z,accent,active,i,activeCount);
    });
    // centralized walking lane across floor
    box(0,.09,5.18,15.8,.019,.12,'#6073aa',.1);
    const arr=new Float32Array(data);count=arr.length/13;
    gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,arr,gl.STATIC_DRAW);
    buttons.innerHTML=namesOnFloor.map((name,i)=>{
      const runs=(snapshot.agents||[]).filter(a=>a.division===name);
      const live=runs.find(a=>a.live),latest=live||runs[0];
      return `<button type="button" class="office3d-room ${selectedRoom===name?'is-selected':''}" aria-pressed="${selectedRoom===name}" data-name="${name}" data-run="${latest?Number(latest.id):''}" aria-label="${name}: ${live?'sedang bekerja':latest?'aktivitas tercatat':'idle'}"><span class="office3d-dot ${live?'is-live':''}"></span><span><strong>${name}</strong><small>${live?'RUNNING · '+runs.filter(a=>a.live===true).length+' active · '+safe(String(live.agent||'agent').slice(0,32)):latest?'LAST RUN · '+safe(String(latest.state||'idle').slice(0,18)):'AVAILABLE · IDLE'}</small></span><span aria-hidden="true">↗</span></button>`;
    }).join('');
    for(const b of buttons.querySelectorAll('button'))b.addEventListener('click',()=>{
      inspectRoom(b.dataset.name);
      rebuild(lastOffice);
      focusRoom(b.dataset.name);
    });
    if(selectedRoom && namesOnFloor.includes(selectedRoom))inspectRoom(selectedRoom);
    else {selectedRoom=null;inspectRoom(null);}
    $('office-3d-floor-number').textContent='0'+floor;
    $('office-3d-mode').textContent=mode.demo?'DEMO · NOT LIVE':gl.isSoftware?'3D CPU · TELEMETRY':'3D WEBGL · TELEMETRY';
    $('office-3d-selection').textContent=mode.demo?'Contoh animasi / status — bukan eksekusi AI nyata.':'Klik divisi untuk melihat agent dan status pekerjaannya.';
    requestDraw();
  }
  function normalize(v){const n=Math.hypot(...v)||1;return v.map(x=>x/n);}
  function cross(a,b){return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];}
  function lookAt(eye,target,up){const z=normalize(eye.map((v,i)=>v-target[i])),x=normalize(cross(up,z)),y=cross(z,x);
    return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-x.reduce((s,v,i)=>s+v*eye[i],0),-y.reduce((s,v,i)=>s+v*eye[i],0),-z.reduce((s,v,i)=>s+v*eye[i],0),1]);}
  function perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,(2*far*near)/(near-far),0]);}
  function multiply(a,b){const r=new Float32Array(16);for(let c=0;c<4;c++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)r[c*4+row]+=a[k*4+row]*b[c*4+k];return r;}
  function resize(){const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
    const cap=gl.isSoftware?.9:quality==='eco'?1:quality==='studio'?2:1.5;
    const dpr=Math.min(devicePixelRatio||1,cap),w=Math.round(rect.width*dpr),h=Math.round(rect.height*dpr);
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);} }
  function draw(ts=0){if(!visible||!count)return;
    const drawStart=performance.now();
    resize();if(!canvas.width||!canvas.height)return;
    const aspect=canvas.width/canvas.height;
    const distance=dist*(aspect<.9?1.53:aspect<1.2?1.20:1);
    const lookY=isBuilding?5.2:.4;
    const eye=[cameraX+Math.sin(yaw)*Math.cos(pitch)*distance,lookY+Math.sin(pitch)*distance+0.1,cameraZ+Math.cos(yaw)*Math.cos(pitch)*distance];
    const vp=multiply(perspective(Math.PI/3.2,canvas.width/canvas.height,.12,130),lookAt(eye,[cameraX,lookY,cameraZ],[0,1,0]));
    lastVP=vp;
    gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.uniformMatrix4fv(uniform.vp,false,vp);
    gl.uniform3f(uniform.eye,...eye);
    gl.uniform1f(uniform.time,ts/1000);
    gl.uniform1i(uniform.animate,mode.motion&&hasLiveMotion&&!prefersReduced.matches?1:0);
    let query=null;
    if(gpuTimer && gpuPending.length<6){
      query=gl.createQuery();
      if(query)gl.beginQuery(gpuTimer.TIME_ELAPSED_EXT,query);
    }
    gl.drawArrays(gl.TRIANGLES,0,count);
    if(query){gl.endQuery(gpuTimer.TIME_ELAPSED_EXT);gpuPending.push(query);}
    if(gpuTimer){
      const disjoint=gl.getParameter(gpuTimer.GPU_DISJOINT_EXT);
      for(let i=0;i<gpuPending.length;){
        const q=gpuPending[i];
        if(!gl.getQueryParameter(q,gl.QUERY_RESULT_AVAILABLE) && !disjoint){i++;continue;}
        if(!disjoint){gpuTimeTotalNs+=gl.getQueryParameter(q,gl.QUERY_RESULT);gpuTimeSamples++;}
        gl.deleteQuery(q);gpuPending.splice(i,1);
      }
    }
    drawCalls++;totalSubmitMs+=performance.now()-drawStart;
  }
  let lastVP=null,viewIntersecting=true;
  function isAnimating(){return mode.motion && hasLiveMotion && !prefersReduced.matches && !gl.isSoftware;}
  function tick(t){
    frame=0; if(!visible || document.hidden || !viewIntersecting)return;
    const smoothing = prefersReduced.matches ? 1 : .21;
    const approach=(current,dest)=> current+(dest-current)*smoothing;
    yaw=approach(yaw,desiredYaw);pitch=approach(pitch,desiredPitch);
    dist=approach(dist,desiredDist);cameraX=approach(cameraX,targetX);cameraZ=approach(cameraZ,targetZ);
    const moving=Math.max(Math.abs(yaw-desiredYaw),Math.abs(pitch-desiredPitch),Math.abs(dist-desiredDist),Math.abs(cameraX-targetX),Math.abs(cameraZ-targetZ))>.002;
    if(t-lastFrame>=33 || moving){
      lastFrame=t;const start=performance.now();draw(t);
      frameSamples++;elapsedSamples+=performance.now()-start;
      if(!startSamples)startSamples=t;
      if(t-startSamples>=1600){
        const target=$('office-3d-performance');
        observedSubmitFps=Math.round(frameSamples*1000/(t-startSamples));
        if(target)target.textContent=`${observedSubmitFps} draw/s · ${Math.round(100*elapsedSamples/frameSamples)/100} ms CPU submit`;
        frameSamples=0;elapsedSamples=0;startSamples=t;
      }
    }
    if(moving||isAnimating())frame=requestAnimationFrame(tick);
    else if($('office-3d-performance'))$('office-3d-performance').textContent='ON DEMAND';
  }
  function requestDraw(){
    if(!visible || document.hidden)return;
    if(gl.isSoftware){yaw=desiredYaw;pitch=desiredPitch;dist=desiredDist;cameraX=targetX;cameraZ=targetZ;draw();return;}
    if(!viewIntersecting)return;
    if(!frame)frame=requestAnimationFrame(tick);
  }
  function setVisible(v){
    visible=Boolean(v)&&host.dataset.mode!=='2d';
    if(!visible){cancelAnimationFrame(frame);frame=0;return;}
    requestDraw();
  }
  function update(snapshot,opts={}){
    const nextFloor=Number(opts.floor)||1;
    if(nextFloor!==floor && isBuilding){isBuilding=false;const b=$('office-building-toggle');b?.setAttribute('aria-pressed','false');if(b)b.textContent='▤ Building Overview';reset();}
    floor=nextFloor;mode.motion=opts.motion!==false;mode.demo=!!opts.demo;
    const sig=JSON.stringify({floor,isBuilding,mode:mode.demo,agents:(snapshot?.agents||[]).map(x=>[x.id,x.division,x.state,x.live,x.agent,x.task])});
    if(sig!==lastSnapshot){lastSnapshot=sig;rebuild(snapshot||{agents:[]});}
    else requestDraw();
  }
  function setBuildingMode(value){
    isBuilding=Boolean(value);
    const b=$('office-building-toggle');
    if(b){b.setAttribute('aria-pressed',String(isBuilding));b.textContent=isBuilding?'◈ View This Floor':'▤ Building Overview';}
    if(isBuilding){desiredYaw=.48;desiredPitch=.48;desiredDist=25;targetX=0;targetZ=0;}
    else{desiredYaw=.41;desiredPitch=.81;desiredDist=17.3;targetX=0;targetZ=0;}
    rebuild(lastOffice);requestDraw();
  }
  $('office-building-toggle')?.addEventListener('click',()=>setBuildingMode(!isBuilding));
  // Equivalent HTML inspector is intentionally separate from the canvas.  A room without
  // recent authenticated work is an EMPTY workstation, not a fabricated working agent.
  function inspectRoom(name){
    selectedRoom=name;
    const runs=(lastOffice.agents||[]).filter(a=>a.division===name);
    const working=runs.find(a=>a.live===true);
    const recent=working||runs[0];
    const title=$('office-3d-task-heading'),state=$('office-3d-task-status');
    if(!title||!state)return;
    title.textContent=name||'Select a workstation';
    state.textContent=mode.demo?'DEMO SCENE · NOT LIVE':
      working?`${runs.filter(a=>a.live===true).length} LIVE specialist(s) confirmed by backend + worker heartbeat`:
      recent?'Previously recorded run · not currently executing':'No agent task recorded for this room';
    $('office-3d-task-agent').textContent=working?runs.filter(a=>a.live===true).slice(0,3).map(a=>a.agent||'agent').join(' · ')+(runs.filter(a=>a.live===true).length>3?' · +more':''):recent?.agent||'—';
    $('office-3d-task-project').textContent=recent?.project_title||'—';
    $('office-3d-task-name').textContent=recent?.task||'—';
    const button=$('office-3d-open-agent');
    button.disabled=!recent||(!mode.demo&&!Number.isSafeInteger(Number(recent.id)));
    button.onclick=()=>{if(recent&&window.wfsOfficeSelectAgent)window.wfsOfficeSelectAgent(Number(recent.id));};
  }
  function focusRoom(name){
    const room=roomAnchors.find(r=>r.name===name);if(!room)return;
    targetX=room.x*.33;targetZ=room.z*.18;desiredDist=15;
    $('office-3d-selection').textContent=`Fokus ${name} · status dan tugas tersedia pada daftar divisi.`;
    requestDraw();
  }
  function projectScreen(world){
    if(!lastVP)return null;
    const [x,y,z]=world,m=lastVP,w=m[3]*x+m[7]*y+m[11]*z+m[15];
    if(w<=0)return null;
    return {x:(.5+(m[0]*x+m[4]*y+m[8]*z+m[12])/w*.5)*canvas.clientWidth,
      y:(.5-(m[1]*x+m[5]*y+m[9]*z+m[13])/w*.5)*canvas.clientHeight};
  }
  canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,yaw:desiredYaw,pitch:desiredPitch};canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging');});
  canvas.addEventListener('pointermove',e=>{if(!drag)return;
    desiredYaw=drag.yaw+(e.clientX-drag.x)*.006;
    desiredPitch=Math.min(1.25,Math.max(.24,drag.pitch+(e.clientY-drag.y)*.004));requestDraw();});
  const stopDrag=()=>{drag=null;canvas.classList.remove('dragging');};
  canvas.addEventListener('pointerup',e=>{
    if(drag && Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<7){
      const rect=canvas.getBoundingClientRect(),px=e.clientX-rect.left,py=e.clientY-rect.top;
      const hits=roomAnchors.map(room=>({room,screen:projectScreen([room.x,room.y||1.1,room.z])})).filter(x=>x.screen);
      hits.sort((a,b)=>Math.hypot(a.screen.x-px,a.screen.y-py)-Math.hypot(b.screen.x-px,b.screen.y-py));
      const hit=hits[0];if(hit&&Math.hypot(hit.screen.x-px,hit.screen.y-py)<110){
        const b=hit.room.floor?buttons.querySelector(`[data-building-floor="${hit.room.floor}"]`):[...buttons.querySelectorAll('button')].find(x=>x.dataset.name===hit.room.name);
        b?.click();
      }
    }
    stopDrag();
  });canvas.addEventListener('pointercancel',stopDrag);
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.15:.87);},{passive:false});
  function zoom(f){desiredDist=Math.min(39,Math.max(10,desiredDist*f));requestDraw();}
  function reset(){desiredYaw=isBuilding?.48:.41;desiredPitch=isBuilding?.48:.81;desiredDist=isBuilding?25:17.3;targetX=0;targetZ=0;requestDraw();}
  function setQuality(value){
    quality=['auto','eco','studio'].includes(value)?value:'auto';
    // Clear old backing size to force a DPR change on the next frame.
    canvas.width=0;canvas.height=0;
    requestDraw();
  }
  $('office-3d-quality')?.addEventListener('change',e=>setQuality(e.target.value));
  $('office-3d-reset').addEventListener('click',reset);
  $('office-3d-zoom-in').addEventListener('click',()=>zoom(.83));
  $('office-3d-zoom-out').addEventListener('click',()=>zoom(1.2));
  $('office-3d-turn-left').addEventListener('click',()=>{desiredYaw-=.19;requestDraw();});
  $('office-3d-turn-right').addEventListener('click',()=>{desiredYaw+=.19;requestDraw();});
  canvas.tabIndex=0;canvas.setAttribute('role','img');
  canvas.setAttribute('aria-label','Kantor 3D. Gunakan tombol putar dan zoom, atau tombol panah saat kanvas difokuskan. Status agent juga ada di daftar di bawah.');
  canvas.addEventListener('keydown',e=>{
    if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','+','-','='].includes(e.key)){
      e.preventDefault();
      if(e.key==='ArrowLeft')desiredYaw-=.19;
      if(e.key==='ArrowRight')desiredYaw+=.19;
      if(e.key==='ArrowUp')desiredPitch=Math.max(.25,desiredPitch-.12);
      if(e.key==='ArrowDown')desiredPitch=Math.min(1.25,desiredPitch+.12);
      if(e.key==='Home')reset();
      if(e.key==='+'||e.key==='=')zoom(.86);
      if(e.key==='-')zoom(1.15);
      requestDraw();
    }
  });
  const onVisibility=()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else requestDraw();};
  window.addEventListener('visibilitychange',onVisibility);
  const ro=new ResizeObserver(()=>requestDraw());ro.observe(host);
  const observer=('IntersectionObserver' in window)?new IntersectionObserver(entries=>{
    viewIntersecting=entries[0]?.isIntersecting??true;
    if(!viewIntersecting){cancelAnimationFrame(frame);frame=0;}else requestDraw();
  },{threshold:0.02}):null;
  observer?.observe(host);
  (localAssets?.loadAll() || Promise.resolve({}))?.then(loaded=>{
    meshLibrary=loaded;host.dataset.assetCount=String(Object.keys(loaded).length);
    host.dataset.assets=Object.keys(loaded).length ? 'local-glb':'procedural';
    if(Object.keys(loaded).length){rebuild(lastOffice);}
  });
  window.WFSOffice3D={supported:true,update,setVisible,reset,focusRoom,setQuality,setBuildingMode,metrics(){
    return {renderer:gl.isSoftware?'cpu-3d':'webgl2',assetMode:host.dataset.assets||'procedural',
      geometryTriangles:count/3,drawCalls,activeDrawsPerSecond:observedSubmitFps,
      meanFrameSubmitMs:drawCalls?Math.round(totalSubmitMs/drawCalls*100)/100:0,
      gpuTimerSupported:!!gpuTimer,gpuQuerySamples:gpuTimeSamples,
      meanGpuTimeMs:gpuTimeSamples?Math.round(gpuTimeTotalNs/gpuTimeSamples/1e4)/100:null,
      measurement:gpuTimeSamples?'GPU timer-query elapsed time (not display FPS)':'CPU submit wall time only; GPU time unverified',quality};
  },dispose(){
    cancelAnimationFrame(frame);ro.disconnect();observer?.disconnect();window.removeEventListener('visibilitychange',onVisibility);
    if(gpuTimer)for(const q of gpuPending)gl.deleteQuery(q);
    gl.deleteBuffer(buffer);gl.deleteProgram(program);
  }};
  host.dataset.support=gl.isSoftware?'cpu-3d':'webgl-3d';
})();
