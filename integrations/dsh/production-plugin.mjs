// Out-of-tree DSH plugin: documented defineTool + tools.execute + appReady/appExit.
import { defineTool } from '@deepseek-ai/dsh-tools';
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';

export const name = 'aigc-production';
export const inject = ['tools', 'cmdlineArgs'];

export function apply(ctx, config) {
  const controller = new AbortController();
  ctx.effect(() => () => controller.abort());
  const trace = { harness: 'DeepSeek Harness', version: '0.1.5-rc.2', mode: 'local-keyless',
    shot_id: config.shotId, started_at: new Date().toISOString(), status: 'running', steps: [],
    observed_tool_results: [], video_api_calls: 0, model_api_calls: 0 };
  const save = () => writeFileSync(join(config.evidenceDir, 'trace.json'), JSON.stringify(trace, null, 2));
  save();
  ctx.on('tools/result', (execution, result) => {
    trace.observed_tool_results.push({ tool: execution.name, at: new Date().toISOString(),
      content_blocks: result.content.length });
    save();
  });

  const specifications = [
    ['prepare_rough_cut', 'timeline_id', 'Assemble saved human order and selected media into OTIO and Preview. Never edit order or selections.'],
    ['get_shot_context', 'shot_id', 'Read Shot, Character/Look, Scene/State, references and review state.'],
    ['build_generation_task', 'shot_id', 'Persist the existing neutral Task and pending fal Fixture execution.'],
    ['dry_run_generation', 'execution_id', 'Run only the existing zero-call fal fixture and ingest its actual local MP4.'],
    ['prepare_dialogue_audio', 'dialogue_id', 'Prepare neutral audio task, run local TTS/WhisperX fixtures, persist WAV and SRT. Never select.'],
    ['prepare_shot_first_frame', 'shot_id', 'Build ComfyUI workflow, run local image Fixture, ingest PNG and return HumanReviewRequired. Never promote.'],
    ['inspect_media', 'result_id', 'Inspect an ingested result with the existing ffprobe tool.'],
  ];
  const childEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
    ['PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATHEXT', 'COMSPEC'].includes(key.toUpperCase())));
  Object.assign(childEnv, { PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' });

  function bridge(tool, args) {
    return new Promise((resolve, reject) => {
      const child = spawn(config.python, ['-m', 'integrations.production_bridge', '--data-dir', config.dataDir], {
        cwd: config.projectRoot, env: childEnv, windowsHide: true, shell: false,
        signal: controller.signal, stdio: ['pipe', 'pipe', 'pipe'],
      });
      let stdout = '', stderr = '';
      const timeout = setTimeout(() => { child.kill(); reject(new Error('Production tool timed out')); }, 90000);
      child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8');
      child.stdout.on('data', chunk => { stdout += chunk; });
      child.stderr.on('data', chunk => { stderr += chunk; });
      child.once('error', error => { clearTimeout(timeout); reject(error); });
      child.once('close', code => {
        clearTimeout(timeout);
        try {
          const response = JSON.parse(stdout);
          if (code !== 0 || !response.ok) throw new Error(response.error || `Bridge exit ${code}`);
          if (response.network_attempts !== 0) throw new Error('Unexpected bridge network attempt');
          resolve(JSON.stringify(response.output));
        } catch (error) { reject(new Error(error.message + (stderr ? `; ${stderr.slice(-500)}` : ''))); }
      });
      child.stdin.on('error', () => {});
      child.stdin.end(JSON.stringify({ tool, arguments: args }));
    });
  }
  for (const [tool, key, description] of specifications) {
    ctx.tools.register(defineTool({ name: tool, description,
      parameters: { [key]: { type: 'string', required: true, description: 'Stable production record ID' } },
      output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
      execute: args => bridge(tool, args),
    }));
  }

  function summarize(output) {
    if (output.shot) return { shot_id: output.shot.id, character: output.character.name,
      look: output.look.name, scene: output.scene?.name, state: output.scene_state?.name,
      character_references: output.character_references.length,
      scene_references: output.scene_references.length, results: output.executions.length,
      selected_take: output.selected_take };
    return output;
  }
  async function call(tool, args) {
    const step = { tool, input: args, started_at: new Date().toISOString(), status: 'running' };
    trace.steps.push(step); save();
    try {
      const result = await ctx.tools.execute({ callId: `production-${trace.steps.length}`,
        name: tool, arguments: args, signal: controller.signal });
      if (result.isError) throw new Error(JSON.stringify(result.content));
      const output = JSON.parse(result.content.filter(b => b.type === 'text').map(b => b.text).join(''));
      step.output = summarize(output); step.status = 'completed';
      return output;
    } catch (error) { step.status = 'failed'; step.error = error.message; throw error; }
    finally { step.finished_at = new Date().toISOString(); save(); }
  }
  async function run() {
    try {
      if (config.mode === 'rough-cut') {
        const result = await call('prepare_rough_cut', { timeline_id: config.timelineId });
        if (!result.human_gate_unchanged || !result.human_review_required) throw new Error('Human Gate changed');
        trace.status = 'completed'; trace.result = result; trace.finished_at = new Date().toISOString(); save(); ctx.get('appExit')(0); return;
      }
      if (config.mode === 'dialogue') {
        const result = await call('prepare_dialogue_audio', { dialogue_id: config.dialogueId });
        if (!result.human_gate_unchanged || !result.human_review_required) throw new Error('Human Gate changed');
        trace.status = 'completed'; trace.result = result; trace.finished_at = new Date().toISOString(); save(); ctx.get('appExit')(0); return;
      }
      const before = await call('get_shot_context', { shot_id: config.shotId });
      if (config.mode === 'first-frame') {
        const result = await call('prepare_shot_first_frame', { shot_id: config.shotId });
        const after = await call('get_shot_context', { shot_id: config.shotId });
        if (before.selected_take !== after.selected_take || !result.selected_first_frame_unchanged) throw new Error('Human Gate changed');
        trace.status = 'completed'; trace.result = { ...result, human_gate_unchanged: true };
        trace.finished_at = new Date().toISOString(); save(); ctx.get('appExit')(0); return;
      }
      const task = await call('build_generation_task', { shot_id: config.shotId });
      const result = await call('dry_run_generation', { execution_id: task.execution_id });
      const media = await call('inspect_media', { result_id: result.result_id });
      const after = await call('get_shot_context', { shot_id: config.shotId });
      if (before.selected_take !== after.selected_take ||
          JSON.stringify(before.rejected) !== JSON.stringify(after.rejected)) {
        throw new Error('Human Gate was unexpectedly changed');
      }
      trace.status = 'completed';
      trace.result = { ...result, media, human_gate_unchanged: true };
      trace.finished_at = new Date().toISOString(); save();
      console.log(JSON.stringify({ status: trace.status, ...trace.result }));
      ctx.get('appExit')(0);
    } catch (error) {
      trace.status = 'failed'; trace.error = error.message;
      trace.finished_at = new Date().toISOString(); save();
      console.error(error.message); ctx.get('appExit')(1);
    }
  }
  const ready = ctx.get('appReady');
  if (!ready || !ctx.get('appExit')) throw new Error('Launch this plugin through the official dsh CLI');
  ctx.effect(() => ready.onReady(() => { void run(); }));
}
