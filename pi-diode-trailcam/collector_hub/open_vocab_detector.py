#!/usr/bin/env python3
"""
File: collector_hub/open_vocab_detector.py
Description: Multi-Category Open-Vocabulary Object Detector (YOLOWorld-v2 Large + CLIP ViT-B/32 on Apple Metal MPS).
             Identifies all object categories (People, Power/Hand Tools, Blades/Weapons, Personal Electronics,
             Wearables & Everyday Carry, Drinkware & Kitchen, Wildlife/Animals, Vehicles/Drones, and Room Furniture)
             and tags each detection with its semantic category so the Operator UI can filter out background noise.
License: MIT
"""
import os
import time
import threading
import cv2
import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

OPEN_VOCAB_CLASSES = [
    # 1. People
    "person",
    # 2. Power & Hand Tools / Appliances
    "power drill", "cordless drill", "hammer", "screwdriver", "pliers", "wrench",
    "flashlight", "tape measure", "saw", "vacuum cleaner",
    # 3. Blades & Weapons
    "scissors", "knife", "baseball bat",
    # 4. Personal Electronics
    "cell phone", "remote control", "headphones", "laptop", "computer keyboard",
    "computer mouse", "camera", "television",
    # 5. Wearables & Everyday Carry
    "eyeglasses", "sunglasses", "wristwatch", "hat", "backpack", "handbag",
    "suitcase", "wallet", "keys", "book", "pen", "shoes",
    # 6. Drinkware & Kitchen
    "coffee mug", "cup", "water bottle", "can", "wine glass", "bowl", "plate", "fork", "spoon",
    # 7. Animals & Wildlife
    "dog", "cat", "bird", "deer", "bear", "fox",
    # 8. Vehicles & Drones
    "car", "truck", "bicycle", "motorcycle", "drone",
    # 9. Room Furniture & Fixtures (Background / Noise-Filterable)
    "couch", "chair", "dining table", "desk", "bookshelf", "potted plant",
    "vase", "lamp", "chandelier", "picture frame", "clock", "pillow",
]

CATEGORY_BY_CLASS = {
    "person": "person",
    # Tools
    "power drill": "tool", "cordless drill": "tool", "hammer": "tool", "screwdriver": "tool",
    "pliers": "tool", "wrench": "tool", "flashlight": "tool", "tape measure": "tool",
    "saw": "tool", "vacuum cleaner": "tool",
    # Weapons
    "scissors": "weapon", "knife": "weapon", "baseball bat": "weapon",
    # Electronics (Personal / Interactive Tech)
    "cell phone": "electronics", "remote control": "electronics", "headphones": "electronics",
    "laptop": "electronics", "computer keyboard": "electronics", "computer mouse": "electronics",
    "camera": "electronics",
    # Wearables & Everyday Carry
    "eyeglasses": "wearables", "sunglasses": "wearables", "wristwatch": "wearables",
    "hat": "wearables", "backpack": "wearables", "handbag": "wearables", "suitcase": "wearables",
    "wallet": "wearables", "keys": "wearables", "book": "wearables", "pen": "wearables", "shoes": "wearables",
    # Drinkware & Kitchen
    "coffee mug": "drinkware", "cup": "drinkware", "water bottle": "drinkware", "can": "drinkware",
    "wine glass": "drinkware", "bowl": "drinkware", "plate": "drinkware", "fork": "drinkware", "spoon": "drinkware",
    # Wildlife
    "dog": "wildlife", "cat": "wildlife", "bird": "wildlife",
    "deer": "wildlife", "bear": "wildlife", "fox": "wildlife",
    # Vehicles
    "car": "vehicle", "truck": "vehicle", "bicycle": "vehicle",
    "motorcycle": "vehicle", "drone": "vehicle",
    # Furniture & Room Decor (Static Room Background)
    "couch": "furniture", "chair": "furniture", "dining table": "furniture", "desk": "furniture",
    "bookshelf": "furniture", "potted plant": "furniture", "vase": "furniture", "lamp": "furniture",
    "chandelier": "furniture", "picture frame": "furniture", "clock": "furniture", "pillow": "furniture",
    "television": "furniture",
}

COCO_NAME_NORMALIZATION = {
    "tv": "television",
    "cell_phone": "cell phone",
    "potted_plant": "potted plant",
    "dining_table": "dining table",
    "wine_glass": "wine glass",
    "baseball_bat": "baseball bat",
    "sports_ball": "ball",
    "remote": "remote control",
    "keyboard": "computer keyboard",
    "mouse": "computer mouse",
    "bottle": "water bottle",
}

