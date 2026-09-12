#include "pp/model.h"

namespace pp {

const char* quality_str(Quality q) {
    switch (q) {
        case Quality::Ok: return "ok";
        case Quality::SensorError: return "sensor_error";
        case Quality::Uncalibrated: return "uncalibrated";
        case Quality::Stale: return "stale";
    }
    return "sensor_error";
}

const char* zone_state_str(ZoneState s) {
    switch (s) {
        case ZoneState::Dry: return "dry";
        case ZoneState::Ok: return "ok";
        case ZoneState::Wet: return "wet";
        case ZoneState::Unknown: return "unknown";
    }
    return "unknown";
}

const char* time_quality_str(TimeQuality q) {
    switch (q) {
        case TimeQuality::Synchronized: return "synchronized";
        case TimeQuality::Relative: return "relative";
        case TimeQuality::Unknown: return "unknown";
    }
    return "unknown";
}

}  // namespace pp
