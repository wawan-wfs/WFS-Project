"""Offline source/asset and privacy contracts for v2.4; not a hardware GPU test."""
from pathlib import Path
import json, struct, unittest

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app'/'static'
ASSETS=('ergonomic_chair','botanical_planter','dual_console','server_rack',
        'conference_table','lounge_sofa','agent_avatar','floor_kiosk')

class SpatialV24Tests(unittest.TestCase):
    def test_all_eight_local_glbs_include_valid_pbr_factors(self):
        for name in ASSETS:
            with self.subTest(asset=name):
                raw=(STATIC/'models'/f'{name}.glb').read_bytes()
                magic,version,size=struct.unpack_from('<4sII',raw,0)
                self.assertEqual((magic,version,size),(b'glTF',2,len(raw)))
                self.assertLess(size,512*1024)
                length,tag=struct.unpack_from('<I4s',raw,12)
                self.assertEqual(tag,b'JSON')
                doc=json.loads(raw[20:20+length])
                primitive=doc['meshes'][0]['primitives'][0]
                self.assertEqual(primitive['mode'],4)
                self.assertIn('COLOR_0',primitive['attributes'])
                mat=doc['materials'][primitive['material']]['pbrMetallicRoughness']
                self.assertLessEqual(0,mat['metallicFactor']);self.assertLessEqual(mat['metallicFactor'],1)
                self.assertLessEqual(0,mat['roughnessFactor']);self.assertLessEqual(mat['roughnessFactor'],1)
                self.assertFalse(doc.get('images'))
                self.assertFalse(doc.get('textures'))

    def test_original_assets_reproducible_and_licensed(self):
        registry=(STATIC/'models'/'ASSET_LICENSES.md').read_text()
        source=(ROOT/'tools'/'build_original_assets.py').read_text()
        for name in ASSETS:
            self.assertIn(name+'.glb',registry)
            self.assertIn("export('"+name+"'",source)
        self.assertIn('CC0',registry)
        self.assertIn('metallicFactor',source)

    def test_3d_pipeline_shader_and_software_stride_consistent(self):
        gpu=(STATIC/'office3d.js').read_text()
        cpu=(STATIC/'office3d-software.js').read_text()
        decoder=(STATIC/'office3d-assets.js').read_text()
        self.assertIn('const stride=13*4',gpu)
        self.assertIn('i*13',cpu)
        self.assertIn('uniform3f()',cpu)
        for keyword in ('aMetal','aRough','metallic','vRough','PBR','uEye'):
            self.assertIn(keyword, gpu+decoder)
        for name in ASSETS:self.assertIn("'"+name+"'",decoder)
        self.assertIn('localAssets?.loadAll()',gpu)
        self.assertIn('a.live===true',gpu)

    def test_native_task_inspector_and_fallback(self):
        html=(STATIC/'index.html').read_text()
        js=(STATIC/'office3d.js').read_text()
        for ident in ('office-3d-task-heading','office-3d-task-status',
                      'office-3d-task-agent','office-3d-task-project',
                      'office-3d-task-name','office-3d-open-agent'):
            self.assertIn('id="'+ident+'"',html)
        self.assertIn('inspectRoom',js)
        self.assertIn('No agent task recorded',js)
        self.assertIn('mode.demo?',js)
        self.assertIn('a.live===true',js)
        self.assertIn('office-view-2d',html)
        self.assertIn('/static/ux-v24.css',html)

    def test_all_thirteen_menus_and_security_routes_retained(self):
        html=(STATIC/'index.html').read_text()
        for page in ('overview','projects','queue','office','collaboration','operator',
                     'agents','quality','deliverables','activity','finops','system','team'):
            self.assertIn('id="page-'+page+'"',html)
        main=(ROOT/'app'/'main.py').read_text()
        self.assertIn("@app.get('/api/office/live')",main)
        self.assertIn('_verify_visible(project_id,token)',main)
        self.assertIn('auth.require_csrf(',main)
        self.assertIn("httponly=True",main)

if __name__=='__main__':unittest.main()
