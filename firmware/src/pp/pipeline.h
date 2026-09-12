// Sampling pipeline + protocol JSON rendering (ArduinoJson is header-only
// and compiles in the native test env too, so payload bytes are covered by
// unit tests shared with the device build).
#pragma once

#include <string>

#include "pp/calibration.h"
#include "pp/config.h"
#include "pp/history.h"
#include "pp/hal.h"
#include "pp/sensors.h"

namespace pp {

// Pulls one sample from every source, applies calibration, assigns time,
// and appends to bounded history (architecture §5 steps 1–4).
class Sampler {
  public:
    Sampler(Ads1115* adc, Sht40* sht, Veml7700* veml, CalibrationStore* cal,
            History* history, IClock* clock)
        : adc_(adc), sht_(sht), veml_(veml), cal_(cal), history_(history),
          clock_(clock) {}

    void sample_once(Environment* env, MoistureSample out_zones[kZoneCount]);

    TimeQuality time_quality() const;

  private:
    Ads1115* adc_;
    Sht40* sht_;
    Veml7700* veml_;
    CalibrationStore* cal_;
    History* history_;
    IClock* clock_;
};

// Protocol JSON renderers. All shapes follow docs/protocol.md sketch +
// normative rules (raw retained, uncalibrated never implied valid,
// explicit unsynchronized time).
std::string render_status_json(const StatusSnapshot& snap);
std::string render_history_json(const std::vector<MoistureSample>& page,
                                const std::string& zone_name);
std::string render_error_json(const char* code, const char* message);
std::string render_ok_json(const char* code);

// Canonical versioned export (protocol POST /api/v1/export): JSON document
// with metadata + all retained samples. Never contains credentials.
std::string render_export_json(const std::string& device_id,
                               const History& history,
                               const ConfigStore& config);

}  // namespace pp
