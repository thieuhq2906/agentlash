#!/usr/bin/env node
'use strict';

// Launcher for AgentLash. The Windows .exe is not shipped inside the npm package:
// it is downloaded on first run from the GitHub Release pinned in binary.json and verified
// against the SHA-256 recorded there before it is ever executed. No install scripts are used.

const fs = require('fs');
const os = require('os');
const path = require('path');
const https = require('https');
const crypto = require('crypto');
const { spawn, execFileSync } = require('child_process');

const pkg = require('../package.json');
const binary = require('../binary.json');

const EXE_NAME = 'AgentLash.exe';
const RUN_KEY = 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run';
const ALLOWED_HOSTS = ['github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com'];
const MAX_BYTES = 200 * 1024 * 1024;
const MAX_REDIRECTS = 5;

const installDir = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'AgentLash');
const exePath = path.join(installDir, EXE_NAME);
const systemRoot = process.env.SystemRoot || 'C:\\Windows';
const sys32 = (exe) => path.join(systemRoot, 'System32', exe);

function fail(msg) {
  console.error(`\n❌ ${msg}`);
  process.exit(1);
}

function sha256File(file) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(file, 'r');
  const buf = Buffer.alloc(1024 * 1024);
  try {
    let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) hash.update(buf.subarray(0, n));
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest('hex');
}

function isInstalled() {
  return fs.existsSync(exePath) && sha256File(exePath) === binary.sha256;
}

function isRunning() {
  try {
    const out = execFileSync(sys32('tasklist.exe'), ['/FI', `IMAGENAME eq ${EXE_NAME}`, '/NH'], { encoding: 'utf8' });
    return out.toLowerCase().includes(EXE_NAME.toLowerCase());
  } catch {
    return false;
  }
}

function stopApp() {
  if (!isRunning()) return false;
  try {
    execFileSync(sys32('taskkill.exe'), ['/IM', EXE_NAME, '/F'], { stdio: 'ignore' });
  } catch {
    // already gone
  }
  // Give Windows a moment to release the file lock
  const until = Date.now() + 3000;
  while (isRunning() && Date.now() < until) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
  return true;
}

function checkAllowedUrl(url) {
  const u = new URL(url);
  if (u.protocol !== 'https:') throw new Error(`Từ chối tải qua giao thức không an toàn: ${u.protocol}`);
  if (!ALLOWED_HOSTS.includes(u.hostname)) throw new Error(`Từ chối tải từ máy chủ lạ: ${u.hostname}`);
  return u;
}

function download(url, dest, redirects = 0) {
  return new Promise((resolve, reject) => {
    let u;
    try {
      u = checkAllowedUrl(url);
    } catch (e) {
      return reject(e);
    }
    const req = https.get(u, { headers: { 'User-Agent': `${pkg.name}/${pkg.version}` } }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        if (redirects >= MAX_REDIRECTS) return reject(new Error('Quá nhiều lần chuyển hướng'));
        return resolve(download(new URL(res.headers.location, u).toString(), dest, redirects + 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`Tải thất bại: HTTP ${res.statusCode}`));
      }
      const total = Number(res.headers['content-length']) || binary.size || 0;
      if (total > MAX_BYTES) {
        res.resume();
        return reject(new Error('File tải về lớn bất thường, đã hủy'));
      }
      const hash = crypto.createHash('sha256');
      const out = fs.createWriteStream(dest);
      let received = 0;
      let lastPct = -1;
      res.on('data', (chunk) => {
        received += chunk.length;
        if (received > MAX_BYTES) {
          req.destroy(new Error('File tải về lớn bất thường, đã hủy'));
          return;
        }
        hash.update(chunk);
        if (total && process.stdout.isTTY) {
          const pct = Math.floor((received / total) * 100);
          if (pct !== lastPct) {
            lastPct = pct;
            process.stdout.write(`\r   Đang tải... ${pct}% (${(received / 1048576).toFixed(1)} MB)`);
          }
        }
      });
      res.on('error', reject);
      res.pipe(out);
      out.on('finish', () => {
        if (process.stdout.isTTY) process.stdout.write('\n');
        resolve({ sha256: hash.digest('hex'), size: received });
      });
      out.on('error', reject);
    });
    req.on('error', reject);
    req.setTimeout(60000, () => req.destroy(new Error('Hết thời gian chờ khi tải')));
  });
}

