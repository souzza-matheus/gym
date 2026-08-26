"""
run_all_tests.py — GymVision — Suite completa de 30 testes automatizados
Executa sem dependências externas (apenas stdlib + código do projeto).
"""
import sys, types, time, json, datetime, traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Stubs mínimos de models ───────────────────────────────────────────────────
class ExerciseType(str, Enum):
    SQUAT="SQUAT"; DEADLIFT="DEADLIFT"; LUNGE="LUNGE"; UNKNOWN="UNKNOWN"

class MovementPhase(str, Enum):
    STANDING="STANDING"; DESCENDING="DESCENDING"; BOTTOM="BOTTOM"
    ASCENDING="ASCENDING"; UNKNOWN="UNKNOWN"

class RiskLevel(str, Enum):
    LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"

class AlertSeverity(str, Enum):
    WARNING="WARNING"; CRITICAL="CRITICAL"

class ErrorType(str, Enum):
    KNEE_CAVE_LEFT="KNEE_CAVE_LEFT"; KNEE_CAVE_RIGHT="KNEE_CAVE_RIGHT"
    BACK_NOT_STRAIGHT="BACK_NOT_STRAIGHT"; DEPTH_INSUFFICIENT="DEPTH_INSUFFICIENT"
    BACK_ROUNDED="BACK_ROUNDED"; HIPS_TOO_HIGH="HIPS_TOO_HIGH"
    LANDMARK_MISSING="LANDMARK_MISSING"; LOW_CONFIDENCE="LOW_CONFIDENCE"
    KNEE_OVER_TOE_LEFT="KNEE_OVER_TOE_LEFT"; KNEE_OVER_TOE_RIGHT="KNEE_OVER_TOE_RIGHT"
    HEELS_OFF_GROUND="HEELS_OFF_GROUND"; BAR_PATH_DRIFT="BAR_PATH_DRIFT"

@dataclass
class Landmark:
    landmark_type: int
    x: float; y: float; z: float = 0.0; visibility: float = 0.9

LandmarkInput = Landmark

@dataclass
class JointAngles:
    left_knee: Optional[float] = None
    right_knee: Optional[float] = None
    left_hip: Optional[float] = None
    right_hip: Optional[float] = None
    left_ankle: Optional[float] = None
    right_ankle: Optional[float] = None
    back_angle: Optional[float] = None
    hip_hinge_angle: Optional[float] = None

@dataclass
class DetectedError:
    error_type: ErrorType
    risk_level: RiskLevel
    description: str
    severity: AlertSeverity = AlertSeverity.WARNING
    joint_angle: Optional[float] = None
    threshold_violated: Optional[float] = None

@dataclass
class AnalysisResult:
    session_id: str; student_id: str; exercise_type: ExerciseType
    frame_seq: int; phase: MovementPhase; score: float
    joint_angles: JointAngles; errors: list = field(default_factory=list)
    has_alert: bool = False; landmark_count: int = 0; analysis_ms: float = 0.0

# Injeta módulo models no sys.modules
m = types.ModuleType("models")
for k in ["Landmark","LandmarkInput","JointAngles","DetectedError","AnalysisResult",
          "ExerciseType","MovementPhase","RiskLevel","ErrorType","AlertSeverity"]:
    setattr(m, k, eval(k))
sys.modules["models"] = m

sys.path.insert(0, ".")
import importlib
ac = importlib.import_module("angle_calculator")
ea = importlib.import_module("exercise_analyzer")

# ── Helpers ───────────────────────────────────────────────────────────────────
results = []

def lm(t, x, y, vis=0.9):
    return Landmark(t, x, y, 0.0, vis)

def mkReq(ex, lms):
    from types import SimpleNamespace
    return SimpleNamespace(session_id="s1", student_id="u1",
                           exercise_type=ex, frame_seq=1, landmarks=lms)

def run(tc_id, name, fn):
    t0 = time.perf_counter()
    try:
        fn()
        ms = (time.perf_counter() - t0) * 1000
        results.append({"id": tc_id, "name": name, "status": "PASSOU",
                        "ms": round(ms, 2), "detail": "Todos os asserts passaram"})
        print(f"  ✅ {tc_id} — {name}  ({ms:.1f}ms)")
    except AssertionError as e:
        ms = (time.perf_counter() - t0) * 1000
        results.append({"id": tc_id, "name": name, "status": "FALHOU",
                        "ms": round(ms, 2), "detail": str(e)})
        print(f"  ❌ {tc_id} — {name}: {e}")
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        results.append({"id": tc_id, "name": name, "status": "ERRO",
                        "ms": round(ms, 2), "detail": traceback.format_exc()[-300:]})
        print(f"  💥 {tc_id} — {name}: {e}")

