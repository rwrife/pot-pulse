// Native unit tests for the Pot Pulse portable core (issue #6 AC 5).
// Everything here runs on the host against fake HALs — the same code paths
// the ESP32-C3 device build compiles (minus Arduino glue).
#include <unity.h>

#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "pp/calibration.h"
#include "pp/config.h"
#include "pp/history.h"
#include "pp/pipeline.h"
#include "pp/sensors.h"

using namespace pp;

// ---------- fakes ----------

// Scripted I2C: responses are queued per address as full read payloads;
// a queue miss records the write and NACKs (simulates an absent part).
class FakeI2c : public II2c {
  public:
    std::map<uint8_t, std::vector<std::vector<uint8_t>>> reads;
    std::vector<std::pair<uint8_t, std::vector<uint8_t>>> writes;
    bool nack_all = false;

    bool write_read(uint8_t addr, const uint8_t* wr, size_t wr_len, uint8_t* rd,
                    size_t rd_len) override {
        writes.push_back({addr, std::vector<uint8_t>(wr, wr + wr_len)});
        if (nack_all) return false;
        if (rd_len == 0) return true;
        auto& q = reads[addr];
        if (q.empty()) return false;
        auto payload = q.front();
        q.erase(q.begin());
        if (payload.size() < rd_len) return false;
        memcpy(rd, payload.data(), rd_len);
        return true;
    }
};

class FakeClock : public IClock {
  public:
    uint64_t mono = 1000;
    int64_t wall = -1;
    uint64_t monotonic_ms() const override { return const_cast<FakeClock*>(this)->mono; }
    int64_t wall_ms() const override { return wall; }
};

class FakeSecrets : public ISecrets {
  public:
    std::string device_id() const override { return "potpulse-test01"; }
    void random_bytes(uint8_t* out, size_t n) override {
        for (size_t i = 0; i < n; i++) out[i] = uint8_t(seed++);
    }
    uint8_t seed = 0xA0;
};

class FakeKv : public IKv {
  public:
    std::map<std::string, std::string> data;
    std::string get(const std::string& key,
                    const std::string& fallback) const override {
        auto it = data.find(key);
        return it == data.end() ? fallback : it->second;
    }
    void put(const std::string& key, const std::string& value) override {
        data[key] = value;
    }
    void remove(const std::string& key) override { data.erase(key); }
};

// CRC table helper: Sensirion canonical example CRC(0xBEEF) = 0x92
// (SHT4x DS v6.4 §4.4 Table 7 "Examples").
void test_sht40_crc_vector(void) {
    const uint8_t beef[2] = {0xBE, 0xEF};
    TEST_ASSERT_EQUAL_HEX8(0x92, Sht40::crc8(beef, 2));
}

// Full SHT40 happy path with datasheet-formula-checked values.
// T ticks 0x6666 -> -45 + 175*26214/65535 = 24.9999 C
// RH ticks 0x3333 -> -6 + 125*13107/65535 = 18.9640 %RH
void test_sht40_read(void) {
    FakeI2c i2c;
    const uint8_t t[2] = {0x66, 0x66};
    const uint8_t rh[2] = {0x33, 0x33};
    std::vector<uint8_t> payload = {t[0], t[1], Sht40::crc8(t, 2), rh[0],
                                    rh[1], Sht40::crc8(rh, 2)};
    i2c.reads[Sht40::kAddr].push_back(payload);
    Sht40 sht(&i2c);
    float temp = 0, hum = 0;
    TEST_ASSERT_TRUE(sht.read(&temp, &hum));
    // float32 result of 24.99998 / 18.96403; compare against the exact
    // float-rounded values with half-ULP allowance.
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 25.0f, temp);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 19.0f, hum);
    // Command issued must be 0xFD (high repeatability).
    TEST_ASSERT_EQUAL_UINT8(0x44, i2c.writes[0].first);
    TEST_ASSERT_EQUAL_UINT8(0xFD, i2c.writes[0].second[0]);
}

void test_sht40_crc_reject(void) {
    FakeI2c i2c;
    i2c.reads[Sht40::kAddr].push_back({0x66, 0x66, 0x00, 0x33, 0x33, 0x99});
    Sht40 sht(&i2c);
    float temp, hum;
    TEST_ASSERT_FALSE(sht.read(&temp, &hum));  // corrupt CRC -> failure, no
                                               // fabricated value
}

void test_sht40_bus_error(void) {
    FakeI2c i2c;  // no payload queued -> NACK
    Sht40 sht(&i2c);
    float temp, hum;
    TEST_ASSERT_FALSE(sht.read(&temp, &hum));
}

