// Exercise the production preflight contract against disposable inputs only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const ts = require('typescript');

const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'pdflow-preflight-'));
const previousRoot = process.env.PD_FLOW_REPO_ROOT;
const previousLoader = require.extensions['.ts'];
process.env.PD_FLOW_REPO_ROOT = fixture;
require.extensions['.ts'] = (module, filename) => {
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    fileName: filename,
  });
  module._compile(compiled.outputText, filename);
};

try {
  const config = path.join(fixture, 'config/pdflow');
  fs.mkdirSync(config, { recursive: true });
  fs.writeFileSync(path.join(config, 'tool_registry.json'), JSON.stringify({
    schema_version: 1, platform: 'linux', default_timeout_seconds: 600, tools: [],
  }));
  fs.writeFileSync(path.join(config, 'action_registry.json'), JSON.stringify({ actions: [] }));
  const { preflightAction } = require('../src/lib/jobs.ts');
  for (const [action, missing] of [
    ['floorplan', '1_synth.odb'], ['activity_power', '6_final.odb'],
    ['system_pdn', '6_final.odb'], ['sta_signoff', '6_final.v'],
  ]) {
    const result = preflightAction(action, { variant: 'flowlab' });
    assert.equal(result.ok, false, action);
    assert.equal(result.code, 'deps', action);
    assert.ok(result.missing.includes(missing), JSON.stringify(result));
  }
  const finish = path.join(fixture, 'tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab');
  fs.mkdirSync(finish, { recursive: true });
  fs.writeFileSync(path.join(finish, '6_final.gds'), 'isolated finish fixture');
  assert.equal(preflightAction('synth', { variant: 'flowlab' }).code, 'forbidden');
  fs.mkdirSync(path.join(fixture, 'learn'), { recursive: true });
  fs.writeFileSync(path.join(fixture, 'learn/.studio-run.lock'), JSON.stringify({
    jobId: 'fixture-lock', action: 'check', pid: process.pid, startedAt: new Date().toISOString(),
  }));
  assert.equal(preflightAction('check').code, 'locked');
  console.log('PASS: isolated missing-input, finish-lock and active-lock contracts');
} finally {
  if (previousRoot === undefined) delete process.env.PD_FLOW_REPO_ROOT;
  else process.env.PD_FLOW_REPO_ROOT = previousRoot;
  if (previousLoader) require.extensions['.ts'] = previousLoader;
  else delete require.extensions['.ts'];
  fs.rmSync(fixture, { recursive: true, force: true });
}
