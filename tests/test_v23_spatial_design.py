"""WFS v2.3 source/asset contracts. Runtime UI is covered by browser-ui-fixture-smoke.py.
These tests do not claim GPU performance or real provider availability.
"""
import json
import struct
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app'/'static'

class SpatialDesignV23Tests(unittest.TestCase):
    def test_original_glb_assets_are_valid_gltf2(self):
        for name in ('ergonomic_chair','botanical_planter','dual_console','server_rack'):
            with self.subTest(name=name):
                raw=(STATIC/'models'/f'{name}.glb').read_bytes()
                self.assertLess(len(raw),512*1024)
                self.assertEqual(struct.unpack_from('<4sII',raw,0),(b'glTF',2,len(raw)))
                json_size,json_tag=struct.unpack_from('<I4s',raw,12)
                self.assertEqual(json_tag,b'JSON')
                gltf=json.loads(raw[20:20+json_size])
                self.assertEqual(len(gltf['meshes']),1)
                self.assertEqual(gltf['meshes'][0]['primitives'][0]['mode'],4)
                self.assertIn('POSITION',gltf['meshes'][0]['primitives'][0]['attributes'])
                self.assertIn('COLOR_0',gltf['meshes'][0]['primitives'][0]['attributes'])

    def test_asset_licensing_and_reproducibility(self):
        registry=(STATIC/'models'/'ASSET_LICENSES.md').read_text()
        self.assertIn('CC0',registry)
        self.assertIn('build_original_assets.py',registry)
        for name in ('ergonomic_chair','botanical_planter','dual_console','server_rack'):
            self.assertIn(name+'.glb',registry)
        self.assertIn('trimesh.creation', (ROOT/'tools'/'build_original_assets.py').read_text())

    def test_no_third_party_runtime_for_3d(self):
        html=(STATIC/'index.html').read_text()
        for name in ('office3d-assets.js','office3d.js','office3d-software.js','ux-v23.css','ux-v23.js'):
            self.assertIn('/static/'+name,html)
            self.assertTrue((STATIC/name).is_file())
        self.assertNotIn('cdn.',html)
        loader=(STATIC/'office3d-assets.js').read_text()
        self.assertIn('cache:',loader)
        self.assertIn('512 * 1024',loader)
        self.assertNotIn('eval(',loader)

    def test_real_telemetry_and_a11y_controls_retained(self):
        js=(STATIC/'office3d.js').read_text()
        self.assertIn('a.live===true',js)
        self.assertIn('DEMO · NOT LIVE',js)
        self.assertIn('IntersectionObserver',js)
        self.assertIn('prefersReduced.matches',js)
        self.assertIn("canvas.addEventListener('keydown'",js)
        self.assertIn('focusRoom',js)
        html=(STATIC/'index.html').read_text()
        for element in ('office-3d-quality','office-3d-performance','office-view-2d','command-dialog','command-search','command-trigger','main-content'):
            self.assertIn(f'id="{element}"',html)
        self.assertIn('aria-live="polite"',html)
        self.assertIn('Lewati navigasi',html)

    def test_workflows_retained(self):
        html=(STATIC/'index.html').read_text()
        for page in ('overview','projects','queue','office','collaboration','operator','finops','team','agents','quality','deliverables','activity','system'):
            self.assertIn(f'id="page-{page}"',html)
        self.assertIn('id="mission-form"',html)
        self.assertIn('id="office-demo-btn"',html)
        self.assertIn('id="project-visibility"',html)

    def test_design_system_stays_dependency_free_and_keyboard_usable(self):
        css=(STATIC/'ux-v23.css').read_text()
        self.assertIn('@media(max-width:720px)',css)
        self.assertIn('prefers-reduced-motion',css)
        self.assertIn(':focus-visible',css)
        palette=(STATIC/'ux-v23.js').read_text()
        self.assertIn('showModal()',palette)
        self.assertIn('ArrowDown',palette)
        self.assertIn('command-close',palette)  # dialog has native Escape behavior
        self.assertIn('window.wfsNavigate',palette)

if __name__=='__main__': unittest.main()
