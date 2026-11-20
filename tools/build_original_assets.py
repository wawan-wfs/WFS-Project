"""Generate the project's small original, offline glTF 2.0 asset collection.
No downloaded meshes/textures. Geometry is authored below with trimesh primitives.
Assets are licensed for reuse by the project (see app/static/models/ASSET_LICENSES.md).
"""
from pathlib import Path
import json
import struct
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1] / 'app' / 'static' / 'models'
ROOT.mkdir(parents=True, exist_ok=True)


def part(parts, mesh, color, at=(0, 0, 0), scale=None):
    mesh = mesh.copy()
    if scale is not None:
        mesh.apply_scale(scale)
    mesh.apply_translation(at)
    mesh.visual.vertex_colors = np.array([*color,255], dtype=np.uint8)
    parts.append(mesh)


def box(parts, at, size, color):
    part(parts, trimesh.creation.box(extents=size), color, at)


def column(parts, at, radius, height, color, sections=10):
    m = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    # trimesh cylinder defaults Z up; rotate so its axis becomes Y.
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
    part(parts,m,color,at)


def ball(parts, at, radius, color, subdivisions=1, scale=(1,1,1)):
    m=trimesh.creation.icosphere(subdivisions=subdivisions,radius=radius)
    m.apply_scale(scale)
    part(parts,m,color,at)


def export(name, parts):
    m = trimesh.util.concatenate(parts)
    # Single mesh with local vertex colors, normals and triangles for a tiny offline glTF loader.
    out = ROOT / f'{name}.glb'
    raw=trimesh.Scene(m).export(file_type='glb')
    json_size,tag=struct.unpack_from('<I4s',raw,12)
    if tag!=b'JSON':raise ValueError('Expected glTF2 JSON chunk')
    doc=json.loads(raw[20:20+json_size]);offset=20+json_size
    bin_size,bin_tag=struct.unpack_from('<I4s',raw,offset)
    if bin_tag!=b'BIN\x00':raise ValueError('Expected GLB binary chunk')
    binary=raw[offset+8:offset+8+bin_size]
    # Actual glTF2 PBR metallic-roughness material, offline and reproducible.
    metal=.32 if name in ('server_rack','floor_kiosk','dual_console') else .07
    rough=.46 if name in ('server_rack','dual_console','floor_kiosk') else .72
    doc['materials']=[{'name':'WFS '+name.replace('_',' ').title(),
        'pbrMetallicRoughness':{'metallicFactor':metal,'roughnessFactor':rough},
        'doubleSided':False}]
    for primitive in doc['meshes'][0]['primitives']:primitive['material']=0
    body=json.dumps(doc,separators=(',',':')).encode('utf-8');body+=b' '*((-len(body))%4)
    glb=bytearray(struct.pack('<4sII',b'glTF',2,12+8+len(body)+8+len(binary)))
    glb.extend(struct.pack('<I4s',len(body),b'JSON'));glb.extend(body)
    glb.extend(struct.pack('<I4s',len(binary),b'BIN\x00'));glb.extend(binary)
    out.write_bytes(glb)
    print(name, f'{len(out.read_bytes())/1024:.1f} KB',len(m.faces),'triangles')


# Sculpted ergonomic chair with five-spoke undercarriage, armrests and inset padding.
dark=(21,32,53); indigo=(79,95,149); leather=(37,56,86); metal=(119,139,171)
p=[]
box(p,(0,.58,.02),(.73,.12,.67),leather)
box(p,(0,.58,.02),(.61,.14,.55),(68,88,129))
box(p,(0,1.02,.32),(.73,.83,.16),dark)
box(p,(0,1.02,.405),(.57,.65,.07),indigo)
box(p,(0,1.33,.43),(.42,.20,.07),(99,110,165))
column(p,(0,.36,.04),.07,.45,metal)
for dx,dz in ((.34,0),(-.34,0),(0,.29),(0,-.29)):
    box(p,(dx*.65,.135,dz*.65),(.14,.06,.15),metal)
    ball(p,(dx*.93,.09,dz*.93),.084,dark)
for s in (-1,1):
    box(p,(s*.4,.79,.09),(.075,.13,.55),metal)
    box(p,(s*.4,.88,.02),(.16,.055,.56),(57,73,103))
export('ergonomic_chair',p)

# Office plant with a tapered pot, layered leaf canopy, and subtle warm rims.
p=[]
column(p,(0,.18,0),.27,.36,(125,95,84),sections=12)
column(p,(0,.37,0),.29,.075,(164,119,104),sections=12)
column(p,(0,.71,0),.038,.63,(67,107,90),sections=8)
for i,(x,z) in enumerate(((.17,0),(-.17,0),(.0,.17),(.0,-.17),(.22,.12),(-.22,-.11))):
    ball(p,(x,.79+(i%3)*.12,z),.27,((45,138,126) if i%2 else (58,160,136)),scale=(.67,1.4,.5))
