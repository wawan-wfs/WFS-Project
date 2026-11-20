"""Transparent deterministic offline template, not AI code generation."""
from __future__ import annotations
import html

def generate_template(title: str, prompt: str, emit) -> dict[str, str]:
    """Clearly labeled deterministic demo, does not purport to be AI coding."""
    emit("Template Engine", "working", "Membuat contoh situs; API key belum disetel")
    safe_title = html.escape(title)
    safe_prompt = html.escape(prompt)
    index = f'''<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} · WFS Preview</title><link rel="stylesheet" href="styles.css"></head>
<body><div class="glow"></div><header><div class="brand">✦ <span>{safe_title}</span></div><a href="#fitur">Jelajahi <span>↗</span></a></header>
<main><section class="hero"><div class="pill">DIBANGUN DENGAN WFS PROJECT • DEMO TEMPLATE</div>
<h1>{safe_title}<br><em>your next big thing.</em></h1><p>{safe_prompt}</p><div class="actions"><a class="primary" href="#fitur">Eksplorasi fitur ↗</a><button id="demo">Lihat interaksi ✨</button></div></section>
<section class="section" id="fitur"><small>FONDASI PROYEK</small><h2>Dari ide menuju implementasi.</h2>
<div class="cards"><article><span>01</span><h3>Konsep</h3><p>Definisikan masalah, pengguna, dan target produk.</p></article>
<article><span>02</span><h3>Desain</h3><p>Bangun pengalaman responsif, konsisten, dan mudah digunakan.</p></article>
<article><span>03</span><h3>Realisasi</h3><p>Mulai dari prototipe kemudian lakukan implementasi dan pengujian.</p></article></div></section></main>
<div id="toast" role="status" aria-live="polite"></div><footer>WFS PROJECT · Starter preview</footer><script src="app.js"></script></body></html>'''
    css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#080c15;color:#f7f8fb;min-height:100vh;overflow-x:hidden}.glow{position:absolute;pointer-events:none;top:-30%;left:10%;width:80vw;height:75vw;background:radial-gradient(circle,#31326075,transparent 64%);filter:blur(12px)}header{position:relative;max-width:1180px;margin:auto;padding:33px 28px;display:flex;justify-content:space-between;align-items:center}a{color:inherit;text-decoration:none}header a{color:#aeb6c9;font-size:14px}.brand{font-size:22px;font-weight:850;letter-spacing:-1px;color:#c5a77a}.brand span{color:white;margin-left:8px}main{position:relative}.hero{max-width:1180px;min-height:600px;margin:auto;padding:120px 28px 85px}.pill{display:inline-block;padding:9px 14px;border:1px solid #373955;border-radius:40px;color:#c4ab82;background:#1c2130;font-size:11px;letter-spacing:2px;font-weight:700}h1{max-width:850px;font-size:clamp(52px,8vw,105px);line-height:1.06;letter-spacing:-.075em;margin:35px 0}h1 em{font-style:normal;background:linear-gradient(110deg,#f2c88a,#b5aaf7,#9fe5e9);color:transparent;background-clip:text}.hero p{max-width:720px;color:#acb5ca;font-size:18px;line-height:1.8}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:36px}.actions a,.actions button{padding:15px 24px;border-radius:11px;border:1px solid #3c4759;font-weight:750;font-size:14px;cursor:pointer;color:white;background:#181e2d}.actions .primary{background:#d4b385;color:#111822;border-color:#d4b385}.section{border-top:1px solid #252b3b;max-width:1180px;margin:auto;padding:88px 28px 120px}.section small{letter-spacing:2.5px;color:#d9b77c}.section h2{font-size:clamp(28px,5vw,48px);letter-spacing:-2px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.cards article{padding:28px;background:#111827;border:1px solid #263042;border-radius:16px;min-height:210px}.cards article span{color:#c2a177;font-size:12px}.cards h3{font-size:23px}.cards p{color:#a3aec3;line-height:1.6}footer{padding:30px;text-align:center;border-top:1px solid #1c2535;color:#737f95;font-size:12px}#toast{position:fixed;bottom:25px;right:25px;background:#d4b385;color:#111827;padding:16px;border-radius:12px;display:none;box-shadow:0 15px 40px #0008}@media(max-width:650px){.hero{padding-top:70px;min-height:500px}.cards{grid-template-columns:1fr}header{padding:22px}h1{letter-spacing:-.05em}}'''
    js = '''document.getElementById('demo').addEventListener('click', () => { const toast=document.getElementById('toast');toast.textContent='✨ Interaksi berfungsi — demo WFS siap dikembangkan';toast.style.display='block';setTimeout(()=>toast.style.display='none',3300); });'''
    return {
        "index.html": index,
        "styles.css": css,
        "app.js": js,
        "WFS_README.md": "# WFS PROJECT — Demo Template\n\nIni adalah template deterministik, **bukan** kode yang dihasilkan AI.\nAktifkan OPENAI_API_KEY untuk menjalankan beberapa panggilan agent model pada tugas baru.\n",
    }
