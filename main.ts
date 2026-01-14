// main.js - handles webcam capture, calls backend endpoints
const startCamEncBtn = document.getElementById('startCamEnc');
const captureEncBtn = document.getElementById('captureEnc');
const videoEnc = document.getElementById('videoEnc');
const canvasEnc = document.getElementById('canvasEnc');
const gestureEncSpan = document.getElementById('gestureEnc');

const startCamDecBtn = document.getElementById('startCamDec');
const captureDecBtn = document.getElementById('captureDec');
const videoDec = document.getElementById('videoDec');
const canvasDec = document.getElementById('canvasDec');
const gestureDecSpan = document.getElementById('gestureDec');

let streamEnc = null;
let streamDec = null;

async function startCameraFor(videoEl) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    videoEl.srcObject = stream;
    return stream;
  } catch (e) {
    alert('Could not open webcam. Allow camera or try different browser.');
    throw e;
  }
}

startCamEncBtn.onclick = async () => {
  try {
    streamEnc = await startCameraFor(videoEnc);
    videoEnc.style.display = 'block';
    captureEncBtn.disabled = false;
  } catch (e) {}
};

captureEncBtn.onclick = async () => {
  const w = videoEnc.videoWidth;
  const h = videoEnc.videoHeight;
  canvasEnc.width = w;
  canvasEnc.height = h;
  const ctx = canvasEnc.getContext('2d');
  ctx.drawImage(videoEnc, 0, 0, w, h);
  canvasEnc.toBlob(async (blob) => {
    try {
      const fd = new FormData();
      fd.append('snapshot', blob, 'snap.png');
      const res = await fetch('/api/estimate', { method: 'POST', body: fd });
      const j = await res.json();
      if (res.ok) {
        gestureEncSpan.textContent = `gesture: ${j.count}`;
        gestureEncSpan.dataset.gesture = j.count;
      } else {
        alert(j.error || 'Failed to estimate gesture');
      }
    } catch (e) {
      alert('Error estimating gesture: ' + e);
    }
  }, 'image/png');
};

startCamDecBtn.onclick = async () => {
  try {
    streamDec = await startCameraFor(videoDec);
    videoDec.style.display = 'block';
    captureDecBtn.disabled = false;
  } catch (e) {}
};

captureDecBtn.onclick = async () => {
  const w = videoDec.videoWidth;
  const h = videoDec.videoHeight;
  canvasDec.width = w;
  canvasDec.height = h;
  const ctx = canvasDec.getContext('2d');
  ctx.drawImage(videoDec, 0, 0, w, h);
  canvasDec.toBlob(async (blob) => {
    try {
      const fd = new FormData();
      fd.append('snapshot', blob, 'snap2.png');
      const res = await fetch('/api/estimate', { method: 'POST', body: fd });
      const j = await res.json();
      if (res.ok) {
        gestureDecSpan.textContent = `gesture: ${j.count}`;
        gestureDecSpan.dataset.gesture = j.count;
      } else {
        alert(j.error || 'Failed to estimate gesture');
      }
    } catch (e) {
      alert('Error estimating gesture: ' + e);
    }
  }, 'image/png');
};

// ENCRYPT
document.getElementById('encryptBtn').onclick = async () => {
  const coverInput = document.getElementById('cover');
  const message = document.getElementById('message').value;
  const pass = document.getElementById('pass_enc').value;
  const encStatus = document.getElementById('encStatus');

  if (!coverInput.files.length) { alert('Choose a cover image'); return; }
  if (!message || !pass) { alert('Enter message and passcode'); return; }

  encStatus.textContent = 'Encrypting...';

  const fd = new FormData();
  fd.append('cover', coverInput.files[0]);
  fd.append('message', message);
  fd.append('passcode', pass);

  // prefer last-estimated gesture if available
  if (gestureEncSpan.dataset.gesture !== undefined) {
    fd.append('gesture', gestureEncSpan.dataset.gesture);
  } else if (canvasEnc.width) {
    // attach snapshot so backend can estimate
    canvasEnc.toBlob(b => fd.append('snapshot', b, 'snap.png'), 'image/png');
  }

  try {
    const res = await fetch('/api/encrypt', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(()=>({error:'Unknown error'}));
      encStatus.textContent = 'Error: ' + (err.error || 'Failed to encrypt');
      return;
    }
    const blob = await res.blob();
    // save as file
    const a = document.createElement('a');
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = 'stego_encrypted.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    encStatus.textContent = 'Encrypted file downloaded.';
  } catch (e) {
    encStatus.textContent = 'Error: ' + e;
  }
};

// DECRYPT
document.getElementById('decryptBtn').onclick = async () => {
  const stegoInput = document.getElementById('stego');
  const pass = document.getElementById('pass_dec').value;
  const decStatus = document.getElementById('decStatus');

  if (!stegoInput.files.length) { alert('Choose a stego image'); return; }
  if (!pass) { alert('Enter passcode'); return; }

  decStatus.textContent = 'Decrypting...';

  const fd = new FormData();
  fd.append('stego', stegoInput.files[0]);
  fd.append('passcode', pass);

  if (gestureDecSpan.dataset.gesture !== undefined) {
    fd.append('gesture', gestureDecSpan.dataset.gesture);
  } else if (canvasDec.width) {
    canvasDec.toBlob(b => fd.append('snapshot', b, 'snap.png'), 'image/png');
  }

  try {
    const res = await fetch('/api/decrypt', { method: 'POST', body: fd });
    const j = await res.json();
    if (res.ok && j.success) {
      decStatus.textContent = 'Decrypted message: ' + j.message;
    } else {
      decStatus.textContent = 'Error: ' + (j.message || j.error || 'Failed to decrypt');
    }
  } catch (e) {
    decStatus.textContent = 'Error: ' + e;
  }
};
