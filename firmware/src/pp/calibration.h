// Per-zone dry/wet calibration + threshold state (architecture §3.2, R-01).
#pragma once

#include <map>
#include <string>
#include <utility>
#include <vector>

#include "pp/model.h"

namespace pp {

struct ZoneCalibration {
    int32_t dry_raw = 0;
    int32_t wet_raw = 0;
    float dry_threshold = 0.30f;  // calibrated < dry → "dry"
    float wet_threshold = 0.70f;  // calibrated > wet → "wet"
    bool present = false;
};

class CalibrationStore {
  public:
    // Stores validated endpoints. Wet sensor signal is direction-agnostic:
    // wet_raw may be above or below dry_raw depending on probe wiring;
    // normalization handles both. Returns false if inputs are invalid
    // (identical endpoints would divide by zero).
    bool set(uint8_t zone, int32_t dry_raw, int32_t wet_raw,
             float dry_threshold, float wet_threshold);
    bool clear(uint8_t zone);
    const ZoneCalibration* get(uint8_t zone) const;

    // Applies calibration: raw counts -> 0..1 (0 dry, 1 wet) and threshold
    // state. Leaves quality/state untouched when uncalibrated.
    void apply(const ZoneCalibration& cal, MoistureSample* s) const;

    size_t count() const { return by_zone_.size(); }
    // For export/backup rendering: iterate present calibrations.
    std::vector<std::pair<uint8_t, ZoneCalibration>> list() const {
        return {by_zone_.begin(), by_zone_.end()};
    }

  private:
    std::map<uint8_t, ZoneCalibration> by_zone_;
};

}  // namespace pp
