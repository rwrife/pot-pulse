// Pot Pulse device firmware — ESP32-C3 (ESP32-C3-MINI-1 on the pot-pulse
// carrier, issue #5). Thin device layer over the portable core:
//   - GPIO/I2C pin map matches hardware/kicad netlist (issue #3).
//   - Web server endpoints freeze the docs/protocol.md contract (§ issue #6).
//   - USB serial (native USB CDC) provides provisioning + recovery without
//     Wi-Fi or cloud (IF-DBG-01).
//
// Evidence boundary: compiles and links for the device target; behavior is
// verified by native unit tests of the portable core. No bench/field claim.
#if !defined(PP_NATIVE_TEST)

#include <ArduinoJson.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>

#include <sys/time.h>

#include <cstdlib>
#include <tuple>
#include <vector>

#include "pp/calibration.h"
#include "pp/config.h"
#include "pp/history.h"
#include "pp/pipeline.h"
#include "pp/sensors.h"

// ---- board mapping (hardware/kicad/schematic-notes.md §Interfaces) ----
static constexpr int PIN_I2C_SDA = 4;   // GPIO4  / I2C_SDA
static constexpr int PIN_I2C_SCL = 5;   // GPIO5  / I2C_SCL
static constexpr int PIN_ADC_ALERT = 6;  // GPIO6 / ADC_ALERT_N (monitored)

// Calibration persistence (defined below; used by HTTP handlers above).
static void save_calibration();
static void clear_calibration_store();

// ---- device HAL adapters ----

class WireI2c : public pp::II2c {
  public:
    bool write_read(uint8_t addr, const uint8_t* wr, size_t wr_len, uint8_t* rd,
                    size_t rd_len) override {
        Wire.setTimeOut(20);  // bounded bus timeout (R-04)
        Wire.beginTransmission(addr);
        for (size_t i = 0; i < wr_len; i++) Wire.write(wr[i]);
        if (Wire.endTransmission(true) != 0) return false;
        if (rd_len == 0) return true;
        const size_t got = Wire.requestFrom(addr, (uint8_t)rd_len);
        if (got != rd_len) return false;
        for (size_t i = 0; i < rd_len; i++) rd[i] = Wire.read();
        return true;
    }
};

class EspClock : public pp::IClock {
  public:
    uint64_t monotonic_ms() const override { return millis(); }
    int64_t wall_ms() const override {
        struct timeval tv;
        gettimeofday(&tv, nullptr);
        // SNTP sets the system clock; before sync it stays at the 1970 epoch.
        if (tv.tv_sec < 1600000000) return -1;  // pre-2020 = unsynchronized
        return int64_t(tv.tv_sec) * 1000 + tv.tv_usec / 1000;
    }
};

class EspSecrets : public pp::ISecrets {
  public:
    std::string device_id() const override {
        uint64_t mac = ESP.getEfuseMac();
        char buf[20];
        snprintf(buf, sizeof(buf), "potpulse-%04X",
                 uint16_t(mac & 0xFFFF));
        return std::string(buf);
    }
    void random_bytes(uint8_t* out, size_t n) override {
        esp_fill_random(out, n);
    }
};

class PrefKv : public pp::IKv {
  public:
    std::string get(const std::string& key,
                    const std::string& fallback) const override {
        ensure_open();
        return std::string(
            prefs_.getString(key.c_str(), fallback.c_str()).c_str());
    }
    void put(const std::string& key, const std::string& value) override {
        ensure_open();
        prefs_.putString(key.c_str(), value.c_str());
    }
    void remove(const std::string& key) override {
        ensure_open();
        prefs_.remove(key.c_str());
    }

  private:
    mutable Preferences prefs_;
    mutable bool opened = false;
    void ensure_open() const {
        if (!opened) {
            prefs_.begin("potpulse", false);
            opened = true;
        }
    }
};

// ---- globals ----

static WireI2c g_i2c;
static EspClock g_clock;
static EspSecrets g_secrets;
static PrefKv g_kv;
static pp::ConfigStore g_config(&g_kv, &g_secrets, &g_clock);
static pp::CalibrationStore g_cal;
static pp::History g_history;
static pp::Ads1115 g_adc(&g_i2c);
static pp::Sht40 g_sht(&g_i2c);
static pp::Veml7700 g_veml(&g_i2c);
static pp::Sampler g_sampler(&g_adc, &g_sht, &g_veml, &g_cal, &g_history,
                             &g_clock);
