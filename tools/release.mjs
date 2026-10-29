#!/usr/bin/env node
// Release tool: build exe -> commit + tag -> push to GitHub -> GitHub Release (exe asset) -> verify -> npm publish
//
//   node tools/release.mjs <version> [--dry-run] [--skip-build] [--skip-npm]
//
// Requirements: python + PyInstaller, git, gh (logged in), npm (logged in, unless --skip-npm).
// The first run also creates the public GitHub repo from npm/package.json "repository" if no "origin" remote exists.

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import https from 'node:https';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NPM_DIR = path.join(ROOT, 'npm');
const PKG_PATH = path.join(NPM_DIR, 'package.json');
const BINARY_PATH = path.join(NPM_DIR, 'binary.json');
const EXE_PATH = path.join(ROOT, 'dist', 'AgentLash.exe');
const SPEC = 'AgentLash.spec';
const ASSET_NAME = 'AgentLash.exe';

const args = process.argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith('--')));
const version = args.find((a) => !a.startsWith('--'));
const DRY = flags.has('--dry-run');

const KNOWN_FLAGS = ['--dry-run', '--skip-build', '--skip-npm'];
for (const f of flags) if (!KNOWN_FLAGS.includes(f)) die(`Unknown flag ${f}`);
if (!version || !/^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$/.test(version)) {
  die('Usage: node tools/release.mjs <version, e.g. 1.0.0> [--dry-run] [--skip-build] [--skip-npm]');
}
const tag = `v${version}`;

function die(msg) {
  console.error(`\n✖ ${msg}`);
  process.exit(1);
}

function step(msg) {
  console.log(`\n▶ ${msg}`);
}

// Runs a command with an argument array (no shell interpolation). npm is a .cmd shim on Windows, so it
// needs a shell; its arguments here are constants or the regex-validated version only.
function run(cmd, cmdArgs, { mutating = true, capture = false, shell = false, cwd = ROOT } = {}) {
  const shown = `${cmd} ${cmdArgs.join(' ')}`;
  if (DRY && mutating) {
    console.log(`  [dry-run] ${shown}`);
    return '';
  }
  console.log(`  $ ${shown}`);
  const opts = { cwd, encoding: 'utf8', stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit', shell };
  return shell ? execFileSync(shown, [], opts) : execFileSync(cmd, cmdArgs, opts);
}

function tryRun(cmd, cmdArgs, opts = {}) {
  try {
    return { ok: true, out: run(cmd, cmdArgs, { mutating: false, capture: true, ...opts }) };
  } catch (e) {
    return { ok: false, out: `${e.stdout || ''}${e.stderr || ''}` };
  }
}

function sha256File(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function fetchSha256(url, redirects = 0) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'agentlash-release' } }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location && redirects < 5) {
        res.resume();
        return resolve(fetchSha256(new URL(res.headers.location, url).toString(), redirects + 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      }
      const hash = createHash('sha256');
      res.on('data', (c) => hash.update(c));
      res.on('end', () => resolve(hash.digest('hex')));
      res.on('error', reject);
    }).on('error', reject);
  });
}

