from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pathlib import Path

from jackbutler.analysis.engine import AnalysisEngine
from jackbutler.parsing.gp_parser import GPParser
from jackbutler.web.schemas import AnalyzeResponse

router = APIRouter()
engine = AnalysisEngine()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TEARS_GP = PROJECT_ROOT / "tabs" / "tears.gp"


@router.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/api/demo", response_model=AnalyzeResponse)
async def demo():
    contents = TEARS_GP.read_bytes()
    song = GPParser.parse(contents, "tears.gp")
    analysis = engine.analyze(song)
    return analysis


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    filename = file.filename or "upload.gp5"
    song = GPParser.parse(contents, filename)
    analysis = engine.analyze(song)
    return analysis