static pp::Environment g_env;
static pp::MoistureSample g_zones[pp::kZoneCount];
static WebServer g_server(80);
static uint32_t g_last_sample_ms = 0;
static bool g_pending_restore_applies = false;

// ---- helpers ----

static bool authorized() {
    return g_server.hasHeader("X-PotPulse-Token") &&
           g_config.authorize(g_server.header("X-PotPulse-Token").c_str());
}

static void send_json(int code, const std::string& body) {
    g_server.send(code, "application/json", body.c_str());
}

static void require_auth_or_401() {
    if (!authorized()) {
        send_json(401, pp::render_error_json("unauthorized",
                                             "valid pairing token required"));
    }
}

static bool parse_zone_id(const String& s, int* out) {
    return pp::zone_index_of(s.c_str(), out);
}

static pp::StatusSnapshot snapshot() {
    pp::StatusSnapshot snap;
    snap.env = g_env;
    for (int z = 0; z < pp::kZoneCount; z++) snap.zones[z] = g_zones[z];
    snap.time_quality = g_sampler.time_quality();
    snap.wall_ms = g_clock.wall_ms();
    snap.paired = g_config.paired();
    snap.device_id = g_secrets.device_id();
    return snap;
}

// ---- endpoints ----

// GET /api/v1/status — pre-pairing first-run status contains NO device_id,
// no user zone names, and no retained history (protocol security boundary).
static void handle_status() {
    pp::StatusSnapshot snap = snapshot();
    if (!authorized()) {
        snap.device_id.clear();  // stable tracking id withheld pre-pairing
    }
    send_json(200, pp::render_status_json(snap));
}

// GET /api/v1/history?zone=<id>&from=<ts>&to=<ts>&limit=<n> — protected:
// returns retained user history (protocol state-changing/user-data list).
static void handle_history() {
    require_auth_or_401();
    if (g_server.arg("zone").length() == 0) {
        send_json(400, pp::render_error_json("bad_request", "zone required"));
        return;
    }
    int zone_idx = -1;
    if (!parse_zone_id(g_server.arg("zone"), &zone_idx)) {
        send_json(400, pp::render_error_json("bad_request", "zone unknown"));
        return;
    }
    int limit = g_server.arg("limit").length() ? g_server.arg("limit").toInt()
                                               : 100;
    if (limit < 1 || limit > 500) {
        send_json(400, pp::render_error_json("bad_request", "limit range"));
        return;
    }
    auto page = g_history.page(pp::zone_id(zone_idx),
                               atoll(g_server.arg("from").c_str()),
                               atoll(g_server.arg("to").c_str()), limit);
    send_json(200, pp::render_history_json(page, pp::zone_id(zone_idx)));
}

// POST /api/v1/pair/request — open on LAN, no user data; single active
// request; confirmation is out-of-band over USB serial (fail closed).
static void handle_pair_request() {
    pp::PairRequest req;
    if (!g_config.create_pair_request(&req)) {
        send_json(409, pp::render_error_json(
                           "request_active", "one active pairing request"));
        return;
    }
    JsonDocument doc;
    doc["pair_id"] = req.pair_id;
    doc["nonce"] = req.nonce;
    doc["confirm_over"] = "usb-serial";
    std::string out;
    serializeJson(doc, out);
    send_json(202, out);
}

// POST /api/v1/calibration/<zone_id> {dry_raw, wet_raw, dry_threshold,
// wet_threshold}
static void handle_calibration(const String& zone_id) {
    require_auth_or_401();
    if (!g_server.hasArg("plainBody")) return;
    JsonDocument doc;
    if (deserializeJson(doc, g_server.arg("plainBody"))) {
        send_json(400, pp::render_error_json("bad_json", "malformed body"));
        return;
    }
    uint8_t zone = 0;
    int zone_idx = -1;
    if (!parse_zone_id(zone_id, &zone_idx)) {
        send_json(400, pp::render_error_json("bad_request", "zone unknown"));
        return;
    }
    zone = uint8_t(zone_idx);
    if (!doc["dry_raw"].is<int32_t>() || !doc["wet_raw"].is<int32_t>()) {
        send_json(400, pp::render_error_json("bad_request",
                                             "dry_raw/wet_raw required"));
        return;
    }
    const float dt = doc["dry_threshold"] | 0.30f;
    const float wt = doc["wet_threshold"] | 0.70f;
    if (!g_cal.set(zone, doc["dry_raw"], doc["wet_raw"], dt, wt)) {
        send_json(400, pp::render_error_json("bad_request",
                                             "endpoints/thresholds invalid"));
        return;
    }
    save_calibration();
    g_sampler.sample_once(&g_env, g_zones);  // reflect immediately
    send_json(200, pp::render_ok_json("calibration_stored"));
}

