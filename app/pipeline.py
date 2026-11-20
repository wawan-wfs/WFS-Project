"""Single master orchestrator, dynamically scheduled specialized agent calls.

AI calls are real and auditable. They do not imply the generated app passes runtime QA.
"""
from __future__ import annotations
import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from . import config, provider, store, validation, artifacts
from .demo import generate_template

DIVISIONS=[
    ('Management','Product planning, requirements, delivery'),
    ('Architecture','System architecture and integration'),
    ('Engineering','Frontend, backend, desktop and mobile'),
    ('Creative Studio','UI/UX, design systems and motion'),
    ('Quality Lab','Static, regression and acceptance testing'),
    ('Infrastructure','Containers, deployment and operations'),
    ('Security','Application security and threat analysis'),
    ('AI & Data','LLM, agent workflows, databases and analytics'),
    ('Documentation','Developer guides and runbooks'),
    ('Operations','Release management and handover'),
]
ROLES={
   'Frontend Engineer':'Engineering', 'Backend Engineer':'Engineering',
   'Full-Stack Engineer':'Engineering','Database Engineer':'AI & Data',
   'AI Engineer':'AI & Data','UI/UX Engineer':'Creative Studio',
   'DevOps Engineer':'Infrastructure','QA Engineer':'Quality Lab',
   'Documentation Engineer':'Documentation','Security Engineer':'Security',
}

class Cancelled(Exception):pass
class Deferred(Exception):
    """Manual approval checkpoint persisted; worker can claim another project."""
    pass


def check_cancel(pid):
    obj=store.get_project(pid)
    if obj and obj['status']=='cancel_requested':raise Cancelled('Dibatalkan oleh administrator')


def specialist(pid,role,division,task,work,budget,worker_id=None):
    check_cancel(pid)
    if not worker_id or not store.owns_lease(pid,worker_id):
        raise Cancelled('Worker lease expired before specialist start')
    run=store.agent_start(pid,role,division,task,worker_id=worker_id)
    store.event(pid,role,'working',task,worker_id=worker_id)
    try:
        result=work()
        check_cancel(pid)
        if worker_id and not store.owns_lease(pid,worker_id):
            raise Cancelled('Worker lease expired during specialist call')
        if not store.agent_finish(run,'done',worker_id=worker_id):
            raise Cancelled('Worker lease expired before specialist checkpoint')
        store.event(pid,role,'done',f'Selesai: {task[:100]}',worker_id=worker_id)
        return result
    except Cancelled:
        store.agent_finish(run,'cancelled',worker_id=worker_id)
        # An obsolete claim must not create a current-project activity event.
        if store.owns_lease(pid,worker_id):
            store.event(pid,role,'cancelled','Specialist work discarded after cancellation or lease change',worker_id=worker_id)
        raise
    except Exception as exc:
        store.agent_finish(run,'failed',worker_id=worker_id)
        store.event(pid,role,'error',f'Agent gagal: {str(exc)[:250]}',worker_id=worker_id)
        raise


def _safe_tasks(plan,stack,existing_paths=()):
    raw=plan.get('tasks',[])
    if not isinstance(raw,list) or not raw or len(raw)>config.MAX_TASKS:
        raise ValueError('Rencana agent melebihi batas atau kosong')
    tasks=[]
    owned=set()
    for idx,t in enumerate(raw):
        if not isinstance(t,dict):raise ValueError('Task harus berupa object')
        role=str(t.get('role',''))
        if role not in ROLES:raise ValueError(f'Role tidak dikenal: {role[:40]}')
        files=t.get('files')
        if not isinstance(files,list) or not (1<=len(files)<=18):raise ValueError('Output task tidak valid')
        paths=[]
        for p in files:
            p=validation.clean_path(p)
            if p=='WFS_DELIVERY.md':raise ValueError('File WFS_DELIVERY.md dikelola sistem, tidak boleh dihasilkan agent')
            if p in owned:raise ValueError(f'Dua agent memiliki file yang sama: {p}')
            paths.append(p); owned.add(p)
        tasks.append({'id':f'T{idx+1}','role':role,'division':ROLES[role],
                      'task':str(t.get('description','Develop files'))[:650],'files':paths})
    owned.update(existing_paths)
    if stack=='static' and 'index.html' not in owned:raise ValueError('Rencana harus mencakup index.html')
    if stack=='fastapi' and not any(p.endswith('.py') for p in owned):raise ValueError('Rencana FastAPI tanpa Python')
    if stack=='node-web' and not ('server.js' in owned and 'package.json' in owned):raise ValueError('Rencana Node Web harus mencakup server.js dan package.json')
    if stack=='react-vite' and not ('package.json' in owned and 'index.html' in owned and any(x in owned for x in ('src/main.jsx','src/main.tsx','src/main.js','src/main.ts'))):raise ValueError('Rencana React tanpa package.json, index.html, src/main')
    return tasks


