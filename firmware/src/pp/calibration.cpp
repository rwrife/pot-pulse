#include "pp/calibration.h"

namespace pp {

bool CalibrationStore::set(uint8_t zone, int32_t dry_raw, int32_t wet_raw,
                           float dry_threshold, float wet_threshold) {
    if (zone >= kZoneCount) return false;
    if (dry_raw == wet_raw) return false;  // would divide by zero
    if (!(dry_threshold >= 0.0f && dry_threshold < wet_threshold &&
          wet_threshold <= 1.0f)) {
        return false;
    }
    ZoneCalibration c;
    c.dry_raw = dry_raw;
    c.wet_raw = wet_raw;
    c.dry_threshold = dry_threshold;
    c.wet_threshold = wet_threshold;
    c.present = true;
    by_zone_[zone] = c;
    return true;
}

bool CalibrationStore::clear(uint8_t zone) { return by_zone_.erase(zone) > 0; }

const ZoneCalibration* CalibrationStore::get(uint8_t zone) const {
    auto it = by_zone_.find(zone);
    return it == by_zone_.end() ? nullptr : &it->second;
}

void CalibrationStore::apply(const ZoneCalibration& cal,
                             MoistureSample* s) const {
    const double span = double(cal.wet_raw) - double(cal.dry_raw);
    // 0.0 at dry endpoint, 1.0 at wet endpoint regardless of signal polarity.
    double v = (double(s->raw) - double(cal.dry_raw)) / span;
    if (v < 0.0) v = 0.0;
    if (v > 1.0) v = 1.0;
    s->calibrated = float(v);
    if (v < cal.dry_threshold) {
        s->state = ZoneState::Dry;
    } else if (v > cal.wet_threshold) {
        s->state = ZoneState::Wet;
    } else {
        s->state = ZoneState::Ok;
    }
    s->quality = Quality::Ok;
}

}  // namespace pp
