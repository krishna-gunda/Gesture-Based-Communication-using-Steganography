# stego_utils.py
import hashlib
import cv2
import numpy as np
import io

# ---------- Utility: password hash ----------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()[:10]

# ---------- Bit helpers ----------
def _to_bit_array(data_bytes: bytes):
    bits = []
    for b in data_bytes:
        for i in range(8)[::-1]:
            bits.append((b >> i) & 1)
    return bits

def _from_bits_to_bytes(bits):
    bytes_out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        bytes_out.append(byte)
    return bytes(bytes_out)

# ---------- LSB Steganography ----------
def embed_message_lsb_image(img: np.ndarray, message: str) -> np.ndarray:
    msg_bytes = message.encode('utf-8')
    msg_len = len(msg_bytes)
    header = msg_len.to_bytes(4, byteorder='big')
    full = header + msg_bytes
    bits = _to_bit_array(full)

    h, w, c = img.shape
    capacity = h * w * c
    if len(bits) > capacity:
        raise ValueError(f"Message too large to embed. Capacity bits={capacity}, needed={len(bits)}")

    flat = img.flatten()
    for i, bit in enumerate(bits):
        flat[i] = (flat[i] & 254) | bit
    stego = flat.reshape(img.shape)
    return stego

def embed_message_lsb_file(in_bytes: bytes, message: str) -> bytes:
    # Read image from bytes
    arr = np.frombuffer(in_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Invalid image.")
    stego = embed_message_lsb_image(img, message)
    # encode back to PNG
    success, buf = cv2.imencode('.png', stego)
    if not success:
        raise RuntimeError("Failed to encode stego image.")
    return buf.tobytes()

def extract_message_lsb_from_bytes(in_bytes: bytes) -> str:
    arr = np.frombuffer(in_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Invalid image.")
    flat = img.flatten()
    header_bits = [int(flat[i] & 1) for i in range(32)]
    header_bytes = _from_bits_to_bytes(header_bits)
    msg_len = int.from_bytes(header_bytes, byteorder='big')
    total_bits = 32 + msg_len * 8
    if total_bits > flat.size:
        raise ValueError("Image does not contain a valid embedded message or message length corrupted.")
    msg_bits = [int(flat[i] & 1) for i in range(32, total_bits)]
    msg_bytes = _from_bits_to_bytes(msg_bits)
    return msg_bytes.decode('utf-8', errors='replace')

# ---------- Finger count estimation (works on single snapshot) ----------
def estimate_finger_count_from_bytes(image_bytes: bytes) -> int:
    arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Cannot decode image for gesture estimation.")
    # The original code expects an ROI (hand area). We'll assume the client crops into a smaller image already.
    # Convert to HSV and threshold for skin-like colors (works in many conditions)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 30, 60], dtype=np.uint8)
    upper = np.array([20, 150, 255], dtype=np.uint8)
    lower2 = np.array([160, 30, 60], dtype=np.uint8)
    upper2 = np.array([179, 255, 255], dtype=np.uint8)
    mask1 = cv2.inRange(hsv, lower, upper)
    mask2 = cv2.inRange(hsv, lower2, upper2)
    mask = cv2.bitwise_or(mask1, mask2)

    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0
    cnt = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(cnt)
    if area < 1000:
        return 0

    hull = cv2.convexHull(cnt, returnPoints=False)
    if hull is None or len(hull) < 3:
        return 0
    defects = cv2.convexityDefects(cnt, hull)
    if defects is None:
        return 0
    finger_count = 0
    for i in range(defects.shape[0]):
        s,e,f,d = defects[i,0]
        start = tuple(cnt[s][0])
        end = tuple(cnt[e][0])
        far = tuple(cnt[f][0])
        a = np.linalg.norm(np.array(end) - np.array(start))
        b = np.linalg.norm(np.array(far) - np.array(start))
        c = np.linalg.norm(np.array(end) - np.array(far))
        if b*c == 0:
            continue
        angle = np.arccos(max(-1.0, min(1.0, (b*b + c*c - a*a) / (2*b*c))))
        if angle <= np.pi/2 and d > 10000:
            finger_count += 1
    return max(0, min(5, finger_count + 1))