def _compact_files(files,limit_per_file=8000,total_limit=50000):
    result={}
    remaining=total_limit
    for path,value in sorted(files.items()):
        slice_=value[:min(limit_per_file,remaining)]
        result[path]=slice_
        remaining-=len(slice_)
        if remaining<=0:break
    return result


def _plan(pid,title,prompt,stack,budget,base_files=None,worker_id=None):
    system=(
       f'Anda Product Manager. Hasilkan JSON object dengan key summary (string), acceptance_criteria (array string), tasks (array object). '
       f'Masing-masing task: role salah satu {list(ROLES)}, description, files (array path unik). Maksimum {config.MAX_TASKS} task, '
       'pemisahan file tanpa duplikasi antar-agent; setiap task idealnya 2-8 file. '
       'Output harus layak produk nyata, bukan contoh kosong. Sertakan tests dan dokumentasi jika relevan. '
       'Jangan meminta atau menyisipkan credential. Files path relatif POSIX. '
       +('INI REVISI: hanya masukkan file yang perlu dibuat/diubah; file yang tidak ditargetkan otomatis dipertahankan. ' if base_files else '')
       +('WAJIB file index.html sebagai entry point.' if stack=='static' else
         'WAJIB file package.json, index.html, dan src/main.jsx atau .tsx sebagai app React Vite. Pastikan package.json punya scripts.build.' if stack=='react-vite' else
         'WAJIB file server.js berbasis Node.js built-in http (tanpa dependensi eksternal), package.json, serta dokumentasi; server listen 0.0.0.0:8000 dengan PORT=8000.' if stack=='node-web' else
         'WAJIB file Python yang mengimplementasikan FastAPI dan requirements.txt.')
    )
    return specialist(pid,'Product Manager','Management','Merencanakan deliverable dan membagi file ke subagent',
       lambda:provider.invoke('Product Manager',system,f'PROJECT: {title}\nSTACK: {stack}\nBRIEF:\n{prompt}\nPARENT FILES (partially truncated):\n'+json.dumps(_compact_files(base_files or {},total_limit=18000),ensure_ascii=False),budget),budget,worker_id=worker_id)


def _spec(pid,role,division,system,title,prompt,plan,budget,worker_id=None):
    return specialist(pid,role,division,'Menyusun spesifikasi yang dapat dieksekusi',
      lambda:provider.invoke(role,system,
         json.dumps({'title':title,'brief':prompt,'plan':plan},ensure_ascii=False),budget),budget,worker_id=worker_id)


def _build_task(pid,title,prompt,stack,plan,arch,design,t,budget,base_files=None,worker_id=None):
    role=t['role']
    targets=t['files']
    def build():
        instructions=(
           'Tulis implementation yang berfungsi, bukan mockup kosong. Return JSON object {"files":{"path":"full file content",...}}. '
           'Path yang wajib dibuat tepat ' + json.dumps(targets) + '. '
           'Jangan tambahkan file lain atau hapus file yang diminta. Jangan gunakan CDN, analytics/tracker, credential hardcoded, '
           'perintah shell berbahaya, pembaca filesystem di luar app, atau install dependency dari repo tak dipercaya. '
           'Gunakan dependensi wajar yang didokumentasikan, error handling, semantic UI, responsive design, dan aksesibilitas. '
           'Dokumentasikan konfigurasi menggunakan environment variables. Untuk layanan backend, ikat localhost sebagai default. '
           'Jangan mengeksekusi kode atau mengaku sudah menguji runtime. Seluruh kode harus lengkap.'
        )
        query=json.dumps({'title':title,'prompt':prompt,'stack':stack,'plan':plan,'architecture':arch,
                          'visual_spec':design,'task':t,
                          'existing_project_files':_compact_files(base_files or {},total_limit=24000),
                          'approved_operator_feedback':store.task_feedback(pid,t['id'])},ensure_ascii=False)
        out=provider.invoke(role,instructions,query,budget)
        files=out.get('files')
        if not isinstance(files,dict) or set(files)!=set(targets):
            raise ValueError(f'{role} tidak mengembalikan semua file tugas secara persis; expected={targets}')
        for name,content in files.items():
            validation.clean_path(name)
            if not isinstance(content,str) or len(content.encode())>240000:
                raise ValueError(f'File AI tidak sesuai batas: {name}')
        return files
    if store.task_gate(pid)['mode']=='manual' and store.task_gate(pid)['approved']<store.task_gate(pid)['total']:
        raise ValueError('Task approval gate not released')
    if not store.task_transition(pid,t['id'],'planned','working',worker_id):
        raise ValueError('Task state was not planned or has already started')
    try:
        output=specialist(pid,role,t['division'],t['task'],build,budget,worker_id=worker_id)
        store.save_task_result(pid,t['id'],output,worker_id)
        return output
    except Exception:
        store.task_transition(pid,t['id'],'working','failed',worker_id)
        raise


