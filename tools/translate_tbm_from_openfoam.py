#!/usr/bin/env python3
"""
Translate a stock STAR-CCM+ TBM file to match an OpenFOAM ECM cell definition.

Usage:
    python3 tools/translate_tbm_from_openfoam.py \
        --in  out/hp18650Spiral-DIST.tbm \
        --manifest bdm/examples/cell_2170_nca_v1/manifest.json \
        --params python/params.csv \
        --out out/hp2170NCA-ECM.tbm

Sources used:
  - manifest.json : cell geometry, capacity, ECM parameters (R0/R1/R2, tau1/tau2, OCV)
  - params.csv    : actual RCR characterisation table (Q_Ah, T_degC, E_OCV_dch_V, R0_Ohm,
                    R_Ohm_1, R_Ohm_2, C_F_1, C_F_2, dUdT …) — when supplied via --params,
                    supersedes manifest ECM defaults and writes full multi-temperature Sets.

Field dependency knowledge (from TBM geometry characterisation tests, 2026-08-14/31):
  - JR target OD         : m_dJellyrollThickness_mm / m_dJellyrollThickness
  - JR axial (electrode) : -{-,+}Electrode {m_dCoatingWidth, m_dWidth, Collector m_dWidth_mm}
                           + SeparatorList1_Separator m_dWidth_mm
  - Can OD               : m_dRepCanXDim / m_dRepCanYDim  (Level-C REPORT field — IS consumed)
  - Can height           : Package m_dextHeight
  - Cell capacity        : m_bSpecifyCapacity=1 + m_dAhCell (in RCRTable 3D section)
  - RCR data             : Set[N]_RCR_V_{SOC,V,Ro,Rp,Rp1,tau,tau1}_k (1-indexed, plain Ω)
  - Temperature sets     : Set[N]_m_dT in K; m_nRCRParameterSets = number of Sets
  - Entropy coefficient  : RCR_dUdT_dUdTSOC_k / RCR_dUdT_dUdT_k (1-indexed)
  - Thermal conductivity : m_dCondX/Y/Z_W_permK  AND  m_dkx/y/z_WpermK (both fields)
  - Current-density caps : Set[N]_m_dMaxChargeCurrent_Aperm2 = 1000 (prevents IDACalcIC crash)
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path


# ── Nominal cell capacity (Qnom used by ecm_step.py for SOC = 1 − Q/Qnom) ─────
# params.csv Q_Ah axis runs to 9.0 but ecm_step.py clamps to [0, Qnom].
# Only the first 7 breakpoints (Q = 0..5.4 Ah) are physically reached.
QNOM_AH = 5.0


# ── OpenFOAM thermal property constants (from thermophysicalProperties files) ──
# jellyRoll  (tabulatedAnIso, cylindrical coords: r / theta / z)
JR_RHO_KG_M3    = 2660.7
JR_CP_J_KGK     = [(250, 835.55), (500, 1585.55)]   # tabulated; use ~985 at 300 K
JR_KAPPA_R_W_MK = 1.4    # radial / tangential
JR_KAPPA_A_W_MK = 29.0   # axial (through current collectors)

# shell (can body — steel)
SHELL_RHO_KG_M3   = 8000.0
SHELL_CP_J_KGK    = 500.0
SHELL_KAPPA_W_MK  = 16.0

# cap
CAP_RHO_KG_M3     = 1447.2
CAP_CP_J_KGK      = 500.0
CAP_KAPPA_R_W_MK  = 0.01
CAP_KAPPA_A_W_MK  = 0.1


# ── Data loading ────────────────────────────────────────────────────────────────

def load_manifest(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_params_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            rows.append({k: float(v) for k, v in row.items()})
    return rows


# ── ECM parameter extraction ────────────────────────────────────────────────────

def ecm_from_params(rows: list[dict], capacity_ah: float) -> dict:
    """
    Build ECM dict from params.csv.

    Uses QNOM_AH (5.0 Ah) to define SOC = 1 − Q_Ah / QNOM_AH.
    Only breakpoints with Q_Ah ≤ QNOM_AH * 1.1 are included, giving
    7 SOC points (−0.08 … 1.0) matching the validated TBM format.

    Returns a dict with:
      sets       : list of per-temperature dicts (T_K, SOC, V, Ro, Rp, Rp1, tau, tau1)
      dudt_soc   : SOC axis for entropy coefficient (from 25 °C slice)
      dudt_val   : dUdT values (V/K)
      capacity_ah: nominal capacity (QNOM_AH)
      … plus backward-compat scalar fields at 25 °C mid-SOC
    """
    # Filter to the physically meaningful range (Q ≤ 5.4 Ah = SOC ≥ −0.08)
    valid = [r for r in rows if r['Q_Ah'] <= QNOM_AH * 1.1]

    temps = sorted({r['T_degC'] for r in valid})

    sets = []
    for t in temps:
        t_rows = sorted([r for r in valid if r['T_degC'] == t], key=lambda r: r['Q_Ah'])
        # Convert to (SOC, row) pairs sorted SOC ascending (low SOC = discharged first)
        pairs = sorted(
            [(1.0 - r['Q_Ah'] / QNOM_AH, r) for r in t_rows],
            key=lambda x: x[0]
        )
        sets.append({
            'T_K':  round(t + 273.15, 2),
            'SOC':  [round(s, 6)                            for s, _ in pairs],
            'V':    [round(r['E_OCV_dch_V'], 6)             for _, r in pairs],
            'Ro':   [round(r['R0_Ohm'], 6)                  for _, r in pairs],
            'Rp':   [round(r['R_Ohm_1'], 6)                 for _, r in pairs],
            'Rp1':  [round(r['R_Ohm_2'], 6)                 for _, r in pairs],
            'tau':  [round(r['R_Ohm_1'] * r['C_F_1'], 4)   for _, r in pairs],
            'tau1': [round(r['R_Ohm_2'] * r['C_F_2'], 4)   for _, r in pairs],
        })

    # dUdT from the 25 °C slice (BDS uses one global dUdT curve)
    t25_rows = sorted([r for r in valid if r['T_degC'] == 25.0], key=lambda r: r['Q_Ah'])
    pairs_25 = sorted(
        [(1.0 - r['Q_Ah'] / QNOM_AH, r) for r in t25_rows],
        key=lambda x: x[0]
    )
    dudt_soc = [round(s, 6)          for s, _ in pairs_25]
    dudt_val = [round(r['dUdT'], 8)  for _, r in pairs_25]

    # Backward-compat scalars at 25 °C mid-SOC
    mid_r = pairs_25[len(pairs_25) // 2][1]
    tau1_ref = round(mid_r['R_Ohm_1'] * mid_r['C_F_1'], 4)
    tau2_ref = round(mid_r['R_Ohm_2'] * mid_r['C_F_2'], 4)

    return {
        'capacity_ah': QNOM_AH,
        'sets':        sets,
        'dudt_soc':    dudt_soc,
        'dudt_val':    dudt_val,
        # scalar back-compat
        'ocv_min_v':  min(r['E_OCV_dch_V'] for _, r in pairs_25),
        'ocv_max_v':  max(r['E_OCV_dch_V'] for _, r in pairs_25),
        'r0_ohm':     round(mid_r['R0_Ohm'], 6),
        'r1_ohm':     round(mid_r['R_Ohm_1'], 6),
        'r2_ohm':     round(mid_r['R_Ohm_2'], 6),
        'tau1_s':     tau1_ref,
        'tau2_s':     tau2_ref,
        'ocv_table':  [(s, r['E_OCV_dch_V'])                    for s, r in pairs_25],
        'r0_table':   [(s, r['R0_Ohm'])                         for s, r in pairs_25],
        'r1_table':   [(s, r['R_Ohm_1'])                        for s, r in pairs_25],
        'r2_table':   [(s, r['R_Ohm_2'])                        for s, r in pairs_25],
        'tau1_table': [(s, round(r['R_Ohm_1']*r['C_F_1'], 4))  for s, r in pairs_25],
        'tau2_table': [(s, round(r['R_Ohm_2']*r['C_F_2'], 4))  for s, r in pairs_25],
        'source': 'params.csv',
    }


def extract_ecm(manifest: dict) -> dict:
    """Pull ECM parameters from manifest (fallback when no params.csv supplied)."""
    te = manifest.get("thermal_electrical", {})
    cap = te.get("capacity_ah", 5.0)
    ocv_min = te.get("ocv_min_v", 3.00)
    ocv_max = te.get("ocv_max_v", 4.20)
    r0  = te.get("r0_ohm",  0.012)
    r1  = te.get("r1_ohm",  0.0040)
    r2  = te.get("r2_ohm",  0.0020)
    t1  = te.get("tau1_s",  8.0)
    t2  = te.get("tau2_s",  40.0)
    # Build a single 25 °C Set with 7 uniform SOC points
    soc_pts = [-0.08, 0.10, 0.28, 0.46, 0.64, 0.82, 1.00]
    ocv_vals = [round(ocv_min + (ocv_max - ocv_min) * (s + 0.08) / 1.08, 4) for s in soc_pts]
    return {
        'capacity_ah': cap,
        'sets': [{
            'T_K':  298.15,
            'SOC':  soc_pts,
            'V':    ocv_vals,
            'Ro':   [r0]  * 7,
            'Rp':   [r1]  * 7,
            'Rp1':  [r2]  * 7,
            'tau':  [t1]  * 7,
            'tau1': [t2]  * 7,
        }],
        'dudt_soc': soc_pts,
        'dudt_val': [0.0] * 7,
        'ocv_min_v': ocv_min,
        'ocv_max_v': ocv_max,
        'r0_ohm': r0, 'r1_ohm': r1, 'r2_ohm': r2,
        'tau1_s': t1, 'tau2_s': t2,
        'ocv_table': None, 'r0_table': None, 'r1_table': None,
        'r2_table': None, 'tau1_table': None, 'tau2_table': None,
        'source': 'manifest',
    }


# ── Geometry ────────────────────────────────────────────────────────────────────

def extract_geom(manifest: dict) -> dict:
    g = manifest.get("geometry", {}).get("procedural", {}).get("dimensions_m", {})
    mm = lambda key: g.get(key, 0.0) * 1000.0
    jr_od_mm    = mm("jelly_roll_diameter_m")
    jr_axial_mm = mm("jelly_roll_height_m")
    can_od_mm   = mm("outer_diameter_m")
    can_h_mm    = mm("total_height_m")
    return dict(
        jr_od_mm    = jr_od_mm,
        jr_axial_mm = jr_axial_mm,
        can_od_mm   = can_od_mm,
        can_h_mm    = can_h_mm,
        neg_width_mm = jr_axial_mm,
        pos_width_mm = jr_axial_mm - 1.0,
        sep_width_mm = jr_axial_mm + 2.0,
    )


# ── TBM text manipulation helpers ───────────────────────────────────────────────

def tbm_sub(content: str, field: str, new_val, *, only_first=False) -> str:
    """Replace  `field\\t=\\told_value\\t` in TBM content."""
    pattern = re.compile(
        r'(?m)^(\t*)(' + re.escape(field) + r')(\t+=\t+)([^\t\r\n]+?)(\t.*)$'
    )
    replacement = rf'\g<1>\g<2>\g<3>{new_val}\g<5>'
    if only_first:
        return pattern.sub(replacement, content, count=1)
    return pattern.sub(replacement, content)


def _set_text(n: int, data: dict) -> str:
    """Build the complete Set[N] block for insertion into RCRTable 3D."""
    p = f'Set[{n}]'
    M = len(data['SOC'])
    L = []
    L.append(f'\t{p}_CRCRCurves classversion\t=\t2\t!\t')
    L.append(f'\t{p}_CellThickness_Interpolation\t=\t0\t!\t')
    L.append(f'\t{p}_RCR_V_DataPoints\t=\t{M}\t!\t')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_Ro_{j}\t=\t{data["Ro"][k]}\t!\t\t!\t{p}_RCR_V_Ro_{j}')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_Rp1_{j}\t=\t{data["Rp1"][k]}\t!\t\t!\t{p}_RCR_V_Rp1_{j}')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_Rp_{j}\t=\t{data["Rp"][k]}\t!\t\t!\t{p}_RCR_V_Rp_{j}')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_SOC_{j}\t=\t{data["SOC"][k]}\t!\t\t!\t{p}_RCR_V_SOC_{j}')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_V_{j}\t=\t{data["V"][k]}\t!\t\t!\t{p}_RCR_V_V_{j}')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_tau1_{j}\t=\t{data["tau1"][k]}\t!\t\t!\t{p}_RCR_V_tau1_{j}')
    for k in range(M):
        j = k + 1
        L.append(f'\t{p}_RCR_V_tau_{j}\t=\t{data["tau"][k]}\t!\t\t!\t{p}_RCR_V_tau_{j}')
    L.append(f'\t{p}_Ro_Interpolation\t=\t2\t!\t')
    L.append(f'\t{p}_Rp_0_Interpolation\t=\t2\t!\t')
    L.append(f'\t{p}_Rp_1_Interpolation\t=\t2\t!\t')
    L.append(f'\t{p}_Type\t=\t0\t!\t')
    L.append(f'\t{p}_V_Interpolation\t=\t1\t!\t')
    L.append(f'\t{p}_YoungsModulus_Interpolation\t=\t0\t!\t')
    L.append(f'\t{p}_m_dMaxChargeCurrent_Aperm2\t=\t1000\t!\t')
    L.append(f'\t{p}_m_dMaxDischargeCurrent_Aperm2\t=\t1000\t!\t')
    L.append(f'\t{p}_m_dT\t=\t{data["T_K"]}\t!\t\t!\tTemperature, K')
    L.append(f'\t{p}_tau_0_Interpolation\t=\t2\t!\t')
    L.append(f'\t{p}_tau_1_Interpolation\t=\t2\t!\t')
    return '\n'.join(L)


def _dudt_text(soc_vals: list, dudt_vals: list) -> str:
    """Build the RCR_dUdT block for insertion into RCRTable 3D."""
    N = len(soc_vals)
    L = []
    L.append(f'\tRCR_dUdT_DataPoints\t=\t{N}\t!\t')
    for k in range(N):
        L.append(f'\tRCR_dUdT_dUdTSOC_{k+1}\t=\t{soc_vals[k]}\t!\t\t!\t')
    for k in range(N):
        L.append(f'\tRCR_dUdT_dUdT_{k+1}\t=\t{dudt_vals[k]}\t!\t\t!\t')
    L.append(f'\tRCR_dUdT_nSize\t=\t{N}\t!\t')
    return '\n'.join(L)


# ── Apply functions ─────────────────────────────────────────────────────────────

def apply_geometry(content: str, geom: dict) -> str:
    g = geom
    content = tbm_sub(content, 'm_dJellyrollThickness_mm', g['jr_od_mm'])
    content = tbm_sub(content, 'm_dJellyrollThickness',    g['jr_od_mm'])
    content = tbm_sub(content, 'm_dRepCanXDim', g['can_od_mm'])
    content = tbm_sub(content, 'm_dRepCanYDim', g['can_od_mm'])
    content = tbm_sub(content, 'm_dRepCanZDim', g['can_h_mm'])
    content = tbm_sub(content, 'Package m_dextHeight',   g['can_h_mm'])
    content = tbm_sub(content, 'Package m_dextDiameter', g['can_od_mm'])
    content = tbm_sub(content, 'DataSheet m_dDSDiameter', g['can_od_mm'])
    content = tbm_sub(content, 'DataSheet m_dDiameter',   g['can_od_mm'])
    content = tbm_sub(content, 'DataSheet m_dThickness',  g['can_od_mm'])
    content = tbm_sub(content, '+Electrode Collector m_dWidth_mm', g['pos_width_mm'])
    content = tbm_sub(content, '+Electrode m_dCoatingWidth',       g['pos_width_mm'])
    content = tbm_sub(content, '+Electrode m_dWidth',              g['pos_width_mm'])
    content = tbm_sub(content, '-Electrode Collector m_dWidth_mm', g['neg_width_mm'])
    content = tbm_sub(content, '-Electrode m_dCoatingWidth',       g['neg_width_mm'])
    content = tbm_sub(content, '-Electrode m_dWidth',              g['neg_width_mm'])
    content = tbm_sub(content, 'SeparatorList1_Separator m_dWidth_mm', g['sep_width_mm'])
    return content


def apply_rcrtable_3d(content: str, ecm: dict, kappa_r: float, kappa_z: float) -> str:
    """
    Rewrite the RCRTable 3D SIMMOD block with full multi-temperature Set data.

    Replaces:
      - All Set[N]_* lines  →  new per-temperature Set blocks
      - RCR_dUdT_*          →  entropy coefficient data from params.csv
      - m_nRCRParameterSets →  number of temperature Sets
      - m_bSpecifyCapacity  →  1
      - m_dAhCell           →  QNOM_AH (5.0 Ah)
      - m_dCondX/Y/Z + m_dkx/y/z  →  kappa from manifest
    """
    sets = ecm['sets']
    n_sets = len(sets)
    cap = ecm['capacity_ah']

    # ── Find block boundaries ────────────────────────────────────────────────
    rcrt_pos = content.find('RCRTable 3D')
    if rcrt_pos == -1:
        print("WARNING: RCRTable 3D block not found — skipping")
        return content

    simmod_open  = content.rfind('<SIMMOD>', 0, rcrt_pos)
    simmod_close = content.find('</SIMMOD>', rcrt_pos)
    if simmod_open == -1 or simmod_close == -1:
        print("WARNING: RCRTable 3D SIMMOD boundaries not found — skipping")
        return content

    # Split into three parts: before, block, after
    pre   = content[:simmod_open]
    block = content[simmod_open: simmod_close + len('</SIMMOD>')]
    post  = content[simmod_close + len('</SIMMOD>'):]

    # ── Rebuild the block line by line ───────────────────────────────────────
    lines = block.split('\n')
    new_lines = []
    sets_and_dudt_inserted = False

    for ln in lines:
        stripped = ln.strip()

        # Drop all old Set[N]_* and RCR_dUdT_* lines (we insert fresh ones)
        if re.match(r'Set\[\d+\]_', stripped) or stripped.startswith('RCR_dUdT_'):
            continue

        # After RCR_Veq_nSize, inject dUdT block + all Set blocks
        if 'RCR_Veq_nSize' in ln and not sets_and_dudt_inserted:
            new_lines.append(ln)
            new_lines.append(_dudt_text(ecm['dudt_soc'], ecm['dudt_val']))
            for i, s in enumerate(sets):
                new_lines.append(_set_text(i, s))
            sets_and_dudt_inserted = True
            continue

        # Update scalar fields within this block
        if 'm_nRCRParameterSets' in ln:
            new_lines.append(
                f'\tm_nRCRParameterSets\t=\t{n_sets}\t!\t\t!\tNo. RCR Data Sets')
            continue
        if re.search(r'\bm_bSpecifyCapacity\b', ln) and '!' in ln:
            new_lines.append(f'\tm_bSpecifyCapacity\t=\t1\t!\t')
            continue
        if re.search(r'\bm_dAhCell\b', ln) and 'Cell Capacity. Ah' in ln:
            new_lines.append(
                f'\tm_dAhCell\t=\t{cap}\t!\t\t!\tCell Capacity. Ah')
            continue
        if 'm_dCondX_W_permK' in ln:
            new_lines.append(
                f'\tm_dCondX_W_permK\t=\t{kappa_r}\t!\t\t!\tConductivity X dir, W/m.K')
            continue
        if 'm_dCondY_W_permK' in ln:
            new_lines.append(
                f'\tm_dCondY_W_permK\t=\t{kappa_r}\t!\t\t!\tConductivity Y dir, W/m.K')
            continue
        if 'm_dCondZ_W_permK' in ln:
            new_lines.append(
                f'\tm_dCondZ_W_permK\t=\t{kappa_z}\t!\t\t!\tConductivity Z dir, W/m.K')
            continue
        if 'm_dkx_WpermK' in ln:
            new_lines.append(
                f'\tm_dkx_WpermK\t=\t{kappa_r}\t!\t\t!\tThermal conductivity in x, W/m-K')
            continue
        if 'm_dky_WpermK' in ln:
            new_lines.append(
                f'\tm_dky_WpermK\t=\t{kappa_r}\t!\t\t!\tThermal conductivity in y, W/m-K')
            continue
        if 'm_dkz_WpermK' in ln:
            new_lines.append(
                f'\tm_dkz_WpermK\t=\t{kappa_z}\t!\t\t!\tThermal conductivity in z, W/m-K')
            continue

        new_lines.append(ln)

    return pre + '\n'.join(new_lines) + post


def tbm_get(content: str, field: str) -> float | None:
    """Read the first numeric value of a field from TBM content."""
    m = re.search(
        r'(?m)^\t*' + re.escape(field) + r'\t+=\t+([^\t\r\n]+?)\t', content)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


# ── Known physical constants for analytical mixing rules ────────────────────
# Textbook / literature values used when the BUILDER has placeholder defaults.
_LIT = {
    # [W/(m·K), g/cm³, J/(g·K)]
    'al':  (160.0, 2.70,  0.900),   # pure Al foil
    'cu':  (385.0, 8.90,  0.385),   # pure Cu foil
    'nca': (  1.0, None,  0.850),   # NCA active material coating
    'gph': (  1.0, None,  0.750),   # graphite active material coating
    'sep': (  0.40, None, 2.00),    # PE separator + LiPF6 electrolyte (pore-filled)
}
_RHO_ELYTE_GCM3 = 1.20   # electrolyte density (LiPF6 in EC/DMC)


def apply_jellyroll_thermal(content: str) -> tuple[str, dict]:
    """
    Apply analytical mixing rules for jellyroll BUILDER material properties.

    Sets individual layer thermal properties to physically consistent values:
      Al foil        κ = 160.0 W/(m·K)  Cp = 0.900 J/(g·K)  [textbook]
      Cu foil        κ = 385.0 W/(m·K)  Cp = 0.385 J/(g·K)  [textbook]
      NCA coating    κ =   1.0 W/(m·K)  Cp = 0.850 J/(g·K)  [literature]
      Graphite coat  κ =   1.0 W/(m·K)  Cp = 0.750 J/(g·K)  [literature]
      Separator      κ =  0.40 W/(m·K)  Cp = 2.000 J/(g·K)  [literature]

    Note: effective kappa is already overridden in the SIMMOD block via m_dCondX/Y/Z.
    This updates BUILDER properties for consistent density, Cp, and kappa.

    Returns (patched_content, info_dict) where info_dict has predicted vs target
    volumetric heat capacity for verification.
    """
    k_al,  rho_al_lit,  Cp_al  = _LIT['al']
    k_cu,  rho_cu_lit,  Cp_cu  = _LIT['cu']
    k_nca, _,           Cp_nca = _LIT['nca']
    k_gph, _,           Cp_gph = _LIT['gph']
    k_sep, _,           Cp_sep = _LIT['sep']

    # ── Foil: Al (positive collector) ────────────────────────────────────────
    content = tbm_sub(content, '+Electrode Collector m_dThermalConductivity', k_al)
    content = tbm_sub(content, '+Electrode Collector m_dHeatCapacity',        Cp_al)
    content = tbm_sub(content, '+Electrode Collector m_dDensity_gpercm3',     rho_al_lit)

    # ── Foil: Cu (negative collector) ────────────────────────────────────────
    content = tbm_sub(content, '-Electrode Collector m_dThermalConductivity', k_cu)
    content = tbm_sub(content, '-Electrode Collector m_dHeatCapacity',        Cp_cu)
    content = tbm_sub(content, '-Electrode Collector m_dDensity_gpercm3',     rho_cu_lit)

    # ── Electrode active material: NCA (positive) ────────────────────────────
    content = tbm_sub(content,
        '+Electrode 1_Formulation FormComp1 ActiveMaterial m_dThermalConductivity', k_nca)
    content = tbm_sub(content,
        '+Electrode 1_Formulation FormComp1 ActiveMaterial m_dHeatCapacity', Cp_nca)
    content = tbm_sub(content,
        '+Electrode 1_Formulation FormComp1 ActiveMaterial m_bHeatCapConst', 1)

    # ── Electrode active material: graphite (negative) ───────────────────────
    content = tbm_sub(content,
        '-Electrode 1_Formulation FormComp1 ActiveMaterial m_dThermalConductivity', k_gph)
    content = tbm_sub(content,
        '-Electrode 1_Formulation FormComp1 ActiveMaterial m_dHeatCapacity', Cp_gph)
    content = tbm_sub(content,
        '-Electrode 1_Formulation FormComp1 ActiveMaterial m_bHeatCapConst', 1)

    # ── Separator (PE/PP + electrolyte-filled pores) ─────────────────────────
    content = tbm_sub(content, 'SeparatorList1_Separator m_dThermalConductivity', k_sep)
    content = tbm_sub(content, 'SeparatorList1_Separator m_dHeatCapacity',        Cp_sep)

    # ── Mixing-rule prediction (for information / verification printout) ──────
    # Read layer thicknesses from (now-updated) content.
    # CoatThickness_mm is per-side; separator and collector thicknesses are in µm.
    t_pos_um  = (tbm_get(content, '+Electrode 1_CoatThickness_mm') or 0.0374556) * 1000.0
    t_al_um   =  tbm_get(content, '+Electrode Collector m_dAvgThickness_um') or 30.0
    t_neg_um  = (tbm_get(content, '-Electrode 1_CoatThickness_mm') or 0.0399605) * 1000.0
    t_cu_um   =  tbm_get(content, '-Electrode Collector m_dAvgThickness_um') or 18.0
    t_sep_um  =  tbm_get(content, 'SeparatorList1_Separator m_dAvgThickness_um') or 25.0

    # Coating bulk densities (g/cm³ → kg/m³)
    rho_pos = (tbm_get(content, '+Electrode 1_CoatDensity_gpercm3') or 2.70)  * 1000.0
    rho_al  = rho_al_lit * 1000.0
    rho_neg = (tbm_get(content, '-Electrode 1_CoatDensity_gpercm3') or 1.52)  * 1000.0
    rho_cu  = rho_cu_lit * 1000.0

    # Separator effective density accounting for porosity and electrolyte fill
    rho_sep_solid = (tbm_get(content, 'SeparatorList1_Separator m_dSolidDensity_gpercm3') or 0.95)
    porosity_pct  =  tbm_get(content, 'SeparatorList1_Separator m_dPorosity') or 40.0
    phi = porosity_pct / 100.0
    rho_sep = ((1.0 - phi) * rho_sep_solid + phi * _RHO_ELYTE_GCM3) * 1000.0  # kg/m³

    # Unit-cell layer thicknesses [µm]: each coating appears on both sides of the foil
    t = {
        'pos': 2.0 * t_pos_um,   # NCA coating (both sides of Al)
        'al':  t_al_um,
        'sep': 2.0 * t_sep_um,   # two separators per winding repeat
        'neg': 2.0 * t_neg_um,   # graphite (both sides of Cu)
        'cu':  t_cu_um,
    }
    L = sum(t.values())

    # Effective density (volume-weighted, kg/m³)
    rho_eff = (t['pos']*rho_pos + t['al']*rho_al + t['sep']*rho_sep
               + t['neg']*rho_neg + t['cu']*rho_cu) / L

    # Effective Cp (mass-weighted, J/(kg·K))
    # BDS uses the ActiveMaterial m_dHeatCapacity as coating Cp (approximation)
    Cp_pos_jkgk = Cp_nca * 1000.0   # J/(g·K) → J/(kg·K)
    Cp_al_jkgk  = Cp_al  * 1000.0
    Cp_sep_jkgk = Cp_sep * 1000.0
    Cp_neg_jkgk = Cp_gph * 1000.0
    Cp_cu_jkgk  = Cp_cu  * 1000.0

    C_vol = (t['pos']*rho_pos*Cp_pos_jkgk + t['al']*rho_al*Cp_al_jkgk
             + t['sep']*rho_sep*Cp_sep_jkgk + t['neg']*rho_neg*Cp_neg_jkgk
             + t['cu']*rho_cu*Cp_cu_jkgk) / L    # J/(m³·K)
    Cp_eff = C_vol / rho_eff                      # J/(kg·K)

    info = {
        'rho_predicted': rho_eff,
        'Cp_predicted':  Cp_eff,
        'C_vol_predicted': C_vol,
        'rho_target':    JR_RHO_KG_M3,
        'Cp_target':     985.0,
        'C_vol_target':  JR_RHO_KG_M3 * 985.0,
    }
    return content, info


def apply_package_thermal(content: str) -> str:
    """Update can/shell material properties in the Package section."""
    content = tbm_sub(content, 'Package Comp1 Material m_dHeatCapacity',
                      round(SHELL_CP_J_KGK / 1000.0, 4))  # J/g·K
    return content


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--in',       dest='tbm_in',   required=True, help='Source TBM file')
    ap.add_argument('--manifest', dest='manifest', required=True, help='Cell manifest.json')
    ap.add_argument('--params',   dest='params',   default=None,
                    help='params.csv (actual RCR characterisation table, enables multi-temp Sets)')
    ap.add_argument('--out',      dest='tbm_out',  required=True, help='Output TBM file')
    args = ap.parse_args()

    tbm_in   = Path(args.tbm_in)
    manifest = Path(args.manifest)
    tbm_out  = Path(args.tbm_out)

    if not tbm_in.exists():
        sys.exit(f"ERROR: source TBM not found: {tbm_in}")
    if not manifest.exists():
        sys.exit(f"ERROR: manifest not found: {manifest}")

    print(f"Reading TBM:      {tbm_in}")
    content = tbm_in.read_text(encoding='utf-8', errors='replace')

    print(f"Reading manifest: {manifest}")
    mdata = load_manifest(manifest)
    geom  = extract_geom(mdata)

    # Pull kappa from manifest region_properties → jellyRoll
    jr_props = mdata.get("region_properties", {}).get("jellyRoll", {})
    kappa = jr_props.get("kappa_w_mK", [JR_KAPPA_R_W_MK, JR_KAPPA_R_W_MK, JR_KAPPA_A_W_MK])
    kappa_r = kappa[0] if isinstance(kappa, list) else kappa   # radial / tangential
    kappa_z = kappa[2] if isinstance(kappa, list) else kappa   # axial

    cap_ah = mdata.get("thermal_electrical", {}).get("capacity_ah", QNOM_AH)

    if args.params:
        params_path = Path(args.params)
        if not params_path.exists():
            sys.exit(f"ERROR: params.csv not found: {params_path}")
        print(f"Reading params:   {params_path}")
        rows = load_params_csv(params_path)
        ecm  = ecm_from_params(rows, cap_ah)
    else:
        ecm = extract_ecm(mdata)

    # ── Print summary ────────────────────────────────────────────────────────
    print("\n── Cell parameters ──────────────────────────────────")
    print(f"  JR target OD    : {geom['jr_od_mm']:.2f} mm")
    print(f"  JR axial length : {geom['jr_axial_mm']:.2f} mm")
    print(f"  Can OD          : {geom['can_od_mm']:.2f} mm")
    print(f"  Can height      : {geom['can_h_mm']:.2f} mm")
    print(f"  Capacity (Qnom) : {ecm['capacity_ah']} Ah")
    print(f"  kappa r/z       : {kappa_r} / {kappa_z} W/(m·K)")
    print(f"  ECM source      : {ecm['source']}")
    if ecm.get('sets'):
        for s in ecm['sets']:
            print(f"    Set @ {s['T_K']} K : {len(s['SOC'])} SOC pts, "
                  f"Ro {s['Ro'][0]:.5f}…{s['Ro'][-1]:.5f} Ω")
    if ecm.get('dudt_soc'):
        print(f"  dUdT points     : {len(ecm['dudt_soc'])} pts, "
              f"range {min(ecm['dudt_val']):.5f}…{max(ecm['dudt_val']):.5f} V/K")

    # ── Apply patches ────────────────────────────────────────────────────────
    print("\n── Applying geometry ────────────────────────────────")
    content = apply_geometry(content, geom)

    print("── Applying RCRTable 3D (multi-temp Sets + dUdT) ────")
    content = apply_rcrtable_3d(content, ecm, kappa_r, kappa_z)

    print("── Applying package thermal properties ──────────────")
    content = apply_package_thermal(content)

    print("── Applying jellyroll layer thermal properties ───────")
    content, jr_info = apply_jellyroll_thermal(content)

    tbm_out.parent.mkdir(parents=True, exist_ok=True)
    tbm_out.write_text(content, encoding='utf-8')
    print(f"\n── Written: {tbm_out}")

    # ── Translation notes ────────────────────────────────────────────────────
    rho_pred = jr_info['rho_predicted']
    Cp_pred  = jr_info['Cp_predicted']
    Cv_pred  = jr_info['C_vol_predicted']
    Cv_tgt   = jr_info['C_vol_target']
    Cv_err   = 100.0 * (Cv_pred - Cv_tgt) / Cv_tgt

    print("\n── Translation notes ────────────────────────────────")
    print("  DONE (automatic):")
    print(f"    JR target OD            → m_dJellyrollThickness_mm = {geom['jr_od_mm']:.2f}")
    print(f"    JR axial                → electrode/separator widths = {geom['jr_axial_mm']:.2f} mm")
    print(f"    Can OD                  → m_dRepCanXDim/YDim + Package m_dextDiameter = {geom['can_od_mm']:.2f} mm")
    print(f"    Can height              → Package m_dextHeight = {geom['can_h_mm']:.2f} mm")
    print(f"    Capacity                → m_bSpecifyCapacity=1, m_dAhCell = {ecm['capacity_ah']} Ah")
    if ecm.get('sets'):
        n_sets = len(ecm['sets'])
        n_pts  = len(ecm['sets'][0]['SOC'])
        temps  = [s['T_K'] for s in ecm['sets']]
        print(f"    RCRTable 3D Sets        → {n_sets} temperature sets ({temps}), "
              f"{n_pts} SOC pts each")
        print(f"    dUdT entropy coeff.     → {len(ecm['dudt_soc'])} pts from params.csv dUdT column")
    print(f"    Thermal conductivity    → m_dkx/y/z + m_dCondX/Y/Z = "
          f"r:{kappa_r} z:{kappa_z} W/(m·K)")
    print(f"    MaxCharge/DischCurrent  → 1000 A/m² (prevents IDACalcIC crash at t=0)")
    print(f"    Shell Cp                → Package Comp1 m_dHeatCapacity = {SHELL_CP_J_KGK/1000:.3f} J/(g·K)")
    print(f"    Jellyroll layer Cp/κ    → analytical mixing rules (literature values, no test needed):")
    print(f"        Al foil:   κ=160 W/(m·K)  Cp=0.900 J/(g·K)  [textbook]")
    print(f"        Cu foil:   κ=385 W/(m·K)  Cp=0.385 J/(g·K)  [textbook]")
    print(f"        NCA coat:  κ=1.0 W/(m·K)  Cp=0.850 J/(g·K)  [literature]")
    print(f"        Gph coat:  κ=1.0 W/(m·K)  Cp=0.750 J/(g·K)  [literature]")
    print(f"        Separator: κ=0.40 W/(m·K) Cp=2.000 J/(g·K)  [literature]")
    print()
    print(f"  Volumetric heat capacity check (analytical mixing rules vs OpenFOAM):")
    print(f"    Predicted  ρ_eff = {rho_pred:.0f} kg/m³   Cp_eff = {Cp_pred:.0f} J/(kg·K)"
          f"   ρCp = {Cv_pred/1e6:.3f} MJ/(m³·K)")
    print(f"    OpenFOAM   ρ     = {JR_RHO_KG_M3} kg/m³   Cp     ≈ 985 J/(kg·K)"
          f"   ρCp = {Cv_tgt/1e6:.3f} MJ/(m³·K)")
    print(f"    ΔρCp = {Cv_err:+.1f}%  ← BUILDER uses stock 18650 electrode thicknesses;")
    print(f"    discrepancy is expected when translating from a different cell design.")
    print(f"    kappa is unaffected (overridden exactly by m_dCondX/Y/Z in SIMMOD).")
    print()
    print("  Requires manual BDS step after import:")
    print(f"    m_bUseEntropyData: set to 1 to activate dUdT contribution")
    print(f"    Active area (m_dActiveArea_m2): read from BDS REPORT after 'Create from Tbm'")


if __name__ == '__main__':
    main()