HANDHELD_CANDIDATE_CLASSES = {
    "power drill", "cordless drill", "hammer", "screwdriver", "pliers", "wrench",
    "flashlight", "tape measure", "saw",
    "scissors", "knife", "baseball bat",
    "cell phone", "remote control", "headphones", "computer mouse", "camera",
    "coffee mug", "cup", "water bottle", "can", "wine glass", "fork", "spoon",
    "wallet", "keys", "book", "pen",
}

CLIP_VERIFICATION_PROMPTS = [
    ("cordless drill", "a photo of a hand holding a cordless power drill or electric drill tool"),
    ("hammer", "a photo of a hand holding a hammer tool"),
    ("screwdriver", "a photo of a hand holding a manual screwdriver tool"),
    ("pliers", "a photo of a hand holding metal pliers or wire cutters"),
    ("wrench", "a photo of a hand holding a metal wrench or spanner"),
    ("flashlight", "a photo of a hand holding a cylindrical flashlight torch"),
    ("tape measure", "a photo of a hand holding a tape measure"),
    ("saw", "a photo of a hand holding a hand saw"),
    ("scissors", "a photo of a hand holding a pair of scissors or shears"),
    ("knife", "a photo of a hand holding a knife blade"),
    ("cell phone", "a photo of a hand holding a smartphone or mobile cell phone"),
    ("remote control", "a photo of a hand holding a TV remote control"),
    ("headphones", "a photo of headphones or headset"),
    ("computer mouse", "a photo of a computer mouse"),
    ("camera", "a photo of a digital camera"),
    ("coffee mug", "a photo of a coffee mug or ceramic cup"),
    ("water bottle", "a photo of a water bottle or drink bottle"),
    ("can", "a photo of a soda can or aluminum beverage can"),
    ("wine glass", "a photo of a drinking glass or wine glass"),
    ("bowl", "a photo of a ceramic bowl or dish"),
    ("fork", "a photo of a metal fork"),
    ("spoon", "a photo of a metal spoon"),
    ("wallet", "a photo of a wallet"),
    ("keys", "a photo of metal keys"),
    ("book", "a photo of a book or paperback"),
    ("pen", "a photo of a pen or pencil"),
    ("_reject", "an empty human hand or fingers holding nothing"),
    ("_reject", "a person's shirt, sweater, sleeve, pants, or clothing fabric"),
    ("_reject", "a chair, couch cushion, pillow, table, cabinet, or wall background"),
]


def _box_iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / (area_a + area_b - inter)


