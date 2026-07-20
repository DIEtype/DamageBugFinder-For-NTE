import { readFileSync, writeFileSync } from 'node:fs';

const path = new URL('../index.html', import.meta.url);
const fragmentPath = new URL('../src/app.fragment.html', import.meta.url);
const appTitle = 'Damage Bug Finder for NTE / 异环NTE数值验算器';
let html = readFileSync(path, 'utf8');
const fragment = readFileSync(fragmentPath, 'utf8').trim();

function decodeAttribute(value) {
  return value
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll('&quot;', '"')
    .replaceAll('&#x27;', "'")
    .replaceAll('&#39;', "'")
    .replaceAll('&amp;', '&');
}

function encodeAttribute(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#x27;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

const iframeMatch = html.match(/(<iframe\b[^>]*\bsrcdoc=")([\s\S]*?)("[^>]*><\/iframe>)/i);
if (!iframeMatch) {
  throw new Error('Unable to locate the standalone iframe srcdoc');
}

const innerHtml = decodeAttribute(iframeMatch[2]);
const calculatorStart = innerHtml.indexOf('<div id="compact-damage-calculator">');
const bodyEnd = innerHtml.lastIndexOf('</body>');
if (calculatorStart < 0 || bodyEnd < calculatorStart) {
  throw new Error('Unable to locate the calculator fragment inside index.html');
}

const synchronizedInnerHtml = `${innerHtml.slice(0, calculatorStart)}${fragment}\n${innerHtml.slice(bodyEnd)}`;
html = html.replace(iframeMatch[0], `${iframeMatch[1]}${encodeAttribute(synchronizedInnerHtml)}${iframeMatch[3]}`);

const marker = 'data-cdc-desktop-bridge';
if (!html.includes(marker)) {
  const bridge = `<script ${marker}>
(() => {
  const frame = document.querySelector('iframe');
  const allowed = new Set(['get_capture_windows', 'capture_panel', 'recognize_uploaded_image']);
  let ready = Boolean(window.pywebview && window.pywebview.api);

  function notifyReady() {
    if (frame && frame.contentWindow) frame.contentWindow.postMessage({ type: 'cdc-api-ready' }, '*');
  }

  window.addEventListener('pywebviewready', () => {
    ready = true;
    notifyReady();
  });

  window.addEventListener('message', async (event) => {
    if (!frame || event.source !== frame.contentWindow) return;
    const message = event.data || {};
    if (message.type === 'cdc-api-probe') {
      if (ready || (window.pywebview && window.pywebview.api)) {
        ready = true;
        notifyReady();
      }
      return;
    }
    if (message.type !== 'cdc-api-call' || !message.id) return;
    if (!allowed.has(message.method)) {
      frame.contentWindow.postMessage({ type: 'cdc-api-result', id: message.id, ok: false, error: '不允许的桌面功能。' }, '*');
      return;
    }
    try {
      if (!window.pywebview || !window.pywebview.api) throw new Error('桌面功能尚未就绪。');
      const result = await window.pywebview.api[message.method](...(message.args || []));
      frame.contentWindow.postMessage({ type: 'cdc-api-result', id: message.id, ok: true, result }, '*');
    } catch (error) {
      frame.contentWindow.postMessage({
        type: 'cdc-api-result', id: message.id, ok: false,
        error: error && error.message ? error.message : String(error)
      }, '*');
    }
  });

  if (ready) notifyReady();
})();
</script>`;
  html = html.replace('</body>', `${bridge}\n</body>`);
}

html = html.replace('max-width:736px;height:', 'max-width:none;height:');
html = html.replace('<html lang="en">', '<html lang="zh-CN">');
html = html.replace(/<title>[^<]*<\/title>/, `<title>${appTitle}</title>`);
html = html.replace(/(<iframe\b[^>]*\btitle=")[^"]*(")/i, `$1${appTitle}$2`);
writeFileSync(path, html, 'utf8');
console.log('Desktop bridge and wide standalone shell: OK');