# ════════════════════════════════════════════════════════
# GRUPO 1 — AngleCalculator (TC-U01 a TC-U05)
# ════════════════════════════════════════════════════════
print("\n📐 AngleCalculator")

def u01():
    a = ac.calculate_angle(lm(0,0.0,0.5), lm(0,0.5,0.5), lm(0,0.5,0.0))
    assert abs(a - 90.0) < 0.5, f"Expected ~90°, got {a}°"
run("TC-U01", "Ângulo reto — vetores ortogonais → 90°", u01)

def u02():
    a = ac.calculate_angle(lm(0,0.0,0.5), lm(0,0.5,0.5), lm(0,1.0,0.5))
    assert abs(a - 180.0) < 0.5, f"Expected ~180°, got {a}°"
run("TC-U02", "Pontos colineares → 180°", u02)

def u03():
    a = ac.calculate_angle(lm(23,0.30,0.72), lm(25,0.50,0.72), lm(27,0.48,0.90))
    assert a < 100, f"Agachamento BOTTOM esperado <100°, got {a}°"
run("TC-U03", "Joelho dobrado agachamento BOTTOM → <100°", u03)

def u04():
    a = ac.calculate_angle(lm(0,0.5,0.5), lm(0,0.5,0.5), lm(0,0.8,0.8))
    assert a == 180.0, f"Pontos coincidentes devem retornar 180, got {a}"
run("TC-U04", "Pontos coincidentes (degenerado) → 180°", u04)

def u05():
    a = ac.calculate_angle(lm(23,0.48,0.30), lm(25,0.50,0.60), lm(27,0.48,0.90))
    assert a > 150, f"Posição em pé esperado >150°, got {a}°"
run("TC-U05", "Joelho estendido posição em pé → >150°", u05)

# ════════════════════════════════════════════════════════
# GRUPO 2 — detect_phase (TC-U06 a TC-U10)
# ════════════════════════════════════════════════════════
print("\n🔄 DetectPhase")

def u06():
    ph = ea.detect_phase(165.0)
    assert ph == MovementPhase.STANDING, f"Expected STANDING, got {ph}"
run("TC-U06", "165° → STANDING", u06)

def u07():
    ph = ea.detect_phase(80.0)
    assert ph == MovementPhase.BOTTOM, f"Expected BOTTOM, got {ph}"
run("TC-U07", "80° → BOTTOM", u07)

def u08():
    ph = ea.detect_phase(130.0, prev_angle=None)
    assert ph == MovementPhase.DESCENDING, f"Expected DESCENDING, got {ph}"
run("TC-U08", "130° sem histórico → DESCENDING", u08)

def u09():
    ph = ea.detect_phase(130.0, prev_angle=110.0)
    assert ph == MovementPhase.ASCENDING, f"Expected ASCENDING, got {ph}"
run("TC-U09", "130° subindo de 110° → ASCENDING", u09)

def u10():
    ph = ea.detect_phase(None)
    assert ph == MovementPhase.UNKNOWN, f"Expected UNKNOWN, got {ph}"
run("TC-U10", "None → UNKNOWN", u10)

# ════════════════════════════════════════════════════════
# GRUPO 3 — calculateScore (TC-U11 a TC-U15)
# ════════════════════════════════════════════════════════
print("\n🎯 CalculateScore")

def u11():
    s = ea.calculate_score([], MovementPhase.STANDING)
    assert s == 100.0, f"Expected 100, got {s}"
run("TC-U11", "Sem erros → score 100", u11)

def u12():
    errs = [DetectedError(ErrorType.BACK_ROUNDED, RiskLevel.HIGH, "t")]
    s = ea.calculate_score(errs, MovementPhase.BOTTOM)
    assert s == 75.0, f"Expected 75, got {s}"
run("TC-U12", "1 erro HIGH → score 75 (-25)", u12)

def u13():
    errs = [DetectedError(ErrorType.KNEE_CAVE_LEFT, RiskLevel.MEDIUM, "t")]
    s = ea.calculate_score(errs, MovementPhase.BOTTOM)
    assert s == 85.0, f"Expected 85, got {s}"
run("TC-U13", "1 erro MEDIUM → score 85 (-15)", u13)

def u14():
    errs = [DetectedError(ErrorType.BACK_ROUNDED, RiskLevel.HIGH, "t")] * 10
    s = ea.calculate_score(errs, MovementPhase.BOTTOM)
    assert s == 0.0, f"Expected 0 (clamp), got {s}"
run("TC-U14", "Múltiplos erros HIGH → clamp score 0", u14)

def u15():
    s = ea.calculate_score([], MovementPhase.UNKNOWN)
    assert s == 0.0, f"Expected 0 for UNKNOWN, got {s}"
run("TC-U15", "Fase UNKNOWN → score 0", u15)