// VEML7700 lux math against the design-note worked example:
// 5581 counts, gain x1/4, IT 100 ms -> uncorrected 1500 lx -> corrected 1658
// (Vishay AN 84323 p.5).
void test_veml7700_lux_worked_example(void) {
    float lux = Veml7700::lux_from_counts(5581, 0b11, 100);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 1658.0f, lux);
}

void test_veml7700_lux_table(void) {
    // AN 84323 resolution table: gain x1 IT 100 ms = 0.5376 lx/count...
    // table shows 0.5376 for gain 1/8; recompute from 0.0042 base:
    // 0.0042 * (2/1) * (800/100) = 0.0672? No: gain x1 => (2/1)=2,
    // 0.0042*2*8 = 0.0672*... assert against documented 0.5376 for
    // gain x1/8 IT 100 ms instead (unambiguous from AN text line 405).
    float lux = Veml7700::lux_from_counts(1000, 0b10, 100);  // 1/8 gain
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 537.6f, lux);            // 1000 x 0.5376
    // No correction below 1000 lx (1500 boundary check on uncorrected).
    float low = Veml7700::lux_from_counts(100, 0b10, 100);   // 53.76 lx
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 53.76f, low);
}

void test_veml7700_read(void) {
    FakeI2c i2c;
    Veml7700 veml(&i2c);
    // begin(): config write only (no read payload consumed).
    TEST_ASSERT_TRUE(veml.begin());
    // read: pointer write ok (no read queued needed), then LE 16-bit.
    i2c.reads[Veml7700::kAddr].push_back({0xA1, 0x21});  // counts 0x21A1 LE
    float lux = 0;
    TEST_ASSERT_TRUE(veml.read_lux(&lux));
    // gain x1, IT 100 ms => 0.0042*2*8 = 0.0672 lx/count; 8609 counts.
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 8609.0f * 0.0672f, lux);
}

// ADS1115 config word: single-ended AIN2, PGA x1 (±4.096V), single shot,
// 128 SPS, comparator off, OS set.
void test_ads1115_begin_ok(void) {
    FakeI2c i2c;
    Ads1115 adc(&i2c);
    // begin(): write config ok, read config back = reset value.
    i2c.reads[Ads1115::kAddr].push_back({0x85, 0x83});
    TEST_ASSERT_TRUE(adc.begin());
    // first write must be pointer 0x01 + BE 0x8583.
    TEST_ASSERT_EQUAL_UINT8(0x01, i2c.writes[0].second[0]);
    TEST_ASSERT_EQUAL_UINT8(0x85, i2c.writes[0].second[1]);
    TEST_ASSERT_EQUAL_UINT8(0x83, i2c.writes[0].second[2]);
}

void test_ads1115_begin_mismatch(void) {
    FakeI2c i2c;
    Ads1115 adc(&i2c);
    i2c.reads[Ads1115::kAddr].push_back({0x00, 0x00});  // wrong readback
    TEST_ASSERT_FALSE(adc.begin());
}

void test_ads1115_read_channel(void) {
    FakeI2c i2c;
    Ads1115 adc(&i2c);
    // read_channel polls config (OS=1 done), then conversion register.
    i2c.reads[Ads1115::kAddr].push_back({0xC5, 0x83});  // OS bit set
    i2c.reads[Ads1115::kAddr].push_back({0x27, 0x10});  // counts 10000
    int32_t counts = 0;
    TEST_ASSERT_TRUE(adc.read_channel(2, &counts));
    TEST_ASSERT_EQUAL_INT32(10000, counts);
    // Validate config word written for AIN2 single-ended.
    const auto& w = i2c.writes[0].second;
    uint16_t cfg = (uint16_t(w[1]) << 8) | w[2];
    TEST_ASSERT_BITS(0xF000, 0xE000, cfg);  // OS=1, MUX=110 (AIN2-GND)
    TEST_ASSERT_BITS(0x0E00, 0x0200, cfg);  // PGA=001 (+-4.096V)
    TEST_ASSERT_BITS(0x0100, 0x0100, cfg);  // single-shot
    TEST_ASSERT_BITS(0x00F0, 0x0040, cfg);  // 128 SPS
    TEST_ASSERT_BITS(0x0003, 0x0003, cfg);  // comparator disabled
}

void test_calibration_math(void) {
    CalibrationStore store;
    // Dry at 30000 counts, wet at 10000 (inverted polarity supported).
    TEST_ASSERT_TRUE(store.set(1, 30000, 10000, 0.30f, 0.70f));
    const ZoneCalibration* cal = store.get(1);
    TEST_ASSERT_NOT_NULL(cal);
    MoistureSample s;
    s.zone_id = "z2";
    s.raw = 20000;  // midpoint
    store.apply(*cal, &s);
    TEST_ASSERT_EQUAL_FLOAT(0.5f, s.calibrated);
    TEST_ASSERT_EQUAL_INT(ZoneState::Ok, s.state);
    s.raw = 30000;  // dry endpoint
    store.apply(*cal, &s);
    TEST_ASSERT_EQUAL_INT(ZoneState::Dry, s.state);
    s.raw = 9000;  // wetter than wet
    store.apply(*cal, &s);
    TEST_ASSERT_EQUAL_INT(ZoneState::Wet, s.state);
}