// POST /api/v1/config {sample_interval_ms?, zone_names?[]}
static void handle_config() {
    require_auth_or_401();
    JsonDocument doc;
    if (deserializeJson(doc, g_server.arg("plainBody"))) {
        send_json(400, pp::render_error_json("bad_json", "malformed body"));
        return;
    }
    std::vector<std::string> applied;
    if (doc["sample_interval_ms"].is<uint32_t>()) {
        if (!g_config.set_sample_interval_ms(doc["sample_interval_ms"])) {
            send_json(400, pp::render_error_json(
                               "bad_request", "interval out of range"));
            return;
        }
        applied.push_back("sample_interval_ms");
    }
    if (JsonArray names = doc["zone_names"].as<JsonArray>()) {
        int z = 0;
        for (JsonVariant n : names) {
            if (z >= pp::kZoneCount) break;
            const char* s = n.as<const char*>();
            if (!s || !g_config.set_zone_name(uint8_t(z), s)) {
                send_json(400, pp::render_error_json("bad_request",
                                                     "zone name invalid"));
                return;
            }
            z++;
        }
        applied.push_back("zone_names");
    }
    JsonDocument out;
    out["ok"] = true;
    JsonArray arr = out["applied"].to<JsonArray>();
    for (auto& a : applied) arr.add(a);
    std::string body;
    serializeJson(out, body);
    send_json(200, body);
}

// POST /api/v1/export — canonical versioned export; no secrets (R-09).
static void handle_export() {
    require_auth_or_401();
    send_json(200, pp::render_export_json(g_secrets.device_id(), g_history,
                                          g_config));
}

// POST /api/v1/backup — settings + calibration + zone metadata (protocol:
// credentials/samples excluded).
static void handle_backup() {
    require_auth_or_401();
    JsonDocument doc;
    doc["backup_version"] = 1;
    doc["sample_interval_ms"] = g_config.settings().sample_interval_ms;
    JsonArray names = doc["zone_names"].to<JsonArray>();
    for (int z = 0; z < pp::kZoneCount; z++) {
        names.add(g_config.settings().zone_names[z]);
    }
    JsonArray cals = doc["calibrations"].to<JsonArray>();
    for (auto& [zone, cal] : g_cal.list()) {
        JsonObject c = cals.add<JsonObject>();
        c["zone_id"] = zone;
        c["dry_raw"] = cal.dry_raw;
        c["wet_raw"] = cal.wet_raw;
        c["dry_threshold"] = cal.dry_threshold;
        c["wet_threshold"] = cal.wet_threshold;
    }
    std::string out;
    serializeJson(doc, out);
    send_json(200, out);
}

// POST /api/v1/restore — validate complete payload BEFORE mutation
// (protocol: atomic or not at all).
static void handle_restore() {
    require_auth_or_401();
    JsonDocument doc;
    if (deserializeJson(doc, g_server.arg("plainBody"))) {
        send_json(400, pp::render_error_json("bad_json", "malformed body"));
        return;
    }
    if (doc["backup_version"] != 1) {
        send_json(422, pp::render_error_json("incompatible_version",
                                             "only backup_version 1 accepted"));
        return;
    }
    // Validate everything first.
    const uint32_t interval =
        doc["sample_interval_ms"] | g_config.settings().sample_interval_ms;
    if (interval < pp::kMinSampleIntervalMs ||
        interval > pp::kMaxSampleIntervalMs) {
        send_json(400, pp::render_error_json("bad_request",
                                             "interval out of range"));
        return;
    }
    std::vector<std::tuple<int, int32_t, int32_t, float, float>> cals;
    for (JsonObject c : doc["calibrations"].as<JsonArray>()) {
        const long zone = c["zone_id"] | -1;
        if (zone < 0 || zone >= pp::kZoneCount || !c["dry_raw"].is<int32_t>() ||
            !c["wet_raw"].is<int32_t>() ||
            c["dry_raw"].as<int32_t>() == c["wet_raw"].as<int32_t>()) {
            send_json(400, pp::render_error_json("bad_request",
                                                 "calibration invalid"));
            return;  // nothing mutated above
        }
        cals.emplace_back(int(zone), c["dry_raw"], c["wet_raw"],
                          c["dry_threshold"] | 0.30f,
                          c["wet_threshold"] | 0.70f);
    }
    // All valid — apply.
    g_config.set_sample_interval_ms(interval);
    int z = 0;
    for (JsonVariant n : doc["zone_names"].as<JsonArray>()) {
        if (z >= pp::kZoneCount) break;
        const char* s = n.as<const char*>();
        if (s) g_config.set_zone_name(uint8_t(z), s);
        z++;
    }
    for (auto& [zone, dr, wr, dt, wt] : cals) {
        g_cal.set(uint8_t(zone), dr, wr, dt, wt);
    }
    save_calibration();
    send_json(200, pp::render_ok_json("restore_applied"));
}