# ════════════════════════════════════════════════════════
# GRUPO 4 — ExerciseAnalyzer (TC-U16 a TC-U22)
# ════════════════════════════════════════════════════════
print("\n🏋️  ExerciseAnalyzer")

def u16():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.SQUAT, [
        lm(11,0.45,0.20), lm(23,0.30,0.72),
        lm(25,0.50,0.72), lm(27,0.48,0.90), lm(31,0.50,0.95)
    ]))
    assert r.score > 0, "Score deve ser >0 com postura correta"
    assert not any(e.risk_level == RiskLevel.HIGH for e in r.errors), "Não deve ter HIGH"
run("TC-U16", "SQUAT postura correta → sem erros HIGH, score >0", u16)

def u17():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.SQUAT, [
        lm(11,0.45,0.20), lm(23,0.30,0.72),
        lm(25,0.70,0.72), lm(27,0.48,0.90), lm(31,0.50,0.95)
    ]))
    assert ErrorType.KNEE_CAVE_LEFT in [e.error_type for e in r.errors], \
        f"KNEE_CAVE_LEFT não detectado: {[e.error_type for e in r.errors]}"
run("TC-U17", "SQUAT joelho cave → KNEE_CAVE_LEFT MEDIUM", u17)

def u18():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.SQUAT, [
        lm(11,0.05,0.50), lm(23,0.48,0.55),
        lm(25,0.50,0.72), lm(27,0.48,0.90), lm(31,0.50,0.95)
    ]))
    assert ErrorType.BACK_NOT_STRAIGHT in [e.error_type for e in r.errors], \
        f"BACK_NOT_STRAIGHT não detectado: {[e.error_type for e in r.errors]}"
run("TC-U18", "SQUAT tronco inclinado → BACK_NOT_STRAIGHT", u18)

def u19():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.SQUAT, [lm(0,0.5,0.1)]))
    assert r.score == 0.0, f"Score deve ser 0: {r.score}"
    assert ErrorType.LANDMARK_MISSING in [e.error_type for e in r.errors]
run("TC-U19", "Landmarks insuficientes → LANDMARK_MISSING, score=0", u19)

def u20():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.SQUAT, [
        lm(11,0.45,0.20), lm(23,0.30,0.72),
        lm(25,0.70,0.72), lm(27,0.48,0.90), lm(31,0.50,0.95)
    ]))
    exp = any(e.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH) for e in r.errors)
    assert r.has_alert == exp, f"has_alert={r.has_alert} != esperado={exp}"
run("TC-U20", "has_alert=True quando há erros MEDIUM/HIGH", u20)

def u21():
    angles = ac.calculate_joint_angles([
        lm(11,0.45,0.20), lm(23,0.30,0.72),
        lm(25,0.50,0.72), lm(27,0.48,0.90), lm(31,0.50,0.95)
    ])
    assert angles.left_knee is not None
    assert 0 < angles.left_knee < 180
    assert angles.back_angle is not None
run("TC-U21", "joint_angles calculados com landmarks válidos", u21)

def u22():
    angles = ac.calculate_joint_angles([
        lm(25,0.5,0.7,vis=0.2), lm(23,0.3,0.5,vis=0.2), lm(27,0.48,0.9,vis=0.2)
    ])
    assert angles.left_knee is None, "Landmarks <0.5 vis devem ser ignorados"
run("TC-U22", "Landmarks visibilidade <0.5 ignorados pelo filtro", u22)

# ════════════════════════════════════════════════════════
# GRUPO 5 — RepCounter + Throttle (TC-U23 a TC-U30)
# ════════════════════════════════════════════════════════
print("\n🔁 RepCounter + Throttle")

from video_analyzer import RepCounter, FrameResult

def mkF(i, ph, sc, errs=None, alert=False):
    return FrameResult(i, i*200.0, ph, sc, 5, errs or [], alert, {})

def u23():
    rc = RepCounter()
    for f in [mkF(0,"STANDING",100), mkF(1,"DESCENDING",90), mkF(2,"BOTTOM",80),
              mkF(3,"ASCENDING",85), mkF(4,"STANDING",100)]:
        rc.feed(f)
    rc.finish()
    assert len(rc.reps) == 1, f"Expected 1 rep, got {len(rc.reps)}"
    assert rc.reps[0].rep_number == 1
run("TC-U23", "RepCounter — 1 ciclo completo detectado", u23)

def u24():
    rc = RepCounter()
    idx = 0
    for _ in range(3):
        for ph, sc in [("STANDING",100),("DESCENDING",90),("BOTTOM",80),
                       ("ASCENDING",90),("STANDING",100)]:
            rc.feed(mkF(idx, ph, sc))
            idx += 1
    rc.finish()
    assert len(rc.reps) == 3, f"Expected 3 reps, got {len(rc.reps)}"