async function install() {
  if (!binary.url || !/^[0-9a-f]{64}$/.test(binary.sha256)) {
    fail('Gói npm này chưa có bản phát hành hợp lệ (binary.json trống).');
  }
  fs.mkdirSync(installDir, { recursive: true });
  const tmp = `${exePath}.download`;
  console.log(`⬇️  Tải AgentLash v${binary.version} từ GitHub Releases...`);
  try {
    const { sha256 } = await download(binary.url, tmp);
    if (sha256 !== binary.sha256) {
      throw new Error(`Mã kiểm tra SHA-256 không khớp!\n   mong đợi: ${binary.sha256}\n   nhận được: ${sha256}\n   File có thể đã bị thay đổi - KHÔNG chạy.`);
    }
    // Only stop the running copy once the replacement is downloaded and verified (the exe is locked while running)
    if (isRunning()) {
      console.log('   Đang tắt bản cũ để cập nhật...');
      stopApp();
    }
    fs.renameSync(tmp, exePath);
  } catch (e) {
    fs.rmSync(tmp, { force: true });
    fail(e.message);
  }
  console.log('✅ Đã tải và xác minh SHA-256.');
}

async function start() {
  if (!isInstalled()) {
    await install();
  } else if (isRunning()) {
    console.log('💥 AgentLash đang chạy rồi! Xem icon ở khay hệ thống (góc phải dưới màn hình).');
    return;
  }
  const child = spawn(exePath, [], { cwd: installDir, detached: true, stdio: 'ignore', windowsHide: false });
  child.on('error', (e) => fail(`Không chạy được ứng dụng: ${e.message}`));
  child.unref();
  console.log('💥 Đã bật AgentLash! Click chuột bất cứ đâu để quất roi. Phím F8: Bật/Tắt.');
  console.log('   Tắt hẳn: chuột phải icon ở khay hệ thống -> Thoát, hoặc gõ: agentlash stop');
}

function uninstall() {
  stopApp();
  try {
    execFileSync(sys32('reg.exe'), ['delete', RUN_KEY, '/v', 'AgentLash', '/f'], { stdio: 'ignore' });
  } catch {
    // autostart was not enabled
  }
  fs.rmSync(installDir, { recursive: true, force: true });
  console.log(`🧹 Đã xóa ${installDir} và tắt khởi động cùng Windows.`);
  console.log('   Gỡ lệnh agentlash: npm uninstall -g agentlash');
}

function help() {
  console.log(`AgentLash v${pkg.version} - quất roi tung màn hình trong lúc đợi agent 💥

Cách dùng:
  agentlash            Bật ứng dụng (lần đầu sẽ tải bản exe${binary.size ? ` ~${Math.round(binary.size / 1048576)} MB` : ''} từ GitHub)
  agentlash stop       Tắt ứng dụng
  agentlash update     Tải lại bản exe khớp với phiên bản gói npm hiện tại
  agentlash folder     Mở thư mục cài đặt (config, hoạt ảnh/âm thanh tùy chỉnh)
  agentlash uninstall  Tắt, xóa file đã tải và tắt khởi động cùng Windows
  agentlash --version  Xem phiên bản

Thư mục cài đặt: ${installDir}`);
}

async function main() {
  if (process.platform !== 'win32') fail('AgentLash chỉ chạy trên Windows.');
  const cmd = (process.argv[2] || 'start').toLowerCase();
  switch (cmd) {
    case 'start':
      return start();
    case 'stop':
      console.log(stopApp() ? '⏹️  Đã tắt AgentLash.' : 'AgentLash không chạy.');
      return;
    case 'update':
      return install();
    case 'folder':
      fs.mkdirSync(installDir, { recursive: true });
      spawn(path.join(systemRoot, 'explorer.exe'), [installDir], { detached: true, stdio: 'ignore' }).unref();
      return;
    case 'uninstall':
      return uninstall();
    case '-v':
    case '--version':
      console.log(pkg.version);
      return;
    case '-h':
    case '--help':
    case 'help':
      return help();
    default:
      help();
      process.exit(1);
  }
}

main().catch((e) => fail(e.message));
