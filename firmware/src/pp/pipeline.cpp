#include "pp/pipeline.h"

#include <ArduinoJson.h>

#include <cstdio>
#include <ctime>

#include "pp/config.h"

namespace pp {

TimeQuality Sampler::time_quality() const {
    return clock_->wall_ms() >= 0 ? TimeQuality::Synchronized
                                  : TimeQuality::Relative;
}

void Sampler::sample_once(Environment* env,
                          MoistureSample out_zones[kZoneCount]) {
    env->monotonic_ms = clock_->monotonic_ms();

    // Ambient (device-level): SHT40. Failure => quality sensor_error with no
    // fabricated numbers (protocol normative rule).
    float t = 0.0f, rh = 0.0f;
    if (sht_->read(&t, &rh)) {
        env->temperature_c = t;
        env->humidity_rh = rh;
        env->ambient_quality = Quality::Ok;
    } else {
        env->temperature_c = 0.0f;
        env->humidity_rh = 0.0f;
        env->ambient_quality = Quality::SensorError;
    }

    // Light (device-level): VEML7700.
    float lux = 0.0f;
    if (veml_->read_lux(&lux)) {
        env->lux = lux;
        env->light_quality = Quality::Ok;
    } else {
        env->lux = 0.0f;
        env->light_quality = Quality::SensorError;
    }

    // Per-zone moisture via ADS1115 single-ended channels.
    const int64_t wall = clock_->wall_ms();
    for (uint8_t z = 0; z < kZoneCount; z++) {
        MoistureSample s;
        s.zone_id = zone_id(z);
        s.monotonic_ms = env->monotonic_ms;
        s.wall_ms = wall;
        int32_t counts = 0;
        if (adc_->read_channel(z, &counts)) {
            s.raw = counts;
            const ZoneCalibration* cal = cal_->get(z);
            if (cal && cal->present) {
                cal_->apply(*cal, &s);  // sets calibrated/state/quality=Ok
            } else {
                s.calibrated = 0.0f;
                s.state = ZoneState::Unknown;
                s.quality = Quality::Uncalibrated;  // raw still retained
            }
        } else {
            s.raw = 0;
            s.quality = Quality::SensorError;
            s.state = ZoneState::Unknown;
        }
        out_zones[z] = s;
        history_->append(s);
    }
}

// ---------- renderers ----------

static void iso8601(char* buf, size_t n, int64_t wall_ms) {
    // Seconds resolution is enough for MVP UI; wall_ms is epoch UTC ms.
    time_t secs = time_t(wall_ms / 1000);
    struct tm tm_utc;
    gmtime_r(&secs, &tm_utc);
    strftime(buf, n, "%Y-%m-%dT%H:%M:%SZ", &tm_utc);
}

static void write_sample(JsonObject obj, const MoistureSample& s) {
    obj["zone_id"] = s.zone_id;
    obj["moisture_raw"] = s.raw;
    if (s.quality == Quality::Ok) {
        obj["moisture_calibrated"] = s.calibrated;
        obj["state"] = zone_state_str(s.state);
    } else {
        // Normative rule: uncalibrated/sensor_error/stale must not imply a
        // valid calibration — omit, do not fabricate.
        obj["moisture_calibrated"] = nullptr;
        obj["state"] = "unknown";
    }
    obj["quality"] = quality_str(s.quality);
    if (s.wall_ms >= 0) {
        char ts[32];
        iso8601(ts, sizeof(ts), s.wall_ms);
        obj["timestamp"] = ts;
    } else {
        obj["timestamp"] = nullptr;
    }
    obj["monotonic_ms"] = s.monotonic_ms;
}

std::string render_status_json(const StatusSnapshot& snap) {
    JsonDocument doc;
    JsonObject root = doc.to<JsonObject>();
    root["schema_version"] = 1;
    root["device_id"] = snap.device_id;
    if (snap.wall_ms >= 0) {
        char ts[32];
        iso8601(ts, sizeof(ts), snap.wall_ms);
        root["timestamp"] = ts;
    } else {
        root["timestamp"] = nullptr;
    }
    root["time_quality"] = time_quality_str(snap.time_quality);
    root["paired"] = snap.paired;

    JsonObject env = root["environment"].to<JsonObject>();
    if (snap.env.light_quality == Quality::Ok) {
        env["light_lux"] = snap.env.lux;
    } else {
        env["light_lux"] = nullptr;
    }
    env["light_quality"] = quality_str(snap.env.light_quality);
    if (snap.env.ambient_quality == Quality::Ok) {
        env["temperature_c"] = snap.env.temperature_c;
        env["humidity_rh"] = snap.env.humidity_rh;
    } else {
        env["temperature_c"] = nullptr;
        env["humidity_rh"] = nullptr;
    }
    env["ambient_quality"] = quality_str(snap.env.ambient_quality);

    JsonArray zones = root["zones"].to<JsonArray>();
    for (int z = 0; z < kZoneCount; z++) {
        write_sample(zones.add<JsonObject>(), snap.zones[z]);
    }

    std::string out;
    serializeJson(doc, out);
    return out;
}

std::string render_history_json(const std::vector<MoistureSample>& page,
                                const std::string& zone_name) {
    JsonDocument doc;
    JsonObject root = doc.to<JsonObject>();
    root["schema_version"] = 1;
    root["zone_id"] = zone_name;
    JsonArray items = root["items"].to<JsonArray>();
    for (const auto& s : page) {
        write_sample(items.add<JsonObject>(), s);
    }
    root["count"] = page.size();
    std::string out;
    serializeJson(doc, out);
    return out;
}

std::string render_error_json(const char* code, const char* message) {
    JsonDocument doc;
    JsonObject root = doc.to<JsonObject>();
    root["error"] = code;
    root["message"] = message;  // no secret/config details, ever (R-06)
    std::string out;
    serializeJson(doc, out);
    return out;
}

std::string render_ok_json(const char* code) {
    JsonDocument doc;
    JsonObject root = doc.to<JsonObject>();
    root["ok"] = code;
    std::string out;
    serializeJson(doc, out);
    return out;
}

std::string render_export_json(const std::string& device_id,
                               const History& history,
                               const ConfigStore& config) {
    JsonDocument doc;
    JsonObject root = doc.to<JsonObject>();
    root["export_version"] = 1;
    root["device_id"] = device_id;
    root["sample_interval_ms"] = config.settings().sample_interval_ms;
    JsonArray names = root["zone_names"].to<JsonArray>();
    for (int z = 0; z < kZoneCount; z++) {
        names.add(config.settings().zone_names[z]);
    }
    // Explicitly no pairing tokens/nonce/credentials (R-09 golden test
    // asserts absence).
    JsonArray items = root["samples"].to<JsonArray>();
    for (const auto& s : history.all()) {
        write_sample(items.add<JsonObject>(), s);
    }
    std::string out;
    serializeJson(doc, out);
    return out;
}

}  // namespace pp