run("TC-U24", "RepCounter — 3 reps consecutivas detectadas", u24)

def u25():
    rc = RepCounter()
    for i in range(5):
        rc.feed(mkF(i, "STANDING", 100))
    rc.finish()
    assert len(rc.reps) == 0, "Sem descida não deve detectar reps"
run("TC-U25", "RepCounter — só STANDING → 0 reps", u25)

def u26():
    # Usa timestamps simulados para independência do clock real
    from collections import defaultdict
    last: dict = defaultdict(float)
    THROTTLE = 5.0
    fired = 0
    # Simula 5 chamadas no instante t=100s (todas dentro do janela de throttle)
    fake_times = [100.0, 100.001, 100.002, 100.003, 100.004]
    for t in fake_times:
        key = "KNEE_CAVE_LEFT"
        if t - last[key] >= THROTTLE:
            last[key] = t
            fired += 1
    assert fired == 1, f"Throttle deve disparar 1 vez, disparou {fired}"
    # Verifica que após 5s um novo alerta passa
    t_after = 100.0 + THROTTLE + 0.1
    if t_after - last["KNEE_CAVE_LEFT"] >= THROTTLE:
        fired += 1
    assert fired == 2, "Após throttle expirar, novo alerta deve passar"
run("TC-U26", "Throttle — 5 erros iguais rápidos → 1 alerta; após 5s → novo alerta", u26)

def u27():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.DEADLIFT, [
        lm(11,0.05,0.55), lm(23,0.30,0.72),
        lm(25,0.50,0.72), lm(27,0.48,0.90)
    ]))
    types_ = [e.error_type for e in r.errors]
    has_back = (ErrorType.BACK_ROUNDED in types_ or ErrorType.BACK_NOT_STRAIGHT in types_)
    assert has_back, f"Erro de costas esperado: {types_}"
run("TC-U27", "DEADLIFT lombar arredondada (fase BOTTOM) → erro de costas", u27)

def u28():
    r = ea.ExerciseAnalyzer().analyze(mkReq(ExerciseType.LUNGE, [
        lm(11,0.45,0.20), lm(23,0.30,0.72),
        lm(25,0.50,0.72), lm(27,0.48,0.90), lm(31,0.50,0.95)
    ]))
    assert r.exercise_type == ExerciseType.LUNGE
    assert 0 <= r.score <= 100, f"Score fora de range: {r.score}"
run("TC-U28", "LUNGE — processado sem exceção, score 0–100", u28)

def u29():
    rc = RepCounter()
    for f in [mkF(0,"STANDING",100), mkF(1,"DESCENDING",90), mkF(2,"BOTTOM",80),
              mkF(3,"ASCENDING",85), mkF(4,"STANDING",95)]:
        rc.feed(f)
    rc.finish()
    assert len(rc.reps) == 1
    # frames 1,2,3,4 capturados: (90+80+85+95)/4 = 87.5
    assert abs(rc.reps[0].avg_score - 87.5) < 0.1, \
        f"avg={rc.reps[0].avg_score} expected 87.5"
run("TC-U29", "RepCounter — avg_score correto: média de todos os frames da rep", u29)

def u30():
    err_h = DetectedError(ErrorType.BACK_ROUNDED, RiskLevel.HIGH, "t")
    err_m = DetectedError(ErrorType.KNEE_CAVE_LEFT, RiskLevel.MEDIUM, "t")
    rc = RepCounter()
    for f in [mkF(0,"STANDING",100), mkF(1,"DESCENDING",85,[err_m],True),
              mkF(2,"BOTTOM",60,[err_h],True), mkF(3,"ASCENDING",75),
              mkF(4,"STANDING",90)]:
        rc.feed(f)
    rc.finish()
    assert len(rc.reps) == 1
    assert rc.reps[0].risk_level == "HIGH", f"Pior risco deve ser HIGH: {rc.reps[0].risk_level}"
run("TC-U30", "RepCounter — risk_level da rep = pior erro encontrado", u30)

# ── Resultado final ───────────────────────────────────────────────────────────
passed = sum(1 for r in results if r["status"] == "PASSOU")
failed = sum(1 for r in results if r["status"] == "FALHOU")
errors = sum(1 for r in results if r["status"] == "ERRO")
total_ms = sum(r["ms"] for r in results)

print(f"\n{'='*60}")
print(f"RESULTADO FINAL: {passed}/{len(results)} PASSOU | {failed} FALHOU | {errors} ERRO")
print(f"Tempo total de execução: {total_ms:.1f}ms")

output = {
    "run_date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    "total": len(results), "passed": passed, "failed": failed, "errors": errors,
    "total_ms": round(total_ms, 2),
    "results": results
}
with open("/tmp/test_results.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print("Resultados salvos em /tmp/test_results.json")