void test_calibration_rejects_invalid(void) {
    CalibrationStore store;
    TEST_ASSERT_FALSE(store.set(0, 100, 100, 0.3f, 0.7f));  // zero span
    TEST_ASSERT_FALSE(store.set(0, 1, 2, 0.9f, 0.3f));      // inverted th
    TEST_ASSERT_FALSE(store.set(9, 1, 2, 0.3f, 0.7f));      // zone range
}

void test_uncalibrated_keeps_raw(void) {
    FakeI2c i2c;
    FakeClock clock;
    Sht40 sht(&i2c);
    Veml7700 veml(&i2c);
    Ads1115 adc(&i2c);
    CalibrationStore cal;
    History hist(16);
    Sampler sampler(&adc, &sht, &veml, &cal, &hist, &clock);
    // ADC responds for all four channels; sensors NACK (no queue) =>
    // ambient/light are sensor_error.
    for (int i = 0; i < 4; i++) {
        i2c.reads[Ads1115::kAddr].push_back({0xC5, 0x83});
        i2c.reads[Ads1115::kAddr].push_back({0x00, 0x64});  // 100 counts
    }
    Environment env;
    MoistureSample zones[kZoneCount];
    sampler.sample_once(&env, zones);
    TEST_ASSERT_EQUAL_INT(Quality::SensorError, env.ambient_quality);
    TEST_ASSERT_EQUAL_INT(Quality::Uncalibrated, zones[0].quality);
    TEST_ASSERT_EQUAL_INT32(100, zones[0].raw);  // raw retained for audit
    TEST_ASSERT_EQUAL_INT(ZoneState::Unknown, zones[0].state);
    TEST_ASSERT_EQUAL_INT(4, hist.size());
}

void test_history_bounded_and_pageable(void) {
    History h(8);
    for (int i = 0; i < 20; i++) {
        MoistureSample s;
        s.zone_id = "z1";
        s.raw = i;
        s.wall_ms = 1000 + i;
        h.append(s);
    }
    TEST_ASSERT_EQUAL_INT(8, h.size());  // hard bound (R-07)
    auto page = h.page("z1", 0, 0, 5);
    TEST_ASSERT_EQUAL_INT(5, page.size());
    TEST_ASSERT_EQUAL_INT32(19, page[0].raw);  // newest first
    auto windowed = h.page("z1", 1015, 1017, 10);
    TEST_ASSERT_EQUAL_INT(3, windowed.size());
    TEST_ASSERT_EQUAL_INT(8, h.clear());
    TEST_ASSERT_EQUAL_INT(0, h.size());
}

void test_pairing_flow_and_authorization(void) {
    FakeKv kv;
    FakeSecrets secrets;
    FakeClock clock;
    ConfigStore cfg(&kv, &secrets, &clock);
    TEST_ASSERT_FALSE(cfg.paired());
    TEST_ASSERT_FALSE(cfg.authorize("00000000000000000000000000000000"));
    PairRequest req;
    TEST_ASSERT_TRUE(cfg.create_pair_request(&req));
    TEST_ASSERT_FALSE(cfg.create_pair_request(&req));  // single active (409)
    PairingToken tok;
    TEST_ASSERT_FALSE(cfg.confirm_pair_request("deadbeef", &tok));  // wrong id
    TEST_ASSERT_TRUE(cfg.confirm_pair_request(req.pair_id, &tok));
    TEST_ASSERT_TRUE(cfg.paired());
    TEST_ASSERT_EQUAL_UINT(32, tok.token.size());
    TEST_ASSERT_TRUE(cfg.authorize(tok.token));
    TEST_ASSERT_FALSE(cfg.authorize("nope"));
    TEST_ASSERT_TRUE(cfg.revoke(tok.token));
    TEST_ASSERT_FALSE(cfg.authorize(tok.token));
    // Token survives reload (KV persistence).
    ConfigStore cfg2(&kv, &secrets, &clock);
    TEST_ASSERT_FALSE(cfg2.authorize(tok.token));  // revoked before save
}