function writeJson(file, data) {
  if (DRY) {
    console.log(`  [dry-run] write ${path.relative(ROOT, file)}: ${JSON.stringify(data)}`);
    return;
  }
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

async function main() {
  const pkg = JSON.parse(fs.readFileSync(PKG_PATH, 'utf8'));
  const repoMatch = /github\.com\/([\w.-]+)\/([\w.-]+?)(\.git)?$/.exec(pkg.repository?.url || '');
  if (!repoMatch) die('npm/package.json "repository.url" must point to a github.com repo');
  const repo = `${repoMatch[1]}/${repoMatch[2]}`;

  console.log(`Release ${pkg.name} ${tag} -> github.com/${repo}${DRY ? '  (DRY RUN: nothing is changed)' : ''}`);

  // ---------- preflight ----------
  step('Preflight checks');
  if (process.platform !== 'win32') die('Build the Windows exe on Windows');
  const status = tryRun('git', ['status', '--porcelain']);
  if (!status.ok) die('Not a git repository');
  if (status.out.trim()) die(`Working tree is not clean. Commit or stash first:\n${status.out}`);
  if (tryRun('git', ['rev-parse', '-q', '--verify', `refs/tags/${tag}`]).ok) die(`Tag ${tag} already exists`);
  const gh = tryRun('gh', ['auth', 'status']);
  if (!gh.ok) die('gh is not logged in: run "gh auth login"');
  if (!flags.has('--skip-npm')) {
    const who = tryRun('npm', ['whoami'], { shell: true });
    if (!who.ok) die('npm is not logged in: run "npm login" (or pass --skip-npm)');
    console.log(`  npm user: ${who.out.trim()}`);
    if (tryRun('npm', ['view', `${pkg.name}@${version}`, 'version'], { shell: true }).out.trim() === version) {
      die(`${pkg.name}@${version} is already on npm`);
    }
  }
  const branch = tryRun('git', ['rev-parse', '--abbrev-ref', 'HEAD']).out.trim();
  console.log(`  branch: ${branch}`);

  // ---------- build ----------
  if (!flags.has('--skip-build')) {
    step('Building exe with PyInstaller');
    run('python', ['-m', 'PyInstaller', '--noconfirm', '--clean', SPEC], { mutating: false });
  }
  if (!fs.existsSync(EXE_PATH)) die(`${EXE_PATH} not found (build first or drop --skip-build)`);
  const sha256 = sha256File(EXE_PATH);
  const size = fs.statSync(EXE_PATH).size;
  console.log(`  ${ASSET_NAME}: ${(size / 1048576).toFixed(1)} MB  sha256=${sha256}`);

  // ---------- version bump ----------
  step('Updating npm/package.json and npm/binary.json');
  const url = `https://github.com/${repo}/releases/download/${tag}/${ASSET_NAME}`;
  writeJson(PKG_PATH, { ...pkg, version });
  writeJson(BINARY_PATH, { version, url, sha256, size });

  // ---------- git ----------
  step('Commit, tag and push');
  run('git', ['add', 'npm/package.json', 'npm/binary.json']);
  run('git', ['commit', '-m', `release: ${tag}`]);
  run('git', ['tag', '-a', tag, '-m', `AgentLash ${tag}`]);
  if (!tryRun('git', ['remote', 'get-url', 'origin']).ok) {
    step(`No "origin" remote: creating public repo github.com/${repo}`);
    run('gh', ['repo', 'create', repo, '--public', '--source', '.', '--remote', 'origin',
      '--description', pkg.description]);
  }
  run('git', ['push', '-u', 'origin', branch]);
  run('git', ['push', 'origin', tag]);

  // ---------- GitHub release ----------
  step('Creating GitHub Release with the exe');
  const notes = [
    `## Cài đặt`,
    '```',
    `npm install -g ${pkg.name}`,
    `agentlash`,
    '```',
    `Hoặc tải trực tiếp **${ASSET_NAME}** bên dưới và nhấp đúp để chạy (Windows 10/11).`,
    '',
    `SHA-256: \`${sha256}\``,
  ].join('\n');
  run('gh', ['release', 'create', tag, `${EXE_PATH}#${ASSET_NAME}`, '--repo', repo,
    '--title', `AgentLash ${tag}`, '--notes', notes, '--verify-tag']);

  // ---------- verify before npm publish ----------
  step('Verifying the published asset checksum');
  if (DRY) {
    console.log(`  [dry-run] download ${url} and compare sha256`);
  } else {
    const remote = await fetchSha256(url);
    if (remote !== sha256) die(`Published asset checksum mismatch (${remote}). npm publish aborted.`);
    console.log('  ✔ checksum matches');
  }

  // ---------- npm ----------
  if (!flags.has('--skip-npm')) {
    step('Publishing to npm');
    run('npm', ['publish', '--access', 'public'], { shell: true, cwd: NPM_DIR });
  }

  console.log(`\n✔ Done${DRY ? ' (dry run)' : ''}: https://github.com/${repo}/releases/tag/${tag}`);
  console.log(`  Users install with: npm install -g ${pkg.name}  then run: agentlash`);
}

main().catch((e) => die(e.message));
