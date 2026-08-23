/* PyKode — JS bersama */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

var _toastTimer = null;
function toast(msg, type) {
  var el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function () { el.className = 'toast'; }, 3500);
}

function confetti() {
  var emojis = ['🎉', '⭐', '✨', '🎊', '💜', '🌟'];
  for (var i = 0; i < 18; i++) {
    var s = document.createElement('span');
    s.className = 'confetti';
    s.textContent = emojis[Math.floor(Math.random() * emojis.length)];
    s.style.left = (Math.random() * 100) + 'vw';
    s.style.top = (20 + Math.random() * 40) + 'vh';
    s.style.animationDelay = (Math.random() * 0.3) + 's';
    document.body.appendChild(s);
    setTimeout(function (n) { n.remove(); }, 2200);
  }
}

function initEditor(textarea) {
  if (!window.CodeMirror || !textarea) return { getValue: function () { return textarea.value; } };

  /* Fitur bantu ngetik (auto-complete kecil):
     1. Kutip/kurung langsung ditutup otomatis: ' " ( [ {
     2. Enter setelah titik dua (:) langsung kasih indentasi baris baru */
  var PAIRS = { "'": "'", '"': '"', '(': ')', '[': ']', '{': '}' };

  function autoPair(cm, open) {
    var close = PAIRS[open];
    if (cm.somethingSelected()) {
      cm.replaceSelection(open + cm.getSelection() + close);
      return;
    }
    var cur = cm.getCursor();
    var line = cm.getLine(cur.line);
    // Kalau karakter berikutnya sudah penutupnya, cukup lompati saja.
    if (line.charAt(cur.ch) === close) {
      cm.setCursor({ line: cur.line, ch: cur.ch + 1 });
      return;
    }
    cm.replaceSelection(open + close);
    cm.setCursor({ line: cur.line, ch: cur.ch + 1 });
  }

  function smartEnter(cm) {
    var cur = cm.getCursor();
    var line = cm.getLine(cur.line);
    var before = line.slice(0, cur.ch).replace(/\s+$/, '');
    if (before.endsWith(':')) {
      var indent = (line.match(/^\s*/) || [''])[0];
      cm.replaceSelection('\n' + indent + '    ');
      return;
    }
    cm.execCommand('newlineAndIndent');
  }

  var extraKeys = {
    Tab: function (cm) { cm.replaceSelection('    ', 'end'); },
    Enter: smartEnter
  };
  Object.keys(PAIRS).forEach(function (k) {
    extraKeys[k] = (function (open) {
      return function (cm) { autoPair(cm, open); };
    })(k);
  });

  return CodeMirror.fromTextArea(textarea, {
    mode: 'python',
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: false,
    extraKeys: extraKeys
  });
}

/* Badge "Hello, Dunia!" — cukup sekali per halaman */
var _firstRunChecked = false;
function maybeFirstRun() {
  if (_firstRunChecked) return;
  _firstRunChecked = true;
  fetch(PYKODE_BASE + '/api/first-run', { method: 'POST' })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.new) toast('Badge baru: 👋 Hello, Dunia! (+10 XP)', 'good');
    }).catch(function () {});
}

/* Contoh di materi pelajaran */
document.querySelectorAll('.run-example').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var box = btn.closest('.example-box');
    var out = box.querySelector('.example-out');
    out.textContent = '⏳ Menjalankan...';
    out.classList.add('show');
    fetch(PYKODE_BASE + '/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: btn.dataset.code })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.status === 'ok') {
        out.textContent = d.stdout || '(tidak ada output)';
        maybeFirstRun();
      } else {
        out.textContent = '❌ ' + (d.stderr || 'Error');
      }
    }).catch(function () { out.textContent = '❌ Gagal terhubung ke server.'; });
  });
});

/* Kuis pelajaran */
document.querySelectorAll('.quiz-item').forEach(function (item) {
  var inputs = item.querySelectorAll('input[type=radio]');
  inputs.forEach(function (inp) {
    inp.addEventListener('change', function () {
      var answer = parseInt(inp.value, 10);
      var qIndex = parseInt(item.dataset.q, 10);
      var lessonId = item.dataset.lesson;
      inputs.forEach(function (i) { i.disabled = true; });
      fetch(PYKODE_BASE + '/api/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_id: lessonId, q_index: qIndex, answer: answer })
      }).then(function (r) { return r.json(); }).then(function (d) {
        var opts = item.querySelectorAll('.quiz-opt');
        var explain = item.querySelector('.quiz-explain');
        if (d.correct) {
          opts[answer].classList.add('correct');
          explain.innerHTML = '✅ Benar! ' + esc(d.penjelasan || '');
          if (d.xp_added) toast('+' + d.xp_added + ' XP ⭐', 'good');
        } else {
          opts[answer].classList.add('wrong');
          if (d.jawaban_benar != null) opts[d.jawaban_benar].classList.add('correct');
          explain.innerHTML = '❌ Belum tepat. ' + esc(d.penjelasan || '');
        }
        explain.classList.add('show');
      }).catch(function () { inputs.forEach(function (i) { i.disabled = false; }); });
    });
  });
});

/* Tombol petunjuk soal */
document.getElementById('btn-hint')?.addEventListener('click', function () {
  document.getElementById('hint-box').classList.add('show');
  this.remove();
});