def _repair(pid, prompt, stack, files, explanation, budget, worker_id=None):
    """One strictly-bounded repair pass. Files may be replaced, never added or removed."""
    def work():
        response=provider.invoke('QA Repair Engineer',
            'Perbaiki hanya defect nyata pada file yang ada. Keluarkan JSON {"files":{"existing/path":"complete replacement file content"}}. '
            'Jangan sertakan perubahan pada file yang tidak diperbaiki. File harus lengkap, bukan diff/patch. '
            'Jangan mengubah credential atau menambah dependency berbahaya. Jika tidak dapat memperbaiki, kembalikan {"files":{}}.',
            json.dumps({'brief':prompt,'stack':stack,'issue':str(explanation)[:3500],
                        'files':_compact_files(files,limit_per_file=16000,total_limit=65000)},ensure_ascii=False),budget)
        replacements=response.get('files',{})
        if not isinstance(replacements,dict) or not set(replacements).issubset(files):
            raise ValueError('Repair agent mencoba menambahkan atau mengganti file yang tidak dimiliki')
        for name,body in replacements.items():
            validation.clean_path(name)
            if not isinstance(body,str) or len(body.encode())>240000:
                raise ValueError('Repair agent memberikan file tidak valid')
        return replacements
    return specialist(pid,'QA Repair Engineer','Quality Lab','Memperbaiki temuan QA yang teridentifikasi',work,budget,worker_id=worker_id)


def _review(pid,prompt,stack,files,checks,budget,worker_id=None):
    def work():
        return provider.invoke('QA Reviewer',
            'Kembalikan JSON {"summary":"...","issues":[{"severity":"critical|high|medium|low","file":"...","description":"..."}],"acceptance_notes":["..."]}. '
            'Review source secara kritis terkait logic, security, integrasi, import, kecocokan brief, responsivitas. '
            'Jangan mengklaim menjalankan unit tests, Docker, browser, atau CI. Maksimum 12 issues.',
            json.dumps({'brief':prompt,'stack':stack,'static_checks':checks,'files':_compact_files(files)},ensure_ascii=False),budget)
    result=specialist(pid,'QA Reviewer','Quality Lab','Melakukan review AI terhadap hasil (bukan runtime test)',work,budget,worker_id=worker_id)
    if not isinstance(result.get('issues'),list) or not isinstance(result.get('summary'),str):
        raise ValueError('QA reviewer tidak mengembalikan format summary/issues yang wajib')
    return result


def _report(project,plan,arch,design,review,checks,files,mode):
    summary=str(plan.get('summary','-'))
    criteria=plan.get('acceptance_criteria',[])
    if not isinstance(criteria,list):criteria=[]
    issues=review.get('issues',[]) if isinstance(review,dict) else []
    if not isinstance(issues,list):issues=[]
    issues=[i for i in issues if isinstance(i,dict)][:12]
    lines=[f'# WFS PROJECT — Delivery Report', '',f'- Project: {project["title"]}',
           f'- Project ID: {project["id"]}',f'- Parent revision: {project.get("parent_id") or "none"}',f'- Stack: {project["stack"]}',
           f'- Mode: {mode}',f'- Generated at (UTC): {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
           f'- File count (without report): {len(files)}','', '## Summary',summary,'','## Acceptance Criteria (planned, not runtime verified)']
    lines.extend(f'- [ ] {str(x)[:350]}' for x in criteria[:25])
    lines +=['','## Static Validation'] + [f'- PASS: {x}' for x in checks]
    lines+=['','## AI Reviewer (advisory only)',str(review.get('summary','-'))[:1200] if isinstance(review,dict) else '-']
    for issue in issues:
        lines.append('- '+str(issue.get('severity','medium')).upper()+': '+str(issue.get('file',''))[:100]+' — '+str(issue.get('description',''))[:300])
    lines+=['','## IMPORTANT','- AI-generated code is not automatically production certified.',
            '- No runtime tests, security penetration tests, container builds, or browser E2E tests were executed by the platform.',
            '- Review dependencies, configuration, privacy, secrets, and migration behavior before deployment.',
            '- Use scripts/check-project.ps1 for an optional isolated syntax check of supported static files.',
            '', '## Architecture summary',json.dumps(arch,ensure_ascii=False,indent=2)[:3500],
            '', '## UX summary',json.dumps(design,ensure_ascii=False,indent=2)[:2400], '']
    return '\n'.join(lines)