// DELETE /api/v1/history?confirm=confirm
static void handle_history_delete() {
    require_auth_or_401();
    if (g_server.arg("confirm") != pp::ConfigStore::kConfirmWord) {
        send_json(428, pp::render_error_json(
                           "confirmation_required",
                           "append ?confirm=confirm to delete retained history"));
        return;
    }
    const int deleted = g_history.clear();
    JsonDocument doc;
    doc["ok"] = true;
    doc["deleted"] = deleted;
    doc["complete"] = (g_history.size() == 0);
    std::string out;
    serializeJson(doc, out);
    send_json(200, out);
}

// POST /api/v1/reset {level:"full-firmware", confirm:"confirm"}
// full-firmware erases: pairing tokens, settings, zone metadata,
// calibration, retained history. Network (Wi-Fi) credentials are RETAINED
// so the device stays reachable; documented below and in firmware/README.
static void handle_reset() {
    require_auth_or_401();
    JsonDocument doc;
    if (deserializeJson(doc, g_server.arg("plainBody"))) {
        send_json(400, pp::render_error_json("bad_json", "malformed body"));
        return;
    }
    if (doc["confirm"] != pp::ConfigStore::kConfirmWord ||
        doc["level"] != "full-firmware") {
        send_json(400, pp::render_error_json(
                           "bad_request",
                           "requires {level:'full-firmware',confirm:'confirm'}"));
        return;
    }
    g_config.reset_all();
    clear_calibration_store();
    g_history.clear();
    send_json(200, pp::render_ok_json("factory_reset"));
    delay(200);
    ESP.restart();
}

// ---- calibration persistence on flash ----

static const char* kCalPath = "/calibration.json";

static void save_calibration() {
    JsonDocument doc;
    JsonArray cals = doc.to<JsonArray>();
    for (auto& [zone, cal] : g_cal.list()) {
        JsonObject c = cals.add<JsonObject>();
        c["zone_id"] = zone;
        c["dry_raw"] = cal.dry_raw;
        c["wet_raw"] = cal.wet_raw;
        c["dry_threshold"] = cal.dry_threshold;
        c["wet_threshold"] = cal.wet_threshold;
    }
    File f = LittleFS.open(kCalPath, "w");
    if (f) {
        serializeJson(doc, f);
        f.close();
    }
}

static void load_calibration() {
    File f = LittleFS.open(kCalPath, "r");
    if (!f) return;
    JsonDocument doc;
    if (!deserializeJson(doc, f)) {
        for (JsonObject c : doc.as<JsonArray>()) {
            const long zone = c["zone_id"] | -1;
            if (zone >= 0 && zone < pp::kZoneCount &&
                c["dry_raw"].is<int32_t>() && c["wet_raw"].is<int32_t>()) {
                g_cal.set(uint8_t(zone), c["dry_raw"], c["wet_raw"],
                          c["dry_threshold"] | 0.30f,
                          c["wet_threshold"] | 0.70f);
            }
        }
    }
    f.close();
}

static void clear_calibration_store() {
    for (auto& [zone, _] : g_cal.list()) g_cal.clear(uint8_t(zone));
    LittleFS.remove(kCalPath);
}

// ---- USB serial console: provisioning, pairing confirm, recovery ----
// Available over native USB CDC with no Wi-Fi or cloud dependency.

