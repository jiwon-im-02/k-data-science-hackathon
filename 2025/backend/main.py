from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from PIL import Image
import io
import numpy as np
import pandas as pd
from pathlib import Path
import uuid

# ----------------------------- App & CORS -----------------------------
app = FastAPI(title="AegisSign API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 개발 중엔 * 허용, 배포시 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------- Data Dir -------------------------------
DATA_DIR = Path(__file__).parent / "user_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def user_dir(user_id: str) -> Path:
    p = DATA_DIR / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p

# ----------------------------- Enroll APIs ----------------------------
@app.post("/enroll/image")
async def enroll_image(
    user_id: str = Form(...),
    refs: List[UploadFile] = File(...),   # 여러 장
):
    """처음 사용자 등록: 기준(참조) 서명 이미지 여러 장 업로드"""
    p = user_dir(user_id)
    saved = 0
    for f in refs:
        ext = Path(f.filename).suffix or ".png"
        out = p / f"{uuid.uuid4().hex}{ext}"
        out.write_bytes(await f.read())
        saved += 1
    return {"user_id": user_id, "saved": saved}

@app.get("/enroll/status")
def enroll_status(user_id: str):
    """등록된 기준 서명 수 확인"""
    p = user_dir(user_id)
    files = list(p.glob("*"))
    return {"user_id": user_id, "count": len(files)}

# ----------------------------- (Optional) User preprocess -------------
try:
    import user_preprocess as UP  # 사용자가 올린 전처리 훅 (있으면 사용)
except Exception:
    UP = None

def default_preprocess_image(img: Image.Image) -> np.ndarray:
    arr = np.asarray(img.convert("L").resize((128,128)), dtype=np.float32) / 255.0
    arr = (arr - arr.mean()) / (arr.std() + 1e-9)
    return arr.flatten()

def default_preprocess_pen_df(df: pd.DataFrame, steps: int = 200) -> np.ndarray:
    if "pressure" not in df.columns:
        df["pressure"] = 0.0
    df = df[["t","x","y","pressure"]].sort_values("t").reset_index(drop=True)
    t = df["t"].to_numpy().astype(float)
    t = (t - t.min()) / (t.max() - t.min() + 1e-9)
    new_t = np.linspace(0, 1, steps)

    def interp(col):
        return np.interp(new_t, t, df[col].to_numpy().astype(float))

    X = np.stack([interp("x"), interp("y"), interp("pressure")], axis=1)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    feats = np.concatenate([X.mean(0), X.std(0)])
    feats = feats / (np.linalg.norm(feats) + 1e-9)
    return feats

def call_user_preprocess_image(img: Image.Image) -> np.ndarray:
    if UP is None:
        return default_preprocess_image(img)
    for name in ["preprocess_image", "image_preprocess", "to_tensor_image", "make_image_tensor"]:
        if hasattr(UP, name):
            fn = getattr(UP, name)
            z = fn(img)
            try:
                import torch
                if "torch" in str(type(z)):
                    z = z.detach().cpu().numpy()
            except Exception:
                pass
            if isinstance(z, np.ndarray):
                return z.reshape(-1)
    return default_preprocess_image(img)

def call_user_preprocess_pen(df: pd.DataFrame) -> np.ndarray:
    if UP is None:
        return default_preprocess_pen_df(df)
    for name in ["preprocess_pen_df", "preprocess_pen", "sequence_preprocess", "make_seq_features"]:
        if hasattr(UP, name):
            fn = getattr(UP, name)
            z = fn(df)
            try:
                import torch
                if "torch" in str(type(z)):
                    z = z.detach().cpu().numpy()
            except Exception:
                pass
            if isinstance(z, np.ndarray):
                return z.reshape(-1)
    return default_preprocess_pen_df(df)

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))

# ----------------------------- Schemas --------------------------------
class VerifyResponse(BaseModel):
    similarities: List[float]
    final: float
    verdict: str

# ----------------------------- Health ---------------------------------
@app.get("/health")
def health():
    return {"ok": True}

# ----------------------------- Verify (Image) -------------------------
@app.post("/verify/image", response_model=VerifyResponse)
async def verify_image(
    probe: UploadFile = File(...),
    refs: Optional[List[UploadFile]] = File(None),   # 직접 기준 전달(선택)
    threshold: float = Query(0.72),
    user_id: Optional[str] = Query(None),            # 등록 기준 사용(선택)
):
    """
    기준(refs[])을 직접 보내거나, user_id로 등록해둔 기준 이미지를 사용해서 검증.
    둘 중 하나는 반드시 제공되어야 합니다.
    """
    # 1) 기준(ref) 이미지 준비
    ref_bytes_list: List[bytes] = []
    if refs:
        for rf in refs:
            ref_bytes_list.append(await rf.read())
    elif user_id:
        p = user_dir(user_id)
        files = sorted(p.glob("*"))
        if not files:
            raise HTTPException(400, detail="등록된 기준 서명이 없습니다. 먼저 /enroll/image 로 등록하세요.")
        ref_bytes_list = [fp.read_bytes() for fp in files]
    else:
        raise HTTPException(400, detail="refs[] 또는 user_id 중 하나는 필수입니다.")

    # 2) probe 준비
    pimg = Image.open(io.BytesIO(await probe.read()))
    pfeat = call_user_preprocess_image(pimg)

    # 3) 유사도 계산
    sims: List[float] = []
    for b in ref_bytes_list:
        rimg = Image.open(io.BytesIO(b))
        rfeat = call_user_preprocess_image(rimg)
        sims.append((cosine(pfeat, rfeat) + 1) / 2)

    final = float(np.mean(sims)) if sims else 0.0
    verdict = "genuine" if final >= threshold else "forgery"
    return {"similarities": sims, "final": final, "verdict": verdict}

# ----------------------------- Verify (Pen) ---------------------------
@app.post("/verify/pen", response_model=VerifyResponse)
async def verify_pen(
    probe: UploadFile = File(...),
    refs: List[UploadFile] = File(...),
    threshold: float = 0.65
):
    pbytes = await probe.read()
    pdf = pd.read_csv(io.BytesIO(pbytes))
    pfeat = call_user_preprocess_pen(pdf)

    sims: List[float] = []
    for rf in refs:
        rdf = pd.read_csv(io.BytesIO(await rf.read()))
        rfeat = call_user_preprocess_pen(rdf)
        sims.append((cosine(pfeat, rfeat) + 1) / 2)

    final = float(np.mean(sims)) if sims else 0.0
    verdict = "genuine" if final >= threshold else "forgery"
    return {"similarities": sims, "final": final, "verdict": verdict}
