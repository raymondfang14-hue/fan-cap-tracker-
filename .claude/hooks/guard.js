#!/usr/bin/env node
// Claude Code hook for PlainStats. Reads the tool call as JSON on stdin.
//   pre  : blocks direct edits to index.html (it is generated from src.html by build.sh).
//   post : after src.html changes, rebuilds index.html; after a data/*.json change, checks the JSON parses.
// Exit code 2 sends stderr back to Claude so it can correct course.
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const mode = process.argv[2];
let input = '';
process.stdin.on('data', c => (input += c));
process.stdin.on('end', () => {
  let call = {};
  try { call = JSON.parse(input); } catch { process.exit(0); }
  const file = (call.tool_input && (call.tool_input.file_path || call.tool_input.notebook_path)) || '';
  const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const rel = path.relative(root, path.resolve(root, file));

  if (mode === 'pre' && rel === 'index.html') {
    console.error('index.html is generated. Edit src.html instead; build.sh rebuilds index.html automatically.');
    process.exit(2);
  }

  if (mode === 'post' && rel === 'src.html') {
    try { execFileSync('sh', [path.join(root, 'build.sh')], { stdio: 'pipe' }); }
    catch (e) { console.error('build.sh failed: ' + (e.stderr || e.message)); process.exit(2); }
  }

  if (mode === 'post' && /^data\/.+\.json$/.test(rel)) {
    try { JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8')); }
    catch (e) { console.error(`${rel} is no longer valid JSON: ${e.message}. The site will fail to load it.`); process.exit(2); }
  }
});