static void serial_service() {
    static String line;
    while (Serial.available()) {
        const char c = char(Serial.read());
        if (c != '\n' && c != '\r') line += c;
        else if (line.length()) {
            line.trim();
            if (line == "status") {
                Serial.printf("fw pot-pulse 0.1.0 time=%s paired=%d "
                              "history=%d/%d interval_ms=%u\n",
                              pp::time_quality_str(g_sampler.time_quality()),
                              g_config.paired() ? 1 : 0, g_history.size(),
                              g_history.capacity(),
                              g_config.settings().sample_interval_ms);
            } else if (line == "pair list") {
                for (const auto& t : g_config.tokens()) {
                    Serial.printf("token %s… label=%s\n",
                                  t.token.substr(0, 4).c_str(), t.label.c_str());
                }
                if (g_config.pending_request().active) {
                    Serial.printf("pending pair_id=%s nonce=%s\n",
                                  g_config.pending_request().pair_id.c_str(),
                                  g_config.pending_request().nonce.c_str());
                }
            } else if (line.startsWith("pair confirm ")) {
                const std::string pair_id =
                    line.substring(13).c_str();
                pp::PairingToken t;
                if (g_config.confirm_pair_request(pair_id, &t)) {
                    // Token displayed ONLY on the local USB console (out-of-
                    // band confirmation channel, R-06).
                    Serial.printf("token %s\n", t.token.c_str());
                } else {
                    Serial.println("no pending request with that pair_id");
                }
            } else if (line.startsWith("wifi ")) {
                const int sp = line.indexOf(' ', 5);
                if (sp < 0) {
                    Serial.println("usage: wifi <ssid> <password>");
                } else {
                    WiFi.begin(line.substring(5, sp).c_str(),
                               line.substring(sp + 1).c_str());
                    Serial.println("wifi connecting (state preserved by SDK)");
                }
            } else if (line == "reset wifi") {
                WiFi.disconnect(true);
                Serial.println("wifi credentials erased");
            } else if (line == "reset full-firmware") {
                g_config.reset_all();
                clear_calibration_store();
                g_history.clear();
                Serial.println("factory reset complete; restarting");
                delay(200);
                ESP.restart();
            } else if (line == "help") {
                Serial.println("commands: status | pair list | pair confirm "
                               "<pair_id> | wifi <ssid> <pass> | reset wifi | "
                               "reset full-firmware");
            } else {
                Serial.println("unknown command; try 'help'");
            }
            line = "";
        }
    }
}

// ---- Arduino entrypoints ----

void setup() {
    Serial.begin(115200);  // native USB CDC (GPIO18/19 via USBLC6-2SC6)

    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.setClock(100000);  // standard mode (bus spec §component-selection)

    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS mount failed; calibration will not persist");
    }
    load_calibration();

    pinMode(PIN_ADC_ALERT, INPUT_PULLUP);  // ADS1115 ALERT/RDY monitor

    g_adc.begin();
    g_veml.begin();
    g_sampler.sample_once(&g_env, g_zones);  // first readings before serving

    if (WiFi.psk()) {
        WiFi.begin();
        configTime(0, 0, "pool.ntp.org");  // time only; no cloud dependency
    }

    g_server.on("/api/v1/status", HTTP_GET, handle_status);
    g_server.on("/api/v1/history", HTTP_GET, handle_history);
    g_server.on("/api/v1/history", HTTP_DELETE, handle_history_delete);
    g_server.on("/api/v1/pair/request", HTTP_POST, handle_pair_request);
    g_server.on("/api/v1/calibration/z1", HTTP_POST,
                [] { handle_calibration("z1"); });
    g_server.on("/api/v1/calibration/z2", HTTP_POST,
                [] { handle_calibration("z2"); });
    g_server.on("/api/v1/calibration/z3", HTTP_POST,
                [] { handle_calibration("z3"); });
    g_server.on("/api/v1/calibration/z4", HTTP_POST,
                [] { handle_calibration("z4"); });
    g_server.on("/api/v1/config", HTTP_POST, handle_config);
    g_server.on("/api/v1/export", HTTP_POST, handle_export);
    g_server.on("/api/v1/backup", HTTP_POST, handle_backup);
    g_server.on("/api/v1/restore", HTTP_POST, handle_restore);
    g_server.on("/api/v1/reset", HTTP_POST, handle_reset);
    g_server.begin();

    g_last_sample_ms = millis();
    Serial.println("pot-pulse firmware ready");
}

void loop() {
    g_server.handleClient();
    serial_service();
    if (millis() - g_last_sample_ms >=
        g_config.settings().sample_interval_ms) {
        g_sampler.sample_once(&g_env, g_zones);
        g_last_sample_ms = millis();
    }
}

#endif  // !PP_NATIVE_TEST