export('botanical_planter',p)

# Dual-display developer console for desk-top use, including instrument keys and status LEDs.
p=[]
box(p,(0,.12,0),(1.50,.09,.54),(39,51,75))
for s in (-1,1):
    box(p,(s*.42,.49,-.12),(.72,.49,.05),dark)
    box(p,(s*.42,.49,-.09),(.63,.40,.01),(42,77,112))
    box(p,(s*.42,.61,-.079),(.48,.018,.008),(92,220,216))
    box(p,(s*.42,.51,-.078),(.38,.018,.008),(160,150,246))
    box(p,(s*.42,.39,-.078),(.53,.018,.008),(123,154,182))
    box(p,(s*.42,.23,-.12),(.06,.12,.06),metal)
box(p,(0,.21,.30),(.68,.045,.17),(81,100,139))
for i in range(9):
    box(p,(-.29+i*.074,.241,.30),(.049,.012,.04),(156,173,190))
export('dual_console',p)

# Local rack module for reliability floor.
p=[]
box(p,(0,.94,0),(.95,1.84,.70),(30,43,69))
box(p,(0,.99,.365),(.79,1.70,.03),(21,28,49))
for i in range(8):
    y=.22+i*.20
    box(p,(0,y,.396),(.67,.125,.015),(55,71,102))
    for j in range(3):
        ball(p,(-.23+j*.20,y,.412),.018,((115,228,171) if (i+j)%3 else (217,164,112)),subdivisions=0)
for s in (-1,1): box(p,(s*.44,.95,.30),(.035,1.65,.09),(112,128,157))
export('server_rack',p)


# v2.4: original expanded spatial furniture kit, no external meshes.
# Conference table with wired displays and multi-tone wood / metal surfaces.
p=[]
box(p,(0,.72,0),(2.9,.13,1.15),(112,87,84))
box(p,(0,.79,0),(2.78,.024,1.05),(154,124,108))
for x in (-1.22,1.22):
    for z in (-.40,.40):box(p,(x,.36,z),(.10,.72,.10),(61,76,100))
box(p,(0,.82,0),(.52,.035,.31),(38,53,75))
for x in (-.16,.16):ball(p,(x,.85,0),.035,(83,192,184),subdivisions=0)
export('conference_table',p)

# Premium lounge modular seat with tufted upholstered cushions.
p=[]
box(p,(0,.38,0),(2.0,.32,.83),(47,63,88))
box(p,(0,.68,-.34),(2.0,.85,.19),(39,55,78))
for x in (-.51,.51):
    box(p,(x,.57,.08),(.88,.17,.66),(91,107,142))
    box(p,(x,.86,-.22),(.84,.48,.18),(77,91,133))
for x in (-.96,.96):box(p,(x,.66,.10),(.13,.43,.92),(38,51,74))
for x in (-.72,.72):
    for z in (-.27,.27):box(p,(x,.13,z),(.09,.18,.10),(136,140,157))
export('lounge_sofa',p)

# Telemetry-driven character mesh: helmet, faceplate, torso, arms, articulated legs.
# Animation of this mesh is procedural (NOT skeletal/rigged).
p=[]
box(p,(0,.76,0),(.56,.63,.30),(54,82,129))
box(p,(0,1.12,.015),(.38,.16,.31),(121,165,193))
ball(p,(0,1.40,.015),.26,(202,182,173),scale=(.96,1.08,.88))
box(p,(0,1.41,.245),(.35,.15,.033),(29,49,82))
for x in (-.32,.32):
    ball(p,(x,.94,.01),.11,(106,126,157),subdivisions=1)
    box(p,(x,.71,.10),(.15,.42,.18),(70,103,151))
    ball(p,(x,.46,.20),.09,(189,174,161),subdivisions=0)
for x in (-.145,.145):
    box(p,(x,.30,-.02),(.23,.52,.26),(41,61,97))
    box(p,(x,.075,.12),(.25,.12,.39),(25,42,72))
box(p,(0,.83,.161),(.23,.075,.021),(117,222,203))
export('agent_avatar',p)

# Lounge information kiosk / floor guide, its screen remains local decorative geometry.
p=[]
box(p,(0,.80,0),(.14,1.47,.16),(63,80,108))
box(p,(0,1.40,.01),(.84,.65,.13),(37,49,75))
box(p,(0,1.42,.091),(.73,.54,.014),(46,99,129))
for i in range(3):box(p,(-.17,1.54-i*.15,.107),(.31,.025,.016),(99,187,188))
box(p,(0,.12,0),(.65,.16,.50),(83,99,123))
export('floor_kiosk',p)
