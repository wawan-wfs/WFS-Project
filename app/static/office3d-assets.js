/* WFS v2.3 local asset decoder. Four original GLB meshes, no third-party runtime/CDN.
 * Deliberately limited to indexed TRIANGLES + float32 positions + u8/u16/f32 vertex colours.
 * Rejects oversized and unsupported assets rather than evaluating unknown content.
 */
(() => {
  'use strict';
  const FILES = Object.freeze(['ergonomic_chair','botanical_planter','dual_console','server_rack','conference_table','lounge_sofa','agent_avatar','floor_kiosk']);
  const LIMIT = 512 * 1024;
  function decode(buf) {
    if (!(buf instanceof ArrayBuffer) || buf.byteLength < 32 || buf.byteLength > LIMIT) throw Error('Invalid GLB size');
    const view = new DataView(buf);
    if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4,true)!==2 || view.getUint32(8,true)!==buf.byteLength) throw Error('Invalid glTF 2.0');
    let offset=12, doc=null, bin=null;
    while(offset+8<=buf.byteLength){
      const length=view.getUint32(offset,true),tag=view.getUint32(offset+4,true);offset+=8;
      if(length>LIMIT || offset+length>buf.byteLength) throw Error('Malformed GLB chunk');
      if(tag===0x4e4f534a)doc=JSON.parse(new TextDecoder().decode(new Uint8Array(buf,offset,length)));
      if(tag===0x004e4942)bin=new DataView(buf,offset,length);
      offset+=length;
    }
    if(!doc || !bin || !Array.isArray(doc.meshes) || doc.meshes.length!==1)throw Error('Unsupported GLB mesh');
    const primitive=doc.meshes[0].primitives?.[0];
    if(!primitive || primitive.mode!==4 || !primitive.attributes || primitive.indices===undefined)throw Error('Indexed triangle mesh required');
    function accessor(index){
      const a=doc.accessors?.[index],bv=doc.bufferViews?.[a?.bufferView];
      if(!a||!bv||bv.buffer!==0||a.count>9000||a.count<=0||a.sparse)throw Error('Unsupported GLB accessor');
      const typeSize={SCALAR:1,VEC3:3,VEC4:4}[a.type],byteSize={5121:1,5123:2,5125:4,5126:4}[a.componentType];
      if(!typeSize||!byteSize)throw Error('Unsupported GLB format');
      const stride=bv.byteStride||byteSize*typeSize, base=(bv.byteOffset||0)+(a.byteOffset||0);
      if(base<0||base+stride*(a.count-1)+byteSize*typeSize>bin.byteLength)throw Error('Out-of-bounds GLB accessor');
      const values=new Float32Array(a.count*typeSize);
      for(let i=0;i<a.count;i++)for(let j=0;j<typeSize;j++){
        const pos=base+i*stride+j*byteSize;
        let v;
        if(a.componentType===5121)v=bin.getUint8(pos);
        else if(a.componentType===5123)v=bin.getUint16(pos,true);
        else if(a.componentType===5125)v=bin.getUint32(pos,true);
        else v=bin.getFloat32(pos,true);
        values[i*typeSize+j] = a.normalized&&a.componentType!==5126?v/(a.componentType===5121?255:a.componentType===5123?65535:4294967295):v;
      }
      return {values,width:typeSize,count:a.count};
    }
    // glTF 2.0 metallic-roughness factors; no external textures or remote URIs.
    let metal=0.04,rough=0.72;
    if (primitive.material!==undefined) {
      const material=doc.materials?.[primitive.material];
      if (!material || material.extensions || material.pbrMetallicRoughness?.baseColorTexture || material.normalTexture || material.occlusionTexture || material.emissiveTexture) throw Error('Unsupported material');
      const pbr=material.pbrMetallicRoughness||{};
      metal=pbr.metallicFactor??metal;
      rough=pbr.roughnessFactor??rough;
      if (![metal,rough].every(v=>Number.isFinite(v)&&v>=0&&v<=1)) throw Error('Invalid PBR material');
    }
    const pos=accessor(primitive.attributes.POSITION),index=accessor(primitive.indices);
    const color=primitive.attributes.COLOR_0!==undefined?accessor(primitive.attributes.COLOR_0):null;
    if(pos.width!==3||index.width!==1||index.count%3!==0||index.count>16000||color&&color.count!==pos.count)throw Error('Malformed mesh data');
    // Internal format uses nonindexed triangle vertices and one geometric normal per face.
    const triangles=[];
    for(let n=0;n<index.count;n+=3){
      const ids=[index.values[n],index.values[n+1],index.values[n+2]];
      if(ids.some(i=>!Number.isInteger(i)||i>=pos.count||i<0))throw Error('Invalid mesh index');
      const verts=ids.map(i=>Array.from(pos.values.subarray(i*3,i*3+3)));
      if(verts.flat().some(v=>!Number.isFinite(v)||Math.abs(v)>100))throw Error('Invalid mesh position');
      const ab=verts[1].map((v,i)=>v-verts[0][i]),ac=verts[2].map((v,i)=>v-verts[0][i]);
      const normal=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]];
      const len=Math.hypot(...normal)||1;
      triangles.push({verts,normal:normal.map(v=>v/len),colors:ids.map(i=>color?Array.from(color.values.subarray(i*color.width,i*color.width+3)):[.6,.7,.8]),metal,rough});
    }
    return triangles;
  }
  async function loadAll(){
    const out={};
    await Promise.all(FILES.map(async name=>{
      try {
        const response=await fetch('/static/models/'+name+'.glb',{credentials:'same-origin',cache:'force-cache'});
        const size=Number(response.headers.get('Content-Length')||0);
        if(!response.ok||(size && size>LIMIT))throw Error('Asset unavailable');
        out[name]=decode(await response.arrayBuffer());
      } catch { /* Procedural furniture fallback: never block core office */ }
    }));
    return out;
  }
  window.WFSOfficeAssets=Object.freeze({decode,loadAll,files:FILES});
})();
