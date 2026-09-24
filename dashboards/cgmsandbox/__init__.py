"""CGM Sandbox — interactive exploration and visualization of CGM and wearable data.

Single import surface for the public API::

    from cgmsandbox import CGMViewer, TimeInRangeOverlay, HypnogramExtension

Data can be loaded from local Open mHealth / IEEE JSON files (``source="file"``)
or from a JupyterHealth Exchange client DataFrame (``source="client"``).
"""

from .cgm_methods import (
    detect_fasting_segments,
    detect_stable_glucose,
    extract_ppgr_pairs,
    extract_wakeup_glucose,
    label_sleep_period,
    nocturnal_vs_diurnal,
    process_cgm,
)
from .cgmquantify import (
    cv,
    gmi,
    hbgi,
    lbgi,
    mage_ma,
    mage_ma_segments,
    summarize_measures,
    tir_70_180,
)
from .extensions import HypnogramExtension, SleepCompositionExtension, StepCountExtension
from .loader import (
    load_cgm_data,
    load_food_entry_data,
    load_sleep_data,
    load_sleep_nights,
    load_step_count,
)
from .overlays import (
    CgmMeasuresOverlay,
    CvOverlay,
    FoodEntryOverlay,
    MageOverlay,
    MeanGlucoseOverlay,
    PPGROverlay,
    SleepWindowOverlay,
    TimeInRangeOverlay,
    WakeupGlucoseOverlay,
)
from .viewer import CGMViewer

__version__ = "0.1.0"

__all__ = [
    # loaders
    "load_cgm_data",
    "load_sleep_data",
    "load_sleep_nights",
    "load_food_entry_data",
    "load_step_count",
    # viewer and extensions
    "CGMViewer",
    "HypnogramExtension",
    "SleepCompositionExtension",
    "StepCountExtension",
    # overlays
    "MeanGlucoseOverlay",
    "TimeInRangeOverlay",
    "FoodEntryOverlay",
    "CgmMeasuresOverlay",
    "CvOverlay",
    "MageOverlay",
    "WakeupGlucoseOverlay",
    "PPGROverlay",
    "SleepWindowOverlay",
    # signal processing
    "process_cgm",
    "detect_stable_glucose",
    "detect_fasting_segments",
    "extract_wakeup_glucose",
    "extract_ppgr_pairs",
    "label_sleep_period",
    "nocturnal_vs_diurnal",
    # quantified measures
    "tir_70_180",
    "cv",
    "gmi",
    "hbgi",
    "lbgi",
    "mage_ma",
    "mage_ma_segments",
    "summarize_measures",
]
