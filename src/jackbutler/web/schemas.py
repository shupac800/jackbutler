from jackbutler.analysis.models import SongAnalysis

# Re-export — the analysis models are already Pydantic and serve as response schemas
AnalyzeResponse = SongAnalysis
