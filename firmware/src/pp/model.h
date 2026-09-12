// Pot Pulse firmware portable core — shared constants and small types.
//
// Nothing in firmware/src/pp/ may include Arduino/ESP headers: the core is
// compiled both for the ESP32-C3 device target and for native unit tests.
#pragma once

#include <cstdint>
#include <cstring>
#include <string>

namespace pp {

constexpr int kZoneCount = 4;
constexpr int kMaxZoneNameLen = 32;
constexpr int kMaxJsonBody = 8192;         // request body hard limit (R-07 bounds)
constexpr int kHistoryCapacity = 2048;     // bounded ring across all zones (R-07)
constexpr uint32_t kMinSampleIntervalMs = 30000;   // architecture: 30 s..15 min
constexpr uint32_t kMaxSampleIntervalMs = 900000;

// Quality vocabularies (docs/protocol.md normative strings).
enum class Quality : uint8_t { Ok, SensorError, Uncalibrated, Stale };
enum class ZoneState : uint8_t { Dry, Ok, Wet, Unknown };
enum class TimeQuality : uint8_t { Synchronized, Relative, Unknown };

const char* quality_str(Quality q);
const char* zone_state_str(ZoneState s);
const char* time_quality_str(TimeQuality q);

// One per-zone moisture observation.
struct MoistureSample {
    std::string zone_id;         // persistent zone identifier (z1..z4)
    int32_t raw = 0;             // ADS1115 counts (kept forever, AC: audit trail)
    float calibrated = 0.0f;     // 0.0 (dry) .. 1.0 (wet), valid only when quality==Ok
    Quality quality = Quality::SensorError;
    ZoneState state = ZoneState::Unknown;
    uint64_t monotonic_ms = 0;   // always available device clock
    int64_t wall_ms = -1;        // -1 until time synchronized
};

// Device-level environment block.
struct Environment {
    float lux = 0.0f;
    Quality light_quality = Quality::SensorError;
    float temperature_c = 0.0f;
    float humidity_rh = 0.0f;
    Quality ambient_quality = Quality::SensorError;
    uint64_t monotonic_ms = 0;
};

struct StatusSnapshot {
    Environment env;
    MoistureSample zones[kZoneCount];
    TimeQuality time_quality = TimeQuality::Unknown;
    int64_t wall_ms = -1;
    bool paired = false;
    std::string device_id;
};

}  // namespace pp
