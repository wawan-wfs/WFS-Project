"""Contract regressions for v2.2 UI and self-contained 3D features.

These checks complement (never replace) Playwright interactions and real deployment tests.
"""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app'/'static'

class SpatialStudioContractTests(unittest.TestCase):
    def test_spatial_assets_bundled_offline(self):
        html=(STATIC/'index.html').read_text()
        for name in ('ux-v22.css','office3d-software.js','office3d.js'):
            self.assertTrue((STATIC/name).is_file())
            self.assertIn('/static/'+name, html)
        self.assertNotRegex(html, r'<script[^>]+src=["\']https?://')
        self.assertIn('id="office-3d-canvas"',html)
        self.assertIn('id="office-view-2d"',html)
        self.assertIn('id="office-3d-rooms"',html)

    def test_original_office_functionality_retained(self):
        html=(STATIC/'index.html').read_text()
        for key in ('office','projects','queue','collaboration','operator','agents','finops','team','quality','activity','system','deliverables'):
            self.assertIn(f'id="page-{key}"',html)
        self.assertIn('id="office-world"',html)
        self.assertIn('id="office-demo-btn"',html)

    def test_original_project_handler_no_longer_overrides_operator_dialog(self):
        code=(STATIC/'app.js').read_text()
        self.assertIn("#project-list [data-id], #side-projects [data-id]",code)
        self.assertNotIn("document.querySelectorAll('[data-id]').forEach(el=>el.onclick",code)

    def test_3d_source_uses_real_projection_and_telemetry(self):
        js=(STATIC/'office3d.js').read_text()
        self.assertIn("getContext('webgl2'",js)
        self.assertIn('drawArrays(gl.TRIANGLES',js)
        self.assertIn('function perspective(',js)
        self.assertIn('function lookAt(',js)
        self.assertIn('aMotion',js)
        self.assertIn('agent',js)
        self.assertIn('safe(String(live.agent',js)  # Escape telemetry before HTML injection.
        self.assertIn('DEMO · NOT LIVE',js)

    def test_html_equivalent_and_accessible_view_controls(self):
        html=(STATIC/'index.html').read_text()
        for control in ('office-3d-turn-left','office-3d-turn-right','office-3d-zoom-in','office-3d-zoom-out','office-3d-reset'):
            self.assertRegex(html, f'id="{control}"[^>]+aria-label=')
        self.assertIn('aria-label="Daftar divisi dan status agent"',html)
        self.assertIn('prefers-reduced-motion', (STATIC/'ux-v22.css').read_text())

    def test_project_ui_design_skills_installed(self):
        for skill in ('wfs-ui-ux-pro','wfs-3d-spatial-ui','wfs-accessibility'):
            path=ROOT/'.agents'/'skills'/skill/'SKILL.md'
            self.assertTrue(path.is_file(),skill)
            self.assertIn('---',path.read_text())
        self.assertTrue((ROOT/'AGENTS.md').is_file())
        self.assertTrue((ROOT/'docs'/'NEXT_PROMPT.md').is_file())

if __name__=='__main__':unittest.main()