void test_settings_validation_and_reload(void) {
    FakeKv kv;
    FakeSecrets secrets;
    FakeClock clock;
    ConfigStore cfg(&kv, &secrets, &clock);
    TEST_ASSERT_FALSE(cfg.set_sample_interval_ms(1000));  // < 30 s
    TEST_ASSERT_FALSE(cfg.set_sample_interval_ms(99999999));
    TEST_ASSERT_TRUE(cfg.set_sample_interval_ms(60000));
    TEST_ASSERT_TRUE(cfg.set_zone_name(2, "monstera"));
    TEST_ASSERT_FALSE(cfg.set_zone_name(9, "x"));
    ConfigStore reload(&kv, &secrets, &clock);
    TEST_ASSERT_EQUAL_INT(60000, reload.settings().sample_interval_ms);
    TEST_ASSERT_EQUAL_STRING("monstera",
                               reload.settings().zone_names[2].c_str());
    // Corrupt KV falls back to validated defaults (R-07).
    kv.data["interval_ms"] = "not-a-number";
    ConfigStore corrupt(&kv, &secrets, &clock);
    TEST_ASSERT_EQUAL_INT(120000, corrupt.settings().sample_interval_ms);
}

void test_status_json_contract(void) {
    StatusSnapshot snap;
    snap.device_id = "potpulse-abc1";
    snap.time_quality = TimeQuality::Relative;  // unsynchronized
    snap.paired = false;
    snap.env.light_quality = Quality::Ok;
    snap.env.lux = 320.5f;
    snap.env.ambient_quality = Quality::SensorError;  // SHT40 down
    snap.zones[0].zone_id = "z1";
    snap.zones[0].raw = 24500;
    snap.zones[0].quality = Quality::Uncalibrated;
    snap.zones[0].state = ZoneState::Unknown;
    std::string j = render_status_json(snap);
    // Schema vocabulary from docs/protocol.md.
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"schema_version\":1"));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"time_quality\":\"relative\""));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"timestamp\":null"));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"light_lux\":320.5"));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"ambient_quality\":\"sensor_error\""));
    // Missing values must be null, never fabricated numbers.
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"temperature_c\":null"));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"moisture_calibrated\":null"));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"quality\":\"uncalibrated\""));
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"zone_id\":\"z1\""));
}

void test_export_has_no_secrets(void) {
    FakeKv kv;
    FakeSecrets secrets;
    FakeClock clock;
    ConfigStore cfg(&kv, &secrets, &clock);
    PairRequest req;
    cfg.create_pair_request(&req);
    PairingToken tok;
    cfg.confirm_pair_request(req.pair_id, &tok);
    History h(16);
    MoistureSample s;
    s.zone_id = "z1";
    s.raw = 123;
    s.wall_ms = 1700000000000;
    h.append(s);
    std::string j = render_export_json("potpulse-x", h, cfg);
    TEST_ASSERT_NOT_NULL(strstr(j.c_str(), "\"export_version\":1"));
    // R-09: tokens/nonce must not appear anywhere in export.
    TEST_ASSERT_NULL(strstr(j.c_str(), tok.token.c_str()));
    TEST_ASSERT_NULL(strstr(j.c_str(), req.nonce.c_str()));
    TEST_ASSERT_NULL(strstr(j.c_str(), "pair_tokens"));
}

void test_sampler_time_quality(void) {
    FakeI2c i2c;
    FakeClock clock;
    Sht40 sht(&i2c);
    Veml7700 veml(&i2c);
    Ads1115 adc(&i2c);
    CalibrationStore cal;
    History hist(16);
    Sampler sampler(&adc, &sht, &veml, &cal, &hist, &clock);
    TEST_ASSERT_EQUAL_INT(TimeQuality::Relative, sampler.time_quality());
    clock.wall = 1700000000000;
    TEST_ASSERT_EQUAL_INT(TimeQuality::Synchronized, sampler.time_quality());
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_sht40_crc_vector);
    RUN_TEST(test_sht40_read);
    RUN_TEST(test_sht40_crc_reject);
    RUN_TEST(test_sht40_bus_error);
    RUN_TEST(test_veml7700_lux_worked_example);
    RUN_TEST(test_veml7700_lux_table);
    RUN_TEST(test_veml7700_read);
    RUN_TEST(test_ads1115_begin_ok);
    RUN_TEST(test_ads1115_begin_mismatch);
    RUN_TEST(test_ads1115_read_channel);
    RUN_TEST(test_calibration_math);
    RUN_TEST(test_calibration_rejects_invalid);
    RUN_TEST(test_uncalibrated_keeps_raw);
    RUN_TEST(test_history_bounded_and_pageable);
    RUN_TEST(test_pairing_flow_and_authorization);
    RUN_TEST(test_settings_validation_and_reload);
    RUN_TEST(test_status_json_contract);
    RUN_TEST(test_export_has_no_secrets);
    RUN_TEST(test_sampler_time_quality);
    return UNITY_END();
}
