"""MPD Command - Unit Conversion Library

Oilfield unit conversions for drilling engineering calculations.
"""

import math


# --- Pressure Conversions ---

def psi_to_ppg(psi: float, tvd_ft: float) -> float:
    """Convert pressure in psi to equivalent mud weight in ppg at a given TVD."""
    if tvd_ft <= 0:
        return 0.0
    return psi / (0.052 * tvd_ft)


def ppg_to_psi(ppg: float, tvd_ft: float) -> float:
    """Convert mud weight in ppg to hydrostatic pressure in psi at a given TVD."""
    return 0.052 * ppg * tvd_ft


def psi_per_ft_to_ppg(gradient: float) -> float:
    """Convert pressure gradient (psi/ft) to equivalent mud weight (ppg)."""
    return gradient / 0.052


def ppg_to_psi_per_ft(ppg: float) -> float:
    """Convert mud weight (ppg) to pressure gradient (psi/ft)."""
    return ppg * 0.052


def kpa_to_psi(kpa: float) -> float:
    """Convert kilopascals to psi."""
    return kpa * 0.145038


def psi_to_kpa(psi: float) -> float:
    """Convert psi to kilopascals."""
    return psi / 0.145038


def bar_to_psi(bar: float) -> float:
    """Convert bar to psi."""
    return bar * 14.5038


def psi_to_bar(psi: float) -> float:
    """Convert psi to bar."""
    return psi / 14.5038


# --- Length Conversions ---

def ft_to_m(ft: float) -> float:
    """Convert feet to meters."""
    return ft * 0.3048


def m_to_ft(m: float) -> float:
    """Convert meters to feet."""
    return m / 0.3048


def inch_to_mm(inches: float) -> float:
    """Convert inches to millimeters."""
    return inches * 25.4


def mm_to_inch(mm: float) -> float:
    """Convert millimeters to inches."""
    return mm / 25.4


# --- Flow Rate Conversions ---

def gpm_to_lpm(gpm: float) -> float:
    """Convert gallons per minute to liters per minute."""
    return gpm * 3.78541


def lpm_to_gpm(lpm: float) -> float:
    """Convert liters per minute to gallons per minute."""
    return lpm / 3.78541


def bbl_to_gal(bbl: float) -> float:
    """Convert barrels to gallons."""
    return bbl * 42.0


def gal_to_bbl(gal: float) -> float:
    """Convert gallons to barrels."""
    return gal / 42.0


# --- Density Conversions ---

def ppg_to_sg(ppg: float) -> float:
    """Convert ppg to specific gravity."""
    return ppg / 8.33


def sg_to_ppg(sg: float) -> float:
    """Convert specific gravity to ppg."""
    return sg * 8.33


def ppg_to_kg_m3(ppg: float) -> float:
    """Convert ppg to kg/m³."""
    return ppg * 119.826


def kg_m3_to_ppg(kg_m3: float) -> float:
    """Convert kg/m³ to ppg."""
    return kg_m3 / 119.826


# --- Area / Volume ---

def annular_volume_bbl_per_ft(d_hole: float, d_pipe: float) -> float:
    """Calculate annular volume in bbl/ft given hole and pipe diameters in inches."""
    return (d_hole**2 - d_pipe**2) / 1029.4


def pipe_volume_bbl_per_ft(d_id: float) -> float:
    """Calculate pipe internal volume in bbl/ft given ID in inches."""
    return d_id**2 / 1029.4


def annular_capacity_gal_per_ft(d_hole: float, d_pipe: float) -> float:
    """Calculate annular capacity in gal/ft."""
    return annular_volume_bbl_per_ft(d_hole, d_pipe) * 42.0


# --- Drilling Specific ---

def mse(wob_klbs: float, rpm: float, torque_ftlbs: float,
        rop_fthr: float, bit_diameter_in: float) -> float:
    """Calculate Mechanical Specific Energy (MSE) in psi.

    MSE = (480 * T * RPM) / (D² * ROP) + (4 * WOB) / (π * D²)

    Where:
        T = torque (ft-lbs)
        RPM = rotary speed
        D = bit diameter (inches)
        ROP = rate of penetration (ft/hr)
        WOB = weight on bit (lbs, converted from klbs)
    """
    if rop_fthr <= 0 or bit_diameter_in <= 0:
        return 0.0
    wob_lbs = wob_klbs * 1000
    d = bit_diameter_in
    term1 = (480 * torque_ftlbs * rpm) / (d**2 * rop_fthr)
    term2 = (4 * wob_lbs) / (math.pi * d**2)
    return term1 + term2


def ecd_from_apwd(apwd_psi: float, tvd_ft: float) -> float:
    """Calculate ECD in ppg from APWD pressure reading and TVD."""
    if tvd_ft <= 0:
        return 0.0
    return apwd_psi / (0.052 * tvd_ft)


def overbalance_psi(bhp_psi: float, pore_pressure_psi: float) -> float:
    """Calculate overbalance pressure in psi."""
    return bhp_psi - pore_pressure_psi


def differential_pressure(bhp_psi: float, pore_pressure_psi: float) -> float:
    """Calculate differential pressure (same as overbalance). Positive = overbalanced."""
    return bhp_psi - pore_pressure_psi
