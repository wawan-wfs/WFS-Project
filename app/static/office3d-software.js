/* WFS PROJECT 3D — canvas software rasterization fallback for WebGL-blocked devices.
 * Uses the same 3D vertices, camera transforms and lighting as WebGL, with no fake CSS scene.
 * Lower framerate and no GPU effects; full 2.5D view remains user-selectable.
 */
(() => {
  'use strict';
  window.WFSCreateSoftwareGL = canvas => {
    const ctx=canvas.getContext('2d',{alpha:true}); if(!ctx)return null;
    let vertexData=null,vp=null,animate=false,time=0;
    const gl = {
      isSoftware:true,VERTEX_SHADER:1,FRAGMENT_SHADER:2,COMPILE_STATUS:3,LINK_STATUS:4,
      ARRAY_BUFFER:5,STATIC_DRAW:6,FLOAT:7,TRIANGLES:8,DEPTH_TEST:9,CULL_FACE:10,BACK:11,
      COLOR_BUFFER_BIT:12,DEPTH_BUFFER_BIT:13,
      createShader:()=>({}),shaderSource(){},compileShader(){},getShaderParameter:()=>true,getShaderInfoLog:()=>'',
      createProgram:()=>({}),attachShader(){},linkProgram(){},getProgramParameter:()=>true,getProgramInfoLog:()=>'',
      useProgram(){},getAttribLocation:(p,name)=>name,getUniformLocation:(p,name)=>name,
      createBuffer:()=>({}),bindBuffer(){},bufferData:(t,arr)=>{vertexData=arr;},
      enableVertexAttribArray(){},vertexAttribPointer(){},enable(){},cullFace(){},viewport(){},
      clearColor(){},clear(){ctx.clearRect(0,0,canvas.width,canvas.height);},
      uniformMatrix4fv:(name,transpose,m)=>{vp=m;},uniform1f:(name,val)=>{time=val;},
      uniform1i:(name,val)=>{animate=!!val;},uniform3f(){},deleteBuffer(){},deleteProgram(){},
      drawArrays:(mode,start,count)=>{
        if(!vertexData||!vp)return;
        const W=canvas.width,H=canvas.height,points=[],list=[];
        const project=i=>{
          const idx=i*13,x=vertexData[idx],y=vertexData[idx+1]+(animate&&vertexData[idx+10]>.5?Math.sin(time*2.4+x*.7)*.075:0),z=vertexData[idx+2];
          const px=vp[0]*x+vp[4]*y+vp[8]*z+vp[12],py=vp[1]*x+vp[5]*y+vp[9]*z+vp[13],pz=vp[2]*x+vp[6]*y+vp[10]*z+vp[14],pw=vp[3]*x+vp[7]*y+vp[11]*z+vp[15];
          return pw>.001?[(px/pw*.5+.5)*W,(.5-py/pw*.5)*H,pz/pw]:null;
        };
        for(let i=start;i<start+count;i+=3){
          const a=project(i),b=project(i+1),c=project(i+2);if(!a||!b||!c)continue;
          if(Math.max(a[0],b[0],c[0])<0||Math.min(a[0],b[0],c[0])>W||Math.max(a[1],b[1],c[1])<0||Math.min(a[1],b[1],c[1])>H)continue;
          const winding=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
          if(winding>=0)continue;
          const idx=i*13;
          const nx=vertexData[idx+3],ny=vertexData[idx+4],nz=vertexData[idx+5];
          const light=Math.max(0,nx*(-.46)+ny*.90+nz*.67)/1.218;
          let factor=.54+.42*light+vertexData[idx+9]*(0.24+0.17*Math.sin(time*1.7));
          factor=Math.min(1.45,Math.max(.28,factor));
          const col=[6,7,8].map(j=>Math.round(Math.min(255,Math.pow(Math.max(.01,vertexData[idx+j]*factor),.92)*255)));
          list.push({a,b,c,depth:(a[2]+b[2]+c[2])/3,color:`rgb(${col.join(',')})`});
        }
        list.sort((a,b)=>b.depth-a.depth);
        for(const t of list){ctx.beginPath();ctx.moveTo(t.a[0],t.a[1]);ctx.lineTo(t.b[0],t.b[1]);ctx.lineTo(t.c[0],t.c[1]);ctx.closePath();ctx.fillStyle=t.color;ctx.fill();}
      }
    };
    return gl;
  };
})();