def run(project):
    """One project lifecycle. Caller (worker) owns cancellation and final status."""
    pid=project['id']; stack=project['stack']; title=project['title']; prompt=project['prompt']
    check_cancel(pid)
    if not store.owns_lease(pid,project.get('worker_id')):
        raise Cancelled('Current worker lease required for pipeline execution')
    def emit(agent,state,message):
        return store.event(pid,agent,state,message,worker_id=project['worker_id'])
    if project['mode']=='demo':
        store.phase(pid,'demo',worker_id=project['worker_id'])
        demo=generate_template(title,prompt,lambda a,s,m:emit(a,s,m))
        demo['WFS_DELIVERY.md']='# Demo template\n\nTidak menjalankan API model. Hasil adalah contoh, bukan software yang memenuhi brief.\n'
        notes,manifests=store.publish_artifacts(pid,demo,'static',project['worker_id'])
        emit('QA Static Checker','done','; '.join(notes))
        emit('Delivery Manager','done','Template demo tersimpan; bukan hasil pengembangan AI')
        return
    base_files={}
    if project.get('parent_id'):
        parent=store.get_project(project['parent_id'])
        if not parent or parent['status']!='completed' or parent['stack']!=stack:
            raise ValueError('Versi induk sudah berubah; revisi ditolak')
        base_files=artifacts.source_files(project['parent_id'])
        emit('Version Manager','working',f'Revisi dari {project["parent_id"]}; {len(base_files)} file diwarisi')
    budget=provider.CallBudget(pid)
    checkpoint=store.get_checkpoint(pid)
    if checkpoint:
        plan=checkpoint['plan'];tasks=checkpoint['tasks']
        if tasks!=_safe_tasks(plan,stack,base_files.keys()):raise ValueError('Approved checkpoint file ownership changed')
        gate=store.task_gate(pid)
        if not gate or gate['total']!=len(tasks) or gate['approved']!=len(tasks):
            raise ValueError('Checkpoint task approvals changed; refusing build')
        emit('Master Orchestrator','approved','Resuming approved tasks from persisted checkpoint')
    else:
        store.phase(pid,'planning',worker_id=project['worker_id'])
        plan=_plan(pid,title,prompt,stack,budget,base_files,worker_id=project['worker_id'])
        try:
            tasks=_safe_tasks(plan,stack,base_files.keys())
        except ValueError as exc:
            emit('Master Orchestrator','warning','Rencana awal perlu perbaikan; meminta replanning sekali')
            plan=specialist(pid,'Product Manager — Replan','Management','Memperbaiki struktur task yang tidak valid',
              lambda:provider.invoke('Product Manager','Replan. Keluarkan JSON summary, acceptance_criteria, tasks. '
                   'Roles yang diperbolehkan: '+str(list(ROLES)) +
                   f'. Maksimum {config.MAX_TASKS} task, path unik antar task, dan harus mencakup entry point untuk {stack}.',
                   json.dumps({'title':title,'stack':stack,'prompt':prompt,'bad_plan':plan,'validation_error':str(exc)},ensure_ascii=False),budget),budget,worker_id=project['worker_id'])
            tasks=_safe_tasks(plan,stack,base_files.keys())
        if store.checkpoint_task_plan(pid,plan,tasks,worker_id=project['worker_id']):
            raise Deferred()
    check_cancel(pid)
    store.phase(pid,'architecture',worker_id=project['worker_id'])
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_arch=executor.submit(_spec,pid,'Software Architect','Architecture',
             'Return JSON {"components":[],"integration":"...","file_contracts":{},"test_strategy":"..."}. Rancang integrasi antar-file yang solid, dependency, API contracts, keamanan dan kesesuaian stack.',
             title,prompt,plan,budget,project['worker_id'])
        future_design=executor.submit(_spec,pid,'UI/UX Designer','Creative Studio',
             'Return JSON {"visual_direction":"...","colors":{},"layout":"...","components":[],"accessibility":"..."}. Buat desain modern, konsisten, responsif; jika backend-only, beri pedoman dokumentasi dan developer experience.',
             title,prompt,plan,budget,project['worker_id'])
        arch=future_arch.result(); design=future_design.result()
    store.record_handoff(pid,'Architecture + Creative Studio','Specialist Engineering Agents','Architecture and UX specifications available as build context',worker_id=project['worker_id'])
    check_cancel(pid)
    store.phase(pid,'implementation',worker_id=project['worker_id'])
    emit('Master Orchestrator','working',f'Menjalankan {len(tasks)} specialized coding tasks, maksimal {config.MAX_PARALLEL} paralel')
    files=dict(base_files)
    updated=set()
    completed=store.load_task_results(pid)
    for t in tasks:
        if t['id'] not in completed:continue
        output=completed[t['id']]
        if set(output)!=set(t['files']):raise ValueError('Persisted task checkpoint owns different files')
        for key,value in output.items():
            if key in updated:raise ValueError('Duplicate cached task ownership')
            updated.add(key);files[key]=value
    pending=[t for t in tasks if t['id'] not in completed]
    if completed:emit('Master Orchestrator','resumed',f'Reusing {len(completed)} verified specialist outputs; {len(pending)} tasks remaining')
    with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL) as pool:
        future_tasks={pool.submit(_build_task,pid,title,prompt,stack,plan,arch,design,t,budget,base_files,project.get('worker_id')):t for t in pending}
        for future in as_completed(future_tasks):
            output=future.result()
            for key,value in output.items():
                if key in updated:raise ValueError(f'Konflik output file: {key}')
                updated.add(key)
                files[key]=value
    check_cancel(pid)
    store.record_handoff(pid,'Specialist Engineering Agents','Quality Lab',f'{len(tasks)} completed specialist tasks, {len(files)} source files ready for static checks',worker_id=project['worker_id'])
    store.phase(pid,'quality',worker_id=project['worker_id'])
    try:
        notes=validation.check_files(files,stack)
    except ValueError as exc:
        emit('QA Static Checker','warning',f'Gagal validasi awal: {str(exc)[:250]}')
        check_cancel(pid)
        patch=_repair(pid,prompt,stack,files,str(exc),budget,worker_id=project['worker_id'])
        files.update(patch)
        notes=validation.check_files(files,stack)
    emit('QA Static Checker','done','; '.join(notes))
    review=_review(pid,prompt,stack,files,notes,budget,worker_id=project['worker_id'])
    issues=review.get('issues',[]) if isinstance(review,dict) else []
    if isinstance(issues,list) and any(isinstance(issue,dict) and str(issue.get('severity','')).strip().lower() in ('critical','high') for issue in issues):
        emit('QA Reviewer','warning','Review AI menemukan isu prioritas tinggi; mencoba satu repair pass')
        check_cancel(pid)
        try:
            patch=_repair(pid,prompt,stack,files,json.dumps(issues,ensure_ascii=False),budget,worker_id=project['worker_id'])
            if patch:
                candidate={**files,**patch}
                notes=validation.check_files(candidate,stack)
                files=candidate
                review=_review(pid,prompt,stack,files,notes,budget,worker_id=project['worker_id'])
        except Exception as exc:
            emit('QA Repair Engineer','warning',f'Repair tidak berhasil: {str(exc)[:200]}. Temuan awal tetap dilaporkan.')
    check_cancel(pid)
    lines=_report(project,plan,arch,design,review,notes,files,'AI')
    unresolved=review.get('issues',[]) if isinstance(review,dict) else []
    priority=any(isinstance(i,dict) and str(i.get('severity','')).strip().lower() in ('critical','high') for i in unresolved) if isinstance(unresolved,list) else False
    if priority:
        emit('Quality Gate','review_required','Masih ada temuan high/critical: operator harus meninjau dan menyetujui secara manual')
    store.record_handoff(pid,'Quality Lab','Delivery Manager',f'QA review completed; release gate: {"review_required" if priority else "advisory passed"}',worker_id=project['worker_id'])
    files['WFS_DELIVERY.md']=lines
    check_cancel(pid)
    notes,manifest=store.publish_artifacts(pid,files,stack,project['worker_id'])
    emit('Delivery Manager','done',f'{len(files)} file tersimpan; hasil siap review pengguna, bukan tersertifikasi production')
    return 'review_required' if priority else 'completed'
