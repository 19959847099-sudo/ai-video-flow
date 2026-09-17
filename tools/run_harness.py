"""Launch the official DSH CLI with the isolated production profile, without keys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def launch(shot_id, data_dir, output_dir=None, mode="video"):
    if mode not in ("video", "first-frame", "dialogue", "rough-cut"): raise ValueError("Unknown harness mode")
    sys.path.insert(0, str(ROOT))
    from app.core import Store
    store = Store(data_dir)
    dialogue_id = None
    timeline_id = None
    if mode == "rough-cut":
        from app.rough_cut import RoughCutProduction
        timeline_id=shot_id
        definition=RoughCutProduction(store).definition(timeline_id)
        if not definition.shot_ids:raise ValueError("Timeline has no shots")
        shot_id=definition.shot_ids[0]
    if mode == 'dialogue':
        from app.audio_production import AudioProduction
        dialogue_id = shot_id
        shot_id = AudioProduction(store).dialogue(dialogue_id).shot_id
    store.record_path('shots', shot_id)
    if not store.record_path('shots', shot_id).is_file(): raise ValueError('Shot does not exist')
    installation = ROOT/'integrations/dsh'
    node_version = (ROOT/'.tools/node-version.txt').read_text().strip()
    node = ROOT/f'.tools/node-{node_version}-win-x64/node.exe'
    cli = installation/'node_modules/@deepseek-ai/dsh/lib/bin.js'
    if not node.is_file() or not cli.is_file(): raise ValueError('Install the pinned DSH runtime first; see integrations/dsh/README.md')
    manifest = json.loads((cli.parent.parent/'package.json').read_text(encoding='utf-8'))
    if manifest['version'] != '0.1.5-rc.2': raise ValueError('DSH version differs from the verified bridge contract')
    run_id = uuid.uuid4().hex
    evidence = Path(output_dir).resolve() if output_dir else ROOT/'evidence/A-04/runs'/run_id
    evidence.mkdir(parents=True, exist_ok=False)
    runtime = installation/'.runtime'
    # One-shot isolated profile; no user profiles, LLM plugins, or global credentials.
    profile = runtime/'profiles/production'
    profile.mkdir(parents=True, exist_ok=True)
    (profile/'package.json').write_text(json.dumps(dict(name='aigc-production-profile', private=True,
        dsh=dict(profile=dict(bundles=[], patchReload='startup')))), encoding='utf-8')
    patch = [dict(insert=[dict(id='system-prompt', name='@deepseek-ai/dsh-system-prompt'),
        dict(id='tools', name='@deepseek-ai/dsh-tools'),
        dict(id='production', name=str(installation/'production-plugin.mjs'), config=dict(
            projectRoot=str(ROOT), python=sys.executable, dataDir=str(store.root),
            evidenceDir=str(evidence), shotId=shot_id, mode=mode, dialogueId=dialogue_id, timelineId=timeline_id))])]
    patch_file = evidence/'profile.patch.json'
    patch_file.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    environment = {k: v for k, v in os.environ.items() if k.upper() in
                   ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','PATHEXT','COMSPEC')}
    environment.update(DSH_HOME=str(runtime), DSH_TELEMETRY_DISABLED='1',
        AIGC_NETWORK_AUDIT=str(evidence/'network-audit.json'))
    work = runtime/'work'; work.mkdir(exist_ok=True)
    command = [str(node), '--import', (installation/'network-lock.mjs').as_uri(), str(cli),
               '--profile', 'production', '--patch', str(patch_file)]
    (evidence/'launch.json').write_text(json.dumps(dict(command=command, cwd=str(work),
        data_dir=str(store.root), run_id=run_id, no_credentials_forwarded=True), indent=2), encoding='utf-8')
    with (evidence/'stdout.txt').open('w', encoding='utf-8') as stdout, (evidence/'stderr.txt').open('w', encoding='utf-8') as stderr:
        result = subprocess.run(command, cwd=work, env=environment, stdout=stdout, stderr=stderr,
            timeout=180, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError(f'DSH failed ({result.returncode}); see {evidence}')
    trace = json.loads((evidence/'trace.json').read_text(encoding='utf-8'))
    audit = json.loads((evidence/'network-audit.json').read_text(encoding='utf-8'))
    if audit['network_attempts']: raise RuntimeError(f'DSH attempted network access: {evidence}')
    if trace['status'] != 'completed': raise RuntimeError(f'Incomplete DSH run: {evidence}')
    print(json.dumps(dict(status='completed', evidence=str(evidence), result=trace['result']), ensure_ascii=False, indent=2))
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DSH: prepare and dry-run one Shot, then return a candidate for Human Review.')
    parser.add_argument('shot_id')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--mode', choices=['video', 'first-frame', 'dialogue', 'rough-cut'], default='video')
    args = parser.parse_args()
    launch(args.shot_id, args.data_dir, args.output_dir, args.mode)