def _box_containment(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / min(area_a, area_b)


class OpenVocabDetector:
    """Thread-safe singleton wrapper for YOLOWorld-v2 + CLIP ViT-B/32 on Apple Silicon MPS."""

    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False
        self._failed = False
        self.device = "cpu"
        self.yw = None
        self.clip_model = None
        self.clip_preprocess = None
        self.text_features = None
        self.last_infer_ts = 0.0
        self.last_dets = []
        self.last_ms = 0.0

    def _ensure_loaded(self):
        if self._initialized or self._failed:
            return self._initialized
        try:
            import torch
            from ultralytics import YOLOWorld, YOLO

            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
            orig_cwd = os.getcwd()
            os.makedirs(MODELS_DIR, exist_ok=True)
            try:
                os.chdir(MODELS_DIR)
                yw_path = os.path.join(MODELS_DIR, "yolov8l-worldv2.pt")
                if not os.path.isfile(yw_path):
                    yw_path = os.path.join(MODELS_DIR, "yolov8s-worldv2.pt")
                if os.path.isfile(yw_path):
                    try:
                        self.yw = YOLOWorld(yw_path)
                        self.yw.set_classes(OPEN_VOCAB_CLASSES)
                    except Exception:
                        self.yw = YOLO("yolov8n.pt")
                else:
                    self.yw = YOLO("yolov8n.pt")

                try:
                    import clip
                    clip_path = os.path.join(MODELS_DIR, "clip", "ViT-B-32.pt")
                    if os.path.isfile(clip_path):
                        self.clip_model, self.clip_preprocess = clip.load(clip_path, device=self.device)
                    else:
                        self.clip_model, self.clip_preprocess = clip.load(
                            "ViT-B/32", device=self.device, download_root=os.path.join(MODELS_DIR, "clip")
                        )

                    with torch.no_grad():
                        toks = clip.tokenize([p[1] for p in CLIP_VERIFICATION_PROMPTS]).to(self.device)
                        t_feats = self.clip_model.encode_text(toks)
                        self.text_features = t_feats / t_feats.norm(dim=-1, keepdim=True)
                except Exception:
                    self.clip_model = None
                    self.clip_preprocess = None
                    self.text_features = None

                # Warmup pass on a tiny dummy canvas so first live frame is fast
                dummy = np.zeros((320, 320, 3), dtype=np.uint8)
                self.yw.predict(dummy, imgsz=320, conf=0.25, device=self.device, verbose=False)
            finally:
                os.chdir(orig_cwd)

            self._initialized = True
            print(f"[+] OpenVocabDetector loaded on {self.device.upper()} ({len(OPEN_VOCAB_CLASSES)} classes)")
            return True
        except Exception as e:
            print(f"[!] OpenVocabDetector failed to initialize: {e}")
            self._failed = True
            return False

    def detect_on_jpeg(self, jpeg_bytes, pi5_raw_dets=None, min_interval_s=0.18):
        """
        Runs multi-category open-vocabulary detection on `jpeg_bytes`.
        Returns (merged_detections, infer_ms).
        """
        now = time.time()
        if (now - self.last_infer_ts) < min_interval_s and self.last_dets:
            return self.last_dets, self.last_ms

        with self._lock:
            if not self._ensure_loaded():
                return self._normalize_pi5_only(pi5_raw_dets or []), 0.0

            t0 = time.time()
            try:
                import torch
                from PIL import Image

                arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if bgr is None:
                    return self._normalize_pi5_only(pi5_raw_dets or []), 0.0

                H, W = bgr.shape[:2]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

                res = self.yw.predict(
                    bgr, imgsz=960, conf=0.05, iou=0.45, device=self.device, verbose=False
                )[0]

                dets = []
                person_boxes = []
                for i in range(len(res.boxes)):
                    cid = int(res.boxes.cls[i].item())
                    cf = float(res.boxes.conf[i].item())
                    if hasattr(res, "names") and isinstance(res.names, dict) and cid in res.names:
                        cname = str(res.names[cid])
                    else:
                        cname = OPEN_VOCAB_CLASSES[cid] if cid < len(OPEN_VOCAB_CLASSES) else "object"
                    cname = COCO_NAME_NORMALIZATION.get(cname, cname)
                    if cname == "power drill":
                        cname = "cordless drill"
                    box = [round(float(v), 4) for v in res.boxes.xyxyn[i].tolist()]
                    if cname == "person" and cf >= 0.25:
                        person_boxes.append(box)
                    dets.append({
                        "class": cname,
                        "category": CATEGORY_BY_CLASS.get(cname, "furniture"),
                        "conf": round(cf, 3),
                        "box": box,
                        "source": "standing",
                    })

                kept_dets = []
                for d in dets:
                    cname = d["class"]
                    cf = d["conf"]
                    x1, y1, x2, y2 = d["box"]
                    cx, cy = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
                    near_p = any(
                        (px1 - 0.04 <= cx <= px2 + 0.04 and py1 - 0.03 <= cy <= py2 + 0.03)
                        for (px1, py1, px2, py2) in person_boxes
                    )
                    d["near_person"] = bool(near_p or cname == "person")

                    if (
                        self.clip_model is not None
                        and cname in HANDHELD_CANDIDATE_CLASSES
                        and near_p
                        and (x2 - x1) * (y2 - y1) < 0.14
                    ):
                        bw, bh = x2 - x1, y2 - y1
                        cx1 = max(0, int((x1 - 0.18 * bw) * W))
                        cy1 = max(0, int((y1 - 0.18 * bh) * H))
                        cx2 = min(W, int((x2 + 0.18 * bw) * W))
                        cy2 = min(H, int((y2 + 0.18 * bh) * H))
                        if (cx2 - cx1) >= 16 and (cy2 - cy1) >= 16:
                            crop_in = (
                                self.clip_preprocess(Image.fromarray(rgb[cy1:cy2, cx1:cx2]))
                                .unsqueeze(0)
                                .to(self.device)
                            )
                            with torch.no_grad():
                                ifeat = self.clip_model.encode_image(crop_in)
                                ifeat = ifeat / ifeat.norm(dim=-1, keepdim=True)
                                probs = (100.0 * ifeat @ self.text_features.T).softmax(dim=-1).cpu().numpy()[0]
                            top_i = int(np.argmax(probs))
                            top_cls = CLIP_VERIFICATION_PROMPTS[top_i][0]
                            top_p = float(probs[top_i])
                            if top_cls == "_reject":
                                if cf < 0.30:
                                    continue
                            elif top_p >= 0.30:
                                d["class"] = top_cls
                                d["category"] = CATEGORY_BY_CLASS.get(top_cls, "tool")
                                d["conf"] = round(max(cf, min(0.92, 0.65 * top_p + 0.16)), 3)
                            elif top_cls == cname and top_p >= 0.16:
                                d["conf"] = round(max(cf, 0.24), 3)
                            elif cf < 0.12:
                                continue
                    else:
                        # Suppress low-confidence background/scene noise
                        min_cf = 0.18 if d["category"] == "furniture" else 0.12
                        if cf < min_cf:
                            continue

                    kept_dets.append(d)

                # Also merge any non-overlapping high-confidence detections from Pi 5 YOLOv8n (e.g. cell phone)
                for pd in (pi5_raw_dets or []):
                    raw_c = str(pd.get("class", "")).strip().lower()
                    norm_c = COCO_NAME_NORMALIZATION.get(raw_c, raw_c.replace("_", " "))
                    p_cf = float(pd.get("conf", 0.0))
                    p_box = pd.get("box") or [0, 0, 0, 0]
                    if norm_c not in CATEGORY_BY_CLASS or p_cf < 0.22:
                        continue
                    cat = CATEGORY_BY_CLASS[norm_c]
                    if cat == "furniture" and p_cf < 0.35:
                        continue
                    overlaps = any(
                        _box_iou(p_box, kd["box"]) >= 0.35 and (kd["class"] == norm_c or kd["category"] == cat)
                        for kd in kept_dets
                    )
                    if not overlaps:
                        pcx = 0.5 * (float(p_box[0]) + float(p_box[2]))
                        pcy = 0.5 * (float(p_box[1]) + float(p_box[3]))
                        p_near = any(
                            (px1 - 0.08 <= pcx <= px2 + 0.08 and py1 - 0.05 <= pcy <= py2 + 0.05)
                            for (px1, py1, px2, py2) in person_boxes
                        )
                        kept_dets.append({
                            "class": norm_c,
                            "category": cat,
                            "conf": round(p_cf, 3),
                            "box": [round(float(v), 4) for v in p_box],
                            "near_person": bool(p_near or norm_c == "person"),
                            "source": "standing",
                        })

                # Final NMS & per-class deduplication
                kept_dets.sort(key=lambda x: float(x["conf"]), reverse=True)
                final_dets = []
                bg_counts = {}
                for d in kept_dets:
                    dup = False
                    for fd in final_dets:
                        ov = _box_iou(d["box"], fd["box"])
                        cont = _box_containment(d["box"], fd["box"])
                        if d["class"] == fd["class"] and (ov >= 0.35 or cont >= 0.65):
                            dup = True
                            break
                        if (
                            d["category"] not in ("person", "furniture")
                            and fd["category"] not in ("person", "furniture")
                            and (ov >= 0.50 or cont >= 0.75)
                        ):
                            dup = True
                            break
                    if dup:
                        continue
                    if d["category"] == "furniture":
                        c_cnt = bg_counts.get(d["class"], 0)
                        if c_cnt >= 3:
                            continue
                        bg_counts[d["class"]] = c_cnt + 1
                    final_dets.append(d)

                infer_ms = round((time.time() - t0) * 1000.0, 1)
                self.last_infer_ts = time.time()
                self.last_dets = final_dets
                self.last_ms = infer_ms
                return final_dets, infer_ms
            except Exception as e:
                print(f"[!] OpenVocabDetector inference error: {e}")
                return self._normalize_pi5_only(pi5_raw_dets or []), 0.0

    def _normalize_pi5_only(self, pi5_raw_dets):
        out = []
        for pd in pi5_raw_dets:
            raw_c = str(pd.get("class", "")).strip().lower()
            norm_c = COCO_NAME_NORMALIZATION.get(raw_c, raw_c.replace("_", " "))
            cat = CATEGORY_BY_CLASS.get(norm_c, "furniture")
            out.append({
                "class": norm_c,
                "category": cat,
                "conf": round(float(pd.get("conf", 0.0)), 3),
                "box": pd.get("box") or [0, 0, 0, 0],
                "source": pd.get("source", "standing"),
            })
        return out


GLOBAL_DETECTOR = OpenVocabDetector()
